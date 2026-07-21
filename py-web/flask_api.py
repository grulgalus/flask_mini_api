"""
============================================================
 FLASK API - Mini Framework Built on Flask
============================================================
Quick overview of what this file can do (details are in the
comments next to each function/decorator below):

CONFIG      flask_secret, auto_secret, load_env
HELPERS     get_json, get_query, get_form, client_ip, is_mobile,
            uptime_string
INIT        init_dir
STORE       store        - simple in-memory key-value store
ROUTES      routes       - home, new_route, new_routes, api_route,
                           redirect_route, static_folder,
                           upload_route, error_page
            route_group  - routes with a common prefix (e.g., /api/v1)
PROTECTION  require_key, login_required, require_json_fields
PERFORMANCE cache, rate_limit
STATUS      maintenance_mode
LOGGING     log_to_file  - sends request logs to a file,
                           reset_stats
CORS        automatic, no need to call (see CORS section)
DEBUG       list_routes, /routes, /health, /stats
EXECUTION   run_app, cloudflare_web

Most setup functions (init_dir, auto_secret, log_to_file,
maintenance_mode...) must be called manually - nothing happens
automatically until you call it.
============================================================
"""

from flask import *
from time_logger import _time
from logger import logger
import subprocess, logging, os, secrets, time, re, threading
from collections import defaultdict
from functools import wraps

app = Flask(__name__)
_port = 5000
_start_time = time.time()

# Disables default gray werkzeug log (127.0.0.1 - - [...] "GET / ..." 200 -),
# replacing it with our colored log below (_log_request) via logger.py
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# ================= CONFIG =================
def flask_secret(s):
    app.secret_key = s

def auto_secret(path=".secret_key"):
    # The key is saved to a file so session/flash data remain valid across restarts.
    # Without this, Flask's debug reloader would generate a new key on every restart,
    # causing users to lose their session/login status.
    if os.path.exists(path):
        with open(path) as f:
            app.secret_key = f.read().strip()
    else:
        key = secrets.token_hex(32)
        with open(path, "w") as f:
            f.write(key)
        app.secret_key = key

def load_env(path=".env"):
    # Simple .env loader so you don't need to install python-dotenv
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ[key.strip()] = value.strip()

# ================= HELPERS =================
def get_json(default=None):
    # Safe access to request JSON body - returns default if missing or invalid JSON
    # instead of raising an error
    data = request.get_json(silent=True)
    if data is None:
        return default if default is not None else {}
    return data

def get_query(key, default=None):
    # Shortcut for request.args.get to avoid writing it repeatedly
    return request.args.get(key, default)

def get_form(key, default=None):
    # Same as above, but for standard HTML forms (request.form)
    return request.form.get(key, default)

def client_ip():
    # Through Cloudflare tunnel (cloudflare_web()), request.remote_addr points to cloudflared
    # running locally, not the real visitor. Cloudflare sends the real IP in the
    # CF-Connecting-IP header, so we try that first before falling back to remote_addr.
    return request.headers.get("CF-Connecting-IP", request.remote_addr)

def is_mobile():
    # Estimate based on User-Agent header whether request comes from mobile/tablet -
    # useful when serving different templates for mobile vs desktop
    ua = request.headers.get("User-Agent", "").lower()
    return any(k in ua for k in ["mobile", "android", "iphone"])

def uptime_string():
    # Nicer uptime format than raw seconds, e.g. "2h 15m 3s" instead of "8103.4"
    seconds = int(time.time() - _start_time)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)

# ================= INIT =================
def init_dir():
    # Creates templates/, static/js/, and static/css/ if they don't exist yet.
    # Leaves existing folders intact. Must be called manually.
    folders = ["templates", os.path.join("static", "js"), os.path.join("static", "css")]
    created = [f for f in folders if not os.path.exists(f)]
    for f in folders:
        os.makedirs(f, exist_ok=True)
    if created:
        logger.info(f"Created: {', '.join(created)}")
    else:
        logger.info("Folders already exist, nothing was created.")

# ================= STORE =================
class store():
    # Simple in-memory key-value store for fast prototyping without a database.
    # WARNING: lives in memory only - server restart = data loss. Not a replacement for a real DB.
    _data = {}

    @staticmethod
    def set(key, value):
        store._data[key] = value

    @staticmethod
    def get(key, default=None):
        return store._data.get(key, default)

    @staticmethod
    def delete(key):
        store._data.pop(key, None)

    @staticmethod
    def has(key):
        return key in store._data

    @staticmethod
    def all():
        return dict(store._data)

    @staticmethod
    def clear():
        store._data.clear()

# ================= ROUTES =================
class routes():
    @staticmethod
    def home(template, data=None):
        # data = dict (static data) or a callable returning dict (recalculated on every request)
        def view():
            ctx = data() if callable(data) else (data or {})
            return render_template(template, **ctx)
        app.add_url_rule("/", "home", view)

    @staticmethod
    def new_route(s, template, data=None, methods=["GET"]):
        def view():
            ctx = data() if callable(data) else (data or {})
            return render_template(template, **ctx)
        app.add_url_rule(f"/{s}", s, view, methods=methods)

    @staticmethod
    def new_routes(mapping):
        # Registers multiple simple routes at once from a dict {path: template}
        # e.g., routes.new_routes({"about": "about.html", "contact": "contact.html"})
        for path, template in mapping.items():
            routes.new_route(path, template)

    @staticmethod
    def api_route(s, func, methods=["GET"]):
        # func is a standard Python function returning dict/list -> automatically sent as JSON.
        # If func raises an exception, a clean JSON error is returned instead of Flask's HTML error page.
        # If func returns a ready Response or tuple (body, status), it is forwarded without modifications.
        def view():
            try:
                result = func()
                if isinstance(result, (Response, tuple)):
                    return result
                return jsonify(result)
            except Exception as e:
                logger.error(f"api_route /{s} failed: {e}")
                return jsonify({"error": str(e)}), 500
        app.add_url_rule(f"/{s}", s, view, methods=methods)

    @staticmethod
    def redirect_route(s, target, code=302):
        # Quick redirect route, e.g., routes.redirect_route("old", "/new")
        app.add_url_rule(f"/{s}", f"redirect_{s}", lambda: redirect(target, code=code))

    @staticmethod
    def static_folder(url_path, folder_path):
        # Exposes any folder as static content (not just default /static)
        # e.g., routes.static_folder("/uploads", "my_uploads")
        app.add_url_rule(
            f"{url_path}/<path:filename>",
            f"static_{url_path.strip('/')}",
            lambda filename: send_from_directory(folder_path, filename)
        )

    @staticmethod
    def upload_route(s, folder, allowed_ext=None, field="file"):
        # Ready-to-use file upload endpoint via POST.
        # e.g., routes.upload_route("upload", "uploads", allowed_ext=[".png", ".jpg"])
        os.makedirs(folder, exist_ok=True)
        def view():
            if field not in request.files:
                return jsonify({"error": f"Missing file in field '{field}'"}), 400
            f = request.files[field]
            if f.filename == "":
                return jsonify({"error": "No file selected"}), 400
            ext = os.path.splitext(f.filename)[1].lower()
            if allowed_ext and ext not in allowed_ext:
                return jsonify({"error": f"Extension {ext} is not allowed"}), 400
            path = os.path.join(folder, f.filename)
            f.save(path)
            logger.info(f"File uploaded: {path}")
            return jsonify({"ok": True, "filename": f.filename})
        app.add_url_rule(f"/{s}", s, view, methods=["POST"])

    @staticmethod
    def error_page(code, template):
        # Overrides default 404/500 error pages with a custom template.
        # e.g., routes.error_page(404, "404.html")
        @app.errorhandler(code)
        def _custom_error(e):
            return render_template(template), code

# ================= ROUTE GROUPS =================
class route_group():
    # Group of routes under a common prefix - simpler alternative to Flask Blueprints.
    # e.g.:
    #   api = route_group("/api/v1")
    #   api.api_route("users", get_users)   -> registers as /api/v1/users
    def __init__(self, prefix):
        self.prefix = prefix.strip("/")

    def _full_path(self, s):
        s = s.strip("/")
        return f"{self.prefix}/{s}" if self.prefix else s

    def new_route(self, s, template, data=None, methods=["GET"]):
        routes.new_route(self._full_path(s), template, data, methods)

    def api_route(self, s, func, methods=["GET"]):
        routes.api_route(self._full_path(s), func, methods)

    def redirect_route(self, s, target, code=302):
        routes.redirect_route(self._full_path(s), target, code)

# ================= TEMPLATE GLOBALS =================
@app.context_processor
def _inject_globals():
    # {{ now }} will be available in ALL templates automatically
    return {"now": _time()}

# ================= HEALTH / STATS / MISC =================
_request_count = {"total": 0, "errors": 0}

@app.route("/health")
def _health():
    return jsonify({
        "status": "ok",
        "uptime_seconds": round(time.time() - _start_time, 1),
        "uptime": uptime_string()
    })

@app.route("/stats")
def _stats_json():
    # More detailed than /health - tracks total requests and error count
    return jsonify({
        "uptime": uptime_string(),
        "requests_total": _request_count["total"],
        "requests_errors": _request_count["errors"]
    })

def reset_stats():
    # Resets request counters for /stats (uptime resets only on server restart)
    _request_count["total"] = 0
    _request_count["errors"] = 0
    logger.info("Statistics reset")

@app.route("/favicon.ico")
def _favicon():
    return "", 204  # Prevents 404 noise in logs on browser visits

@app.route("/apple-touch-icon.png")
@app.route("/apple-touch-icon-precomposed.png")
def _apple_icon():
    return "", 204

# ================= AUTH / ROUTE PROTECTION =================
def require_key(key):
    # Decorator to protect api_route functions using an X-API-Key header
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if request.headers.get("X-API-Key") != key:
                logger.warn(f"Rejected request to {request.path} - invalid or missing API key")
                return jsonify({"error": "unauthorized"}), 401
            return func(*args, **kwargs)
        return wrapper
    return decorator

def login_required(func):
    # Assumes you set session["user"] manually (e.g., after login)
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect("/login")
        return func(*args, **kwargs)
    return wrapper

# ================= VALIDATION =================
def require_json_fields(*fields):
    # Decorator - ensures the JSON body contains all specified fields.
    # Useful before api_route functions, e.g., @require_json_fields("name", "email")
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            data = get_json()
            missing = [f for f in fields if f not in data]
            if missing:
                return jsonify({"error": f"Missing field(s): {', '.join(missing)}"}), 400
            return func(*args, **kwargs)
        return wrapper
    return decorator

# ================= CACHE =================
_cache_store = {}

def cache(seconds=60):
    # Simple in-memory cache - responses are cached per path + query string for X seconds.
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{request.path}?{request.query_string.decode()}"
            now = time.time()
            if key in _cache_store:
                cached_at, value = _cache_store[key]
                if now - cached_at < seconds:
                    return value
            result = func(*args, **kwargs)
            _cache_store[key] = (now, result)
            return result
        return wrapper
    return decorator

# ================= RATE LIMIT =================
_rate_hits = defaultdict(list)

def rate_limit(max_requests=10, per_seconds=60):
    # Simple IP-based rate limit held in memory.
    # Uses client_ip() instead of request.remote_addr to work properly behind Cloudflare.
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            ip = client_ip()
            now = time.time()
            _rate_hits[ip] = [t for t in _rate_hits[ip] if now - t < per_seconds]
            if len(_rate_hits[ip]) >= max_requests:
                return jsonify({"error": "too many requests"}), 429
            _rate_hits[ip].append(now)
            return func(*args, **kwargs)
        return wrapper
    return decorator

# ================= MAINTENANCE =================
_maintenance = False

def maintenance_mode(on=True):
    # When enabled, all requests (except /health) receive a 503 HTTP status.
    global _maintenance
    _maintenance = on
    logger.info(f"Maintenance mode {'enabled' if on else 'disabled'}")

@app.before_request
def _check_maintenance():
    if _maintenance and request.path != "/health":
        return jsonify({"error": "Server is currently under maintenance, please try again later"}), 503

# ================= REQUEST LOG =================
_ansi_re = re.compile(r"\033\[[0-9;]*m")
_log_file = None

def log_to_file(path="server.log"):
    # Enables writing request logs to a file in addition to stdout.
    global _log_file
    _log_file = path
    logger.info(f"File logging enabled: {path}")

def _write_log_line(line):
    if not _log_file:
        return
    try:
        with open(_log_file, "a", encoding="utf-8") as f:
            f.write(_ansi_re.sub("", line) + "\n")
    except OSError:
        pass

@app.before_request
def _start_request_timer():
    request._t0 = time.time()

@app.after_request
def _log_request(response):
    elapsed = (time.time() - getattr(request, "_t0", time.time())) * 1000
    msg = f"[{response.status_code}] {request.method} {request.path} ({elapsed:.1f}ms)"
    _request_count["total"] += 1
    if response.status_code < 400:
        logger.info(msg)
    else:
        _request_count["errors"] += 1
        logger.error(msg)
    _write_log_line(f"{_time()} {msg}")
    return response

@app.errorhandler(404)
def _not_found(e):
    return f"<h1 style='font-family:monospace'>404</h1><p style='font-family:monospace'>Page {request.path} does not exist.</p>", 404

@app.errorhandler(500)
def _server_error(e):
    return f"<h1 style='font-family:monospace'>500</h1><p style='font-family:monospace'>An internal server error occurred.</p>", 500

# ================= CORS =================
_cors_allowed = None  # None = allow any origin

def restrict_cors(origins):
    global _cors_allowed
    _cors_allowed = origins

def _apply_cors(response):
    origin = request.headers.get("Origin")
    if origin and (_cors_allowed is None or origin in _cors_allowed):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-API-Key"
    return response

@app.before_request
def _cors_preflight():
    if request.method == "OPTIONS" and request.headers.get("Origin"):
        return _apply_cors(app.make_default_options_response())

@app.after_request
def _cors_after(response):
    return _apply_cors(response)

# ================= DEBUG =================
def list_routes():
    # Prints all registered routes - useful for debugging
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        methods = ",".join(sorted(rule.methods - {"HEAD", "OPTIONS"}))
        logger.info(f"{methods:12s} /{rule.rule.lstrip('/')}")

@app.route("/routes")
def _routes_json():
    # Meta endpoint returning a JSON list of all registered paths
    return jsonify(sorted(str(rule) for rule in app.url_map.iter_rules()))

# ================= RUN =================
def _print_banner(port):
    url = f"http://localhost:{port}"
    line = f"  Flask API running on {url}  "
    border = "═" * len(line)
    print(f"\033[95m╔{border}╗\n║{line}║\n╚{border}╝\033[0m")

def run_app(p=None, cloudflare=False):
    global _port
    if p is not None:
        _port = int(p)  # Bezpečně převede port v uvozovkách (např. "5000") na číslo
    
    # Avoid duplicate banners/logs during Flask reloader initialization
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        _print_banner(_port)
        logger.info(f"Starting web server on http://localhost:{_port}")
        if cloudflare:
            cloudflare_web()

    app.run(debug=True, port=_port)

# ================= CLOUDFLARE =================
def cloudflare_web():
    """Launches Cloudflare Tunnel in a background thread so it doesn't block Flask execution."""
    def _run_tunnel():
        time.sleep(1)  # Brief pause to ensure Flask starts listening first
        logger.info(f"Cloudflaring web http://localhost:{_port}")
        try:
            subprocess.run(["cloudflared", "tunnel", "--url", f"http://localhost:{_port}"])
        except Exception as e:
            logger.error(f"Cloudflare Tunnel process stopped: {e}")

    thread = threading.Thread(target=_run_tunnel, daemon=True)
    thread.start()
