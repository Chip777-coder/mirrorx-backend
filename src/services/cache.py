# src/services/cache.py
"""
Lightweight in-memory cache for MirrorX.
Caches recent signal calculations to avoid redundant upstream calls.
"""

import time

CACHE = {}
DEFAULT_TTL = 180  # seconds

def get_cache(key):
    """Return cached value if fresh."""
    if key in CACHE:
        val, expires = CACHE[key]
        if expires > time.time():
            return val
        else:
            del CACHE[key]
    return None

def set_cache(key, value, ttl=DEFAULT_TTL):
    """Store a value in cache with a TTL."""
    CACHE[key] = (value, time.time() + ttl)
