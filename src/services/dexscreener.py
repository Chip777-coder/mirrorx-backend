# src/services/dexscreener.py
import requests

def get_dexscreener(chain_id: str = "solana"):
    """
    Fetch live pair + liquidity data from DexScreener.
    Uses the current /token-pairs/v1/{chainId}/{tokenAddress} structure,
    but defaults to showing the latest global pairs feed for the chain.
    """
    url = f"https://api.dexscreener.com/latest/dex/pairs/{chain_id}"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        # Normalize to always return a list of pairs
        if isinstance(data, dict) and "pairs" in data:
            return data["pairs"]
        elif isinstance(data, list):
            return data
        return []
    except Exception as e:
        print("DexScreener fetch error:", e)
        return []
