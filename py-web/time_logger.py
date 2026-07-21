import datetime

def _time():
    return datetime.datetime.now().strftime("\033[90m%Y-%m-%d %H:%M:%S\033[0m")
