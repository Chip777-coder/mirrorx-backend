# src/routes/fusion.py
from flask import Blueprint, jsonify, request
from src.services.coinmarketcap import get_cmc_listings
from src.services.cryptocompare import get_crypto_compare
from src.services.dexscreener import fetch_pair_search, fetch_token_profiles

fusion_bp = Blueprint("fusion", __name__)

@fusion_bp.route("/fusion/market-intel", methods=["GET"])
def fusion_market_intel():
    """
    Unified fusion endpoint combining CoinMarketCap, CryptoCompare, and DexScreener data.
    Supports ?search= query for Dex pair lookup and highlights meme-coin liquidity.
    """
    try:
        cmc_data = get_cmc_listings() or []
        cc_data = get_crypto_compare() or {}

        # Optional query param that triggers DexScreener pair search
        search_query = request.args.get("search", "").strip()

        # Decide which DexScreener source to use
        dex_data = fetch_pair_search(search_query) if search_query else fetch_token_profiles()
        unified = []

        for t in cmc_data:
            symbol = t.get("symbol")
            cc = cc_data.get(symbol, {})

            # match based on tokens found in pair search or profiles list
            matched = [
                d for d in dex_data
                if d.get("baseToken", {}).get("symbol") == symbol
                or d.get("quoteToken", {}).get("symbol") == symbol
            ]
            dex = matched[0] if matched else {}

            # Try to extract liquidity safely
            liquidity_usd = None
            if dex:
                liquidity_usd = (
                    dex.get("liquidity", {}).get("usd")
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
            })

        # ✅ Optional: Meme-coin highlight filter (BONK, WIF, MYRO, PEPE, etc.)
        meme_keywords = ["BONK", "WIF", "MYRO", "DOGE", "SHIB", "PEPE", "SAMO", "PENGU"]
        meme_coins = [u for u in unified if any(k in (u["symbol"] or "").upper() for k in meme_keywords)]

        return jsonify({
            "updated": "now",
            "totalTokens": len(unified),
            "highlightedMemeCoins": len(meme_coins),
            "data": unified,
            "memeCoins": meme_coins
        })
    except Exception as e:
        print("Fusion market intel error:", e)
        return jsonify({"error": str(e)}), 500
