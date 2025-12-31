from flask import Blueprint, jsonify
from src.services.coinmarketcap import get_cmc_listings
from src.services.cryptocompare import get_crypto_compare
from src.services.dexscreener import get_dexscreener

fusion_bp = Blueprint("fusion", __name__)

@fusion_bp.route("/fusion/market-intel", methods=["GET"])
def fusion_market_intel():
    cmc_data = get_cmc_listings()
    cc_data = get_crypto_compare()
    dex_data = get_dexscreener()
    unified = []
    for t in cmc_data:
        symbol = t.get("symbol")
        cc = cc_data.get(symbol, {})
        dex = next((d for d in dex_data if d.get("symbol") == symbol), {})
        unified.append({
            "symbol": symbol,
            "name": t.get("name"),
            "price": t.get("quote", {}).get("USD", {}).get("price"),
            "cmcVolume": t.get("quote", {}).get("USD", {}).get("volume_24h"),
            "ccChange24h": cc.get("change24h", 0),
            "dexLiquidity": dex.get("liquidity", {}).get("usd") if dex else None
        })
    return jsonify({"updated": "now", "data": unified})
