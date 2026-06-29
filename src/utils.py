"""共享工具：重试、日志"""
import time
import functools
from datetime import datetime


def retry(max_attempts: int = 3, base_delay: float = 2.0, backoff: float = 2.0):
    """指数退避重试装饰器
    
    Args:
        max_attempts: 最大尝试次数（含首次）
        base_delay: 首次重试等待秒数
        backoff: 退避倍数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt < max_attempts - 1:
                        delay = base_delay * (backoff ** attempt)
                        print(f"[Retry] {func.__name__} 第{attempt+1}次失败，"
                              f"{delay:.1f}s 后重试: {e}")
                        time.sleep(delay)
            raise last_exc
        return wrapper
    return decorator


class Logger:
    """简易结构化日志"""
    
    @staticmethod
    def _log(level: str, source: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] [{level}] [{source}] {msg}")
    
    @classmethod
    def info(cls, source: str, msg: str):
        cls._log("INFO", source, msg)
    
    @classmethod
    def warn(cls, source: str, msg: str):
        cls._log("WARN", source, msg)
    
    @classmethod
    def error(cls, source: str, msg: str):
        cls._log("ERROR", source, msg)


log = Logger()
