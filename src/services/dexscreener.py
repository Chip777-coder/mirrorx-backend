# src/services/dexscreener.py
import requests

DEX_BASE = "https://api.dexscreener.com"

# -------------------------------------------------------------------
# Canonical mint registry (Solana)
# Keep this small and explicit to avoid spoof/clones.
# -------------------------------------------------------------------
CANONICAL_SOL_MINTS = {
    "WEN": "WENWENvqqNya429ubCdR81ZmD69brwQaaBYY6p3LCpk",
    # Add more as you verify:
    # "BONK": "...",
    # "WIF": "...",
    # "JUP": "...",
}

DEFAULT_MIN_LIQUIDITY_USD = 10_000  # helps avoid tiny spoof pools


def _as_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def _filter_pairs(pairs, query: str, chain: str | None = "solana"):
    """
    Filter by:
      1) chainId (when provided by DexScreener)
      2) canonical mint (when query matches a known canonical symbol)
      3) minimum liquidity (to avoid tiny spoof pools)
    """
    pairs = pairs or []

    # 1) Chain filter (best effort)
    if chain:
        pairs = [p for p in pairs if (p.get("chainId") or "").lower() == chain.lower()]

    # 2) Canonical mint filter (symbol -> mint)
    mint = CANONICAL_SOL_MINTS.get((query or "").upper())
    if mint:
        pairs = [
            p for p in pairs
            if ((p.get("baseToken") or {}).get("address") == mint)
        ]

    return pairs


def _pick_best_pair(pairs, min_liquidity_usd: float = DEFAULT_MIN_LIQUIDITY_USD):
    """
    Choose the best candidate pair (deepest liquidity).
    Also drop pairs below min liquidity to avoid spoof pools.
    """
    if not pairs:
        return None

    def liq_usd(p):
        liq = p.get("liquidity") or {}
        return _as_float(liq.get("usd"), 0.0)

    # Drop tiny pools if possible (if everything is tiny, keep them so caller sees something)
    filtered = [p for p in pairs if liq_usd(p) >= float(min_liquidity_usd)]
    use = filtered if filtered else pairs

    use_sorted = sorted(use, key=liq_usd, reverse=True)
    return use_sorted[0] if use_sorted else None


def fetch_pair_search(query: str, chain: str | None = "solana", best_only: bool = True):
    """
    Search DexScreener pairs matching a symbol or pair string.
    Example: query='SOL/USDC' or 'ETH'

    Improvements:
      - Optional chain filter (defaults to solana)
      - Canonical mint filtering for known symbols (WEN etc.)
      - Best pair selection by liquidity to avoid spoof pools
    """
    try:
        if not query:
            return []
        url = f"{DEX_BASE}/latest/dex/search"
        res = requests.get(url, params={"q": query}, timeout=10)
        res.raise_for_status()
        data = res.json()
        pairs = data.get("pairs", []) or []

        pairs = _filter_pairs(pairs, query=query, chain=chain)

        if best_only:
            best = _pick_best_pair(pairs)
            return [best] if best else []
        return pairs

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


def get_dexscreener(query: str = ""):
    """
    Legacy wrapper for backward compatibility.
    Uses fetch_pair_search if query provided, else fetch_token_profiles.
    """
    return fetch_pair_search(query) if query else fetch_token_profiles()
