# src/services/coinmarketcap.py
import os
import time
import requests

CMC_URL = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"

# Cache (per worker)
_CMC_CACHE = {"ts": 0.0, "data": None}
_CMC_TTL = int(os.getenv("CMC_TTL_SECONDS", "60"))  # default 60s


def get_cmc_listings():
    """
    Fetch top listings from CoinMarketCap.
    Uses COINMARKETCAP_API_KEY in env.
    Adds short TTL cache to reduce API usage.
    """
    now = time.time()
    if _CMC_CACHE["data"] is not None and (now - _CMC_CACHE["ts"]) < _CMC_TTL:
        return _CMC_CACHE["data"]

    api_key = os.getenv("COINMARKETCAP_API_KEY") or os.getenv("CMC_API_KEY")
    if not api_key:
        print("CMC fetch error: missing COINMARKETCAP_API_KEY (or CMC_API_KEY)")
        return []

    headers = {"X-CMC_PRO_API_KEY": api_key}

    try:
        res = requests.get(CMC_URL, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json().get("data", []) or []
        _CMC_CACHE["ts"] = time.time()
        _CMC_CACHE["data"] = data
        return data
    except Exception as e:
        print("CMC fetch error:", e)
        return []
