# src/services/dexscreener.py
import requests

def get_dexscreener():
    """
    Fetches the latest community takeover data from DexScreener.
    This replaces the deprecated /latest/dex/pairs endpoint.
    Returns [] if the API call fails.
    """
    url = "https://api.dexscreener.com/community-takeovers/latest/v1"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        # DexScreener returns a list of token objects here
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        print("DexScreener fetch error:", e)
        return []
