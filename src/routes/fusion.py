# src/routes/fusion.py
import os
import time
from flask import Blueprint, jsonify, request
from src.services.coinmarketcap import get_cmc_listings
from src.services.cryptocompare import get_crypto_compare
from src.services.dexscreener import fetch_pair_search, fetch_token_profiles, CANONICAL_SOL_MINTS

fusion_bp = Blueprint("fusion", __name__)

# -------------------------------------------------------------------
# Simple in-memory cache (per worker)
# Set env var FUSION_TTL_SECONDS=60 (or 30) to control caching.
# -------------------------------------------------------------------
_FUSION_CACHE = {"ts": 0.0, "payload": None}
_FUSION_TTL = int(os.getenv("FUSION_TTL_SECONDS", "60"))


def _as_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def _liq_usd(pair: dict) -> float:
    liq = pair.get("liquidity") or {}
    return _as_float(liq.get("usd"), 0.0)


def _best_by_liquidity(pairs: list[dict]) -> dict:
    if not pairs:
        return {}
    return sorted(pairs, key=_liq_usd, reverse=True)[0]


@fusion_bp.route("/fusion/market-intel", methods=["GET"])
def fusion_market_intel():
    """
    Unifies CoinMarketCap, CryptoCompare, and DexScreener data streams
    into a single standardized market intelligence endpoint.

    Fixes:
      - Avoid symbol-only spoof matches by using canonical mint for known symbols (WEN etc.)
      - Choose best Dex pair by liquidity (not matched[0])

    Performance:
      - Adds a short TTL cache to reduce upstream API calls.
    """

    # Optional query param for searching specific pairs/tokens
    search_query = request.args.get("search", "").strip()

    # If user searches, skip cache (search should be fresh / specific)
    if search_query:
        dex_data = fetch_pair_search(search_query)  # returns [best] or []
        return jsonify({"updated": "now", "data": dex_data})

    # Serve cached payload if fresh
    now = time.time()
    if _FUSION_CACHE["payload"] is not None and (now - _FUSION_CACHE["ts"]) < _FUSION_TTL:
        return jsonify(_FUSION_CACHE["payload"])

    cmc_data = get_cmc_listings() or []
    cc_data = get_crypto_compare() or {}

    # Otherwise use token profiles (broad list) but DO NOT trust symbol-only for canonical tokens.
    dex_profiles = fetch_token_profiles() or []

    unified = []
    for t in cmc_data:
        symbol = (t.get("symbol") or "").upper()
        cc = cc_data.get(symbol, {})

        dex = {}

        # ✅ If symbol is in canonical registry (WEN etc.), fetch the canonical best pair directly.
        # This prevents spoof pools from token profiles / search collisions.
        if symbol in CANONICAL_SOL_MINTS:
            best = fetch_pair_search(symbol)  # filtered to canonical mint + best liquidity
            dex = best[0] if best else {}
        else:
            # Best-effort match from profiles if they happen to include pair-like objects.
            matched = []
            for d in dex_profiles:
                base = d.get("baseToken", {})
                quote = d.get("quoteToken", {})
                if (base.get("symbol") or "").upper() == symbol or (quote.get("symbol") or "").upper() == symbol:
                    matched.append(d)

            dex = _best_by_liquidity(matched)

        # Safely extract liquidity and normalize
        liquidity_usd = None
        dex_pair_address = None
        dex_chain = None
        dex_base_mint = None

        if dex:
            dex_chain = dex.get("chainId")
            dex_pair_address = dex.get("pairAddress")
            dex_base_mint = (dex.get("baseToken") or {}).get("address")

            liquidity_usd = (
                (dex.get("liquidity") or {}).get("usd")
                or dex.get("liquidityUSD")
                or dex.get("liquidity_usd")
            )

        unified.append({
            "symbol": symbol,
            "name": t.get("name"),
            "price": t.get("quote", {}).get("USD", {}).get("price"),
            "cmcVolume": t.get("quote", {}).get("USD", {}).get("volume_24h"),
            "ccChange24h": cc.get("change24h", 0),
            "dexLiquidity": liquidity_usd,

            # Debug fields (super helpful for verifying WEN mint correctness)
            "dexChain": dex_chain,
            "dexPairAddress": dex_pair_address,
            "dexBaseMint": dex_base_mint,
        })

    payload = {"updated": "now", "data": unified}

    # Store in cache
    _FUSION_CACHE["ts"] = time.time()
    _FUSION_CACHE["payload"] = payload

    return jsonify(payload)
