# src/routes/intel.py
from flask import Blueprint, jsonify
from src.services.coinmarketcap import get_cmc_listings
from src.services.cryptocompare import get_crypto_compare
from src.services.discord import get_discord_data
from src.services.telegram import get_telegram_data
from src.services.twitterRapid import get_twitterRapid_likes
from src.services.solana import get_solana_trending

intel_bp = Blueprint("intel", __name__)

# --------------------------------------------------------------------
#  /intel/summary and /api/intel/summary
# --------------------------------------------------------------------
@intel_bp.route("/summary", methods=["GET"])
def intel_summary():
    """
    Lightweight snapshot combining core sources:
    CoinMarketCap + CryptoCompare + Solana trending + Twitter activity
    """
    try:
        cmc = get_cmc_listings() or []
        cc = get_crypto_compare() or {}
        solana = get_solana_trending() or []
        twitter = get_twitterRapid_likes(pid="mirrorx_trending", count=10) or []

        summary = {
            "updated": "now",
            "marketSnapshot": [
                {
                    "symbol": t.get("symbol"),
                    "name": t.get("name"),
                    "price": t.get("quote", {}).get("USD", {}).get("price"),
                    "volume24h": t.get("quote", {}).get("USD", {}).get("volume_24h"),
                    "change24h": cc.get(t.get("symbol"), {}).get("change24h", 0)
                }
                for t in cmc[:15]
            ],
            "solanaTrending": solana[:10],
            "social": {
                "topTwitterMentions": twitter
            }
        }
        return jsonify(summary)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --------------------------------------------------------------------
#  /intel/full and /api/intel/full
# --------------------------------------------------------------------
@intel_bp.route("/full", methods=["GET"])
def intel_full():
    """
    Deep dataset merging all social + market intelligence streams
    """
    try:
        cmc = get_cmc_listings() or []
        cc = get_crypto_compare() or {}
        solana = get_solana_trending() or []
        twitter = get_twitterRapid_likes(pid="mirrorx_trending", count=25) or []
        discord = get_discord_data() or []
        telegram = get_telegram_data() or []

        full = {
            "updated": "now",
            "market": {
                "solana": solana,
                "coinmarketcap": cmc,
                "compare": cc
            },
            "social": {
                "twitter": twitter,
                "discord": discord,
                "telegram": telegram
            }
        }
        return jsonify(full)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
