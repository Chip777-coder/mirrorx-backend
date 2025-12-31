# src/services/dexscreener.py
import requests

def get_dexscreener():
    """
    Fetch live DEX market pairs from DexScreener.
    You can filter by chain or token if needed.
    """
    # Correct endpoint for all pairs across major DEXes
    url = "https://api.dexscreener.com/latest/dex/pairs"

    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()

        # DexScreener returns a JSON with a "pairs" list
        if isinstance(data, dict) and "pairs" in data:
            return data["pairs"]

        return data
    except Exception as e:
        print("DexScreener fetch error:", e)
        return []
