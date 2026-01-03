# src/services/cryptocompare.py
import os
import time
import requests

# Cache (per worker)
_CC_CACHE = {"ts": 0.0, "data": None}
_CC_TTL = int(os.getenv("CC_TTL_SECONDS", "120"))  # default 120s


def get_crypto_compare():
    """
    Returns mapping:
      { "SYMBOL": { "change24h": float } }

    Uses CC_API_KEY in env (optional depending on CryptoCompare limits).
    Adds short TTL cache to reduce API usage.
    """
    now = time.time()
    if _CC_CACHE["data"] is not None and (now - _CC_CACHE["ts"]) < _CC_TTL:
        return _CC_CACHE["data"]

    api_key = os.getenv("CC_API_KEY", "")
    url = f"https://min-api.cryptocompare.com/data/top/totalvolfull?limit=50&tsym=USD"
    if api_key:
        url += f"&api_key={api_key}"

    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json().get("Data", []) or []

        mapping = {}
        for item in data:
            symbol = item.get("CoinInfo", {}).get("Name")
            if symbol:
                raw = item.get("RAW", {}).get("USD", {}) or {}
                mapping[symbol] = {"change24h": raw.get("CHANGE24HOUR", 0)}

        _CC_CACHE["ts"] = time.time()
        _CC_CACHE["data"] = mapping
        return mapping

    except Exception as e:
        print("CryptoCompare fetch error:", e)
        return {}
