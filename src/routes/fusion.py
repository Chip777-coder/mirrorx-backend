# src/routes/fusion.py
"""
MirrorX Fusion Stream
Unifies CoinMarketCap, CryptoCompare, and DexScreener data
into standardized metrics for downstream intelligence layers.
"""

from flask import Blueprint, jsonify
from src.services.coinmarketcap import get_cmc_listings
from src.services.cryptocompare import get_crypto_compare
from src.services.dexscreener import get_dexscreener

fusion_bp = Blueprint("fusion", __name__)

@fusion_bp.route("/fusion/market-intel", methods=["GET"])
def fusion_market_intel():
    """Return unified, normalized token intelligence snapshot."""
    cmc_data = get_cmc_listings()
    cc_data = get_crypto_compare()
    dex_data = get_dexscreener()

    unified = []
    for t in cmc_data:
        symbol = t.get("symbol")
        cc = cc_data.get(symbol, {})
        dex = next((d for d in dex_data if d.get("symbol") == symbol), {})

        # normalize field names
        liquidity_usd = (
            dex.get("liquidity", {}).get("usd")
            if dex and dex.get("liquidity")
            else None
        )
        volume_24h = (
            t.get("quote", {}).get("USD", {}).get("volume_24h")
            or cc.get("volume24h")
            or None
        )
        price_change_24h = (
            cc.get("change24h")
            or t.get("quote", {}).get("USD", {}).get("percent_change_24h")
            or 0
        )

        unified.append(
            {
                "symbol": symbol,
                "name": t.get("name"),
                "price": t.get("quote", {}).get("USD", {}).get("price"),
                "liquidity_usd": float(liquidity_usd or 0),
                "volume_24h": float(volume_24h or 0),
                "price_change_24h": float(price_change_24h or 0),
            }
        )

    return jsonify({"updated": "now", "data": unified})
