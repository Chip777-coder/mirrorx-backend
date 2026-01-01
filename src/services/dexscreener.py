# src/services/dexscreener.py
import requests

DEX_BASE = "https://api.dexscreener.com"

def fetch_pair_search(query: str):
    """
    Search DexScreener pairs matching a symbol or pair string.
    Example: query='SOL/USDC' or 'ETH'
    """
    try:
        if not query:
            return []
        url = f"{DEX_BASE}/latest/dex/search"
        res = requests.get(url, params={"q": query}, timeout=10)
        res.raise_for_status()
        data = res.json()
        return data.get("pairs", [])
    except Exception as e:
        print("DexScreener search fetch error:", e)
        return []

def fetch_token_profiles():
    """
    Get the latest global token profiles with liquidity/price snapshot.
    This pulls from DexScreener's token profiles API.
    """
    try:
        url = f"{DEX_BASE}/token-profiles/latest/v1"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print("DexScreener token profiles fetch error:", e)
        return []
# Add at the bottom of src/services/dexscreener.py

def get_dexscreener(query: str = ""):
    """
    Legacy wrapper for backward compatibility.
    Uses fetch_pair_search if query provided, else fetch_token_profiles.
    """
    return fetch_pair_search(query) if query else fetch_token_profiles()
