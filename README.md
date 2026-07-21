# Flask Mini API

A powerful, lightweight wrapper around Flask designed for rapid development. It completely eliminates boilerplate code and comes with built-in colored logging, simplified routing, security decorators, and instant Cloudflare tunneling.

## Features
- 🚀 **Instant Webhook/API:** Minimal setup required.
- 🌍 **Built-in Cloudflare Tunnel:** Expose your local server to the internet instantly using `cloudflare=True`.
- 🎨 **Beautiful Colored Logging:** Replaces default ugly Werkzeug logs with clean, timed, and colored terminal outputs.
- 🛡️ **Decorators out-of-the-box:** Easy `@rate_limit`, `@cache`, `@require_key`, and `@require_json_fields`.
- 🗄️ **Memory Store:** A built-in key-value memory store for fast prototyping without setting up a database.

## Installation

```bash
pip install flask-mini-api
```

# Quick Start Example
from flask_mini_api.flask_api import app, routes, run_app, require_key, rate_limit

# 1. Simple API Route (Automatically returns JSON)
routes.api_route("ping", lambda: {"status": "ok", "message": "Pong!"})

# 2. Advanced Route with rate limiting and API Key protection
@require_key("my-secret-key-123")
@rate_limit(max_requests=5, per_seconds=60)
def get_secure_data():
    return {"data": "This is highly classified"}

routes.api_route("secure", get_secure_data)

# 3. Start the server (Starts locally and opens a public Cloudflare URL!)
if __name__ == "__main__":
    run_app(p=5000, cloudflare=True)
Advanced Features
Route Groups
Need to prefix your routes like /api/v1/? Use route_group:

from flask_mini_api.flask_api import route_group

api_v1 = route_group("/api/v1")
api_v1.api_route("users", lambda: {"users": ["Alice", "Bob"]})
In-Memory Database
For fast prototyping, you don't need Redis. Use the built-in store:

from flask_mini_api.flask_api import store

store.set("server_status", "maintenance")
print(store.get("server_status"))
Maintenance Mode
Easily lock down your API with one function (returns 503 for all endpoints except /health):

from flask_mini_api.flask_api import maintenance_mode

maintenance_mode(True)
License
This project is open-source and available under the MIT License.
