# src/routes/fusion.py
from flask import Blueprint, jsonify, request
from src.services.coinmarketcap import get_cmc_listings
from src.services.cryptocompare import get_crypto_compare
from src.services.dexscreener import fetch_pair_search, fetch_token_profiles

fusion_bp = Blueprint("fusion", __name__)

@fusion_bp.route("/fusion/market-intel", methods=["GET"])
def fusion_market_intel():
    cmc_data = get_cmc_listings()
    cc_data = get_crypto_compare()

    # Optional query param that triggers DexScreener pair search
    search_query = request.args.get("search", "").strip()

    # Decide which DexScreener source to use
    if search_query:
        dex_data = fetch_pair_search(search_query)
    else:
        dex_data = fetch_token_profiles()

    unified = []
    for t in cmc_data:
        symbol = t.get("symbol")
        cc = cc_data.get(symbol, {})

        # match based on tokens found in pair search or profiles list
        matched = []
        for d in dex_data:
            base = d.get("baseToken", {})
            quote = d.get("quoteToken", {})
            if base.get("symbol") == symbol or quote.get("symbol") == symbol:
                matched.append(d)

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

    return jsonify({"updated": "now", "data": unified})
