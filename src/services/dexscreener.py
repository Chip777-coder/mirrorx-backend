# src/services/dexscreener.py
import requests

DEX_BASE = "https://api.dexscreener.com"


# ----------------------------
# Existing: search + profiles
# ----------------------------
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


# ----------------------------
# NEW: boosts / takeovers / ads
# ----------------------------
def fetch_token_boosts_latest():
    """DexScreener: /token-boosts/latest/v1"""
    try:
        url = f"{DEX_BASE}/token-boosts/latest/v1"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print("DexScreener token boosts latest fetch error:", e)
        return []


def fetch_token_boosts_top():
    """DexScreener: /token-boosts/top/v1"""
    try:
        url = f"{DEX_BASE}/token-boosts/top/v1"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print("DexScreener token boosts top fetch error:", e)
        return []


def fetch_community_takeovers_latest():
    """DexScreener: /community-takeovers/latest/v1"""
    try:
        url = f"{DEX_BASE}/community-takeovers/latest/v1"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print("DexScreener community takeovers fetch error:", e)
        return []


def fetch_ads_latest():
    """DexScreener: /ads/latest/v1"""
    try:
        url = f"{DEX_BASE}/ads/latest/v1"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        print("DexScreener ads fetch error:", e)
        return []


# Backward-compatible wrapper
def get_dexscreener(query: str = ""):
    """
    Legacy wrapper for backward compatibility.
    Uses fetch_pair_search if query provided, else fetch_token_profiles.
    """
    return fetch_pair_search(query) if query else fetch_token_profiles()
