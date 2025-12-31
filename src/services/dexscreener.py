# src/services/dexscreener.py
import requests

DEX_BASE = "https://api.dexscreener.com"

def fetch_pair_search(query: str):
    """
    Search DexScreener for pairs matching a symbol or pair string.
    E.g. "SOL/USDC", "ETH", "BTC".
    """
    try:
        url = f"{DEX_BASE}/latest/dex/search"
        params = {"q": query}
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        # DexScreener returns "pairs" array on search
        return data.get("pairs", [])
    except Exception as e:
        print("DexScreener search fetch error:", e)
        return []

def fetch_token_profiles():
    """
    Get token profiles (broad feed with price, volume, liquidity, etc.).
    This returns global data useful for overview grids.
    """
    try:
        url = f"{DEX_BASE}/token-profiles/latest/v1"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        # DexScreener token profiles response includes list of profiles
        return data if isinstance(data, list) else []
    except Exception as e:
        print("DexScreener token profiles fetch error:", e)
        return []
