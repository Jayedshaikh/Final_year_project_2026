"""Utilities for timing code execution.

Use time.perf_counter() for high-resolution timings (e.g., model training time).
"""
import time
from contextlib import contextmanager
from typing import Generator


@contextmanager
def timer() -> Generator[dict, None, None]:
    """Context manager that records elapsed wall-clock time in seconds.

    Usage::

        with timer() as t:
            do_something()
        elapsed = t["elapsed"]

    Yields:
        A dict with key "elapsed" populated on exit.
    """
    result: dict = {}
    start = time.perf_counter()
    try:
        yield result
    finally:
        result["elapsed"] = time.perf_counter() - start


def time_it(func):
    """Decorator that adds an elapsed_seconds attribute to the return value dict (if dict).

    Not a replacement for timer(); use this only for simple wrapping.
    """
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        if isinstance(result, dict):
            result["elapsed_seconds"] = elapsed
        return result
    wrapper.__name__ = func.__name__
    return wrapper
