# src/services/dexscreener.py
import requests

DEX_BASE = "https://api.dexscreener.com"

# -------------------------------------------------------------------
# Canonical Solana Mint Registry (prevents spoof / duplicate symbols)
# Add more as you want.
# -------------------------------------------------------------------
CANONICAL_SOL_MINTS = {
    # WEN (example from Phantom)
    "WEN": "WENWENvqqNya429ubCdR81ZmD69brwQaaBYY6p3LCpk",

    # Optional examples (fill in only if you want strict pinning)
    # "BONK": "...",
    # "WIF": "...",
    # "JUP": "...",
}


def _as_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def _liq_usd(pair: dict) -> float:
    liq = pair.get("liquidity") or {}
    return _as_float(liq.get("usd"), 0.0)


def _best_by_liquidity(pairs: list[dict]) -> list[dict]:
    """Return [best_pair] or [] based on liquidity."""
    if not pairs:
        return []
    best = sorted(pairs, key=_liq_usd, reverse=True)[0]
    return [best] if best else []


# ----------------------------
# Search (pairs)
# ----------------------------
def fetch_pair_search(query: str):
    """
    Search DexScreener pairs matching a symbol or pair string.
    Example: query='SOL/USDC' or 'ETH'

    If query is a known canonical symbol (WEN etc.),
    filter results to that mint and return best-by-liquidity only.
    """
    try:
        if not query:
            return []

        url = f"{DEX_BASE}/latest/dex/search"
        res = requests.get(url, params={"q": query}, timeout=10)
        res.raise_for_status()
        data = res.json()
        pairs = data.get("pairs", []) or []

        # ✅ Canonical filter (prevents spoof symbols)
        sym = query.strip().upper()
        if sym in CANONICAL_SOL_MINTS:
            mint = CANONICAL_SOL_MINTS[sym]
            pairs = [
                p for p in pairs
                if (p.get("baseToken") or {}).get("address") == mint
            ]

            # Return best only (most liquid = most "real")
            return _best_by_liquidity(pairs)

        return pairs

    except Exception as e:
        print("DexScreener search fetch error:", e)
        return []


# ----------------------------
# Token profiles
# ----------------------------
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
