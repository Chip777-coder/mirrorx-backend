# src/services/coinmarketcap.py
import os
import time
import requests

CMC_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"

# Cache TTL in seconds (default 6 hours)
CMC_TTL = int(os.getenv("CMC_CACHE_TTL_SECONDS", str(6 * 3600)))

# In-process cache (works per worker; good enough to slash usage)
_cache = {"ts": 0.0, "data": []}


def get_cmc_listings(force: bool = False):
    """
    Cached CoinMarketCap listings.
    - force=False (default): returns cached data if fresh
    - force=True: refreshes from CMC immediately

    This prevents credit burn from frequent polling.
    """
    now = time.time()
    if (not force) and _cache["data"] and (now - _cache["ts"] < CMC_TTL):
        return _cache["data"]

    api_key = os.getenv("COINMARKETCAP_API_KEY") or os.getenv("CMC_API_KEY")
    if not api_key:
        # No key → no fetch
        return _cache["data"] or []

    headers = {"X-CMC_PRO_API_KEY": api_key}
    params = {
        "start": 1,
        "limit": int(os.getenv("CMC_LIMIT", "100")),   # keep small
        "convert": "USD",
    }

    try:
        res = requests.get(CMC_URL, headers=headers, params=params, timeout=12)
        res.raise_for_status()
        data = res.json().get("data", []) or []
        _cache["ts"] = now
        _cache["data"] = data
        return data
    except Exception as e:
        print("CMC fetch error:", e)
        # Serve stale cache if available
        return _cache["data"] or []
