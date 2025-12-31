# src/services/dexscreener.py
import requests

def get_dexscreener():
    """
    Fetch live DEX Screener pairs safely.
    Automatically supports the current /latest/dex/pairs endpoint.
    Returns the full JSON structure or [] if failed.
    """
    url = "https://api.dexscreener.com/latest/dex/pairs"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        # Normalize the structure so the rest of the code never breaks
        if isinstance(data, dict) and "pairs" in data:
            return data["pairs"]
        return data
    except Exception as e:
        print("DexScreener fetch error:", e)
        return []
