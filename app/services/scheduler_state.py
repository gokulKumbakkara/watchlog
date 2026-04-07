"""
Module-level holders for resources needed by the APScheduler job,
which runs outside of request context.
"""
from typing import Optional

_redis = None
_chroma = None


def set_redis(r) -> None:
    global _redis
    _redis = r


def get_redis():
    return _redis


def set_chroma(c) -> None:
    global _chroma
    _chroma = c


def get_chroma():
    return _chroma
