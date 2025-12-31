# src/services/dexscreener.py
import requests

DEX_BASE = "https://api.dexscreener.com"

def fetch_pair_search(query: str):
    """
    Search DexScreener pairs matching a symbol or pair string.
    Example: query="SOL/USDC" or "ETH"
    """
    try:
        url = f"{DEX_BASE}/latest/dex/search"
        params = {"q": query}
        res = requests.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        return data.get("pairs", [])
    except Exception as e:
        print("DexScreener search fetch error:", e)
        return []

def fetch_token_profiles():
    """
    Get the latest global token profiles with liquidity/price snapshot.
    """
    try:
        url = f"{DEX_BASE}/token-profiles/latest/v1"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        # DexScreener token profiles returns a list
        return data if isinstance(data, list) else []
    except Exception as e:
        print("DexScreener token profiles fetch error:", e)
        return []
