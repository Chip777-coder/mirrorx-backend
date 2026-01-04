# src/services/dex_proxy.py
import time
import requests
from functools import lru_cache

DEX_BASE = "https://api.dexscreener.com"
_TIMEOUT = 12

def _get(path: str, params: dict | None = None):
    url = f"{DEX_BASE}{path}"
    r = requests.get(url, params=params, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()

# -----------------------
# Simple caching (best effort)
# -----------------------
def _cache_bust_key(ttl_seconds: int) -> int:
    return int(time.time() // ttl_seconds)

@lru_cache(maxsize=64)
def _cached_get(path: str, params_tuple: tuple, ttl_bucket: int):
    params = dict(params_tuple)
    return _get(path, params=params)

def cached_get(path: str, params: dict | None = None, ttl_seconds: int = 30):
    params = params or {}
    params_tuple = tuple(sorted(params.items()))
    return _cached_get(path, params_tuple, _cache_bust_key(ttl_seconds))

# -----------------------
# Wrapped endpoints
# -----------------------
def dex_token_profiles_latest():
    return cached_get("/token-profiles/latest/v1", ttl_seconds=60)

def dex_community_takeovers_latest():
    return cached_get("/community-takeovers/latest/v1", ttl_seconds=60)

def dex_ads_latest():
    return cached_get("/ads/latest/v1", ttl_seconds=60)

def dex_token_boosts_latest():
    return cached_get("/token-boosts/latest/v1", ttl_seconds=60)

def dex_token_boosts_top():
    return cached_get("/token-boosts/top/v1", ttl_seconds=60)

def dex_orders(chain_id: str, token_address: str):
    return cached_get(f"/orders/v1/{chain_id}/{token_address}", ttl_seconds=30)

def dex_pair(chain_id: str, pair_id: str):
    return cached_get(f"/latest/dex/pairs/{chain_id}/{pair_id}", ttl_seconds=30)

def dex_search(q: str):
    return cached_get("/latest/dex/search", params={"q": q}, ttl_seconds=15)

def dex_token_pairs(chain_id: str, token_address: str):
    return cached_get(f"/token-pairs/v1/{chain_id}/{token_address}", ttl_seconds=30)

def dex_tokens(chain_id: str, token_addresses: str):
    return cached_get(f"/tokens/v1/{chain_id}/{token_addresses}", ttl_seconds=30)
