from time_logger import _time

class logger():
    @staticmethod
    def info(s):
        print(f"{_time()} \033[34m[INFO]\033[0m \033[95m{s}\033[0m")
    @staticmethod
    def warn(s):
        print(f"{_time()} \033[33m[WARN] {s}\033[0m")
    @staticmethod
    def error(s):
        print(f"{_time()} \033[31m[ERROR] {s}\033[0m")
