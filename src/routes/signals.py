# src/routes/signals.py
"""
MirrorX Alpha Signals Route (v2)
Aggregates on-chain, market, and social data into ranked alpha signals.
Now includes caching, sentiment enrichment, and Telegram broadcast support.
"""

from flask import Blueprint, jsonify
import requests
import math

# ✅ new imports for caching, sentiment, and Telegram alerts
from src.services.cache import get_cache, set_cache
from src.services.sentiment import fetch_sentiment_scores
from src.alerts.telegram_bot import send_alpha_alert

signals_bp = Blueprint("signals_bp", __name__)

BASE_URL = "https://mirrorx-backend.onrender.com"

def safe_get(endpoint, fallback=None):
    """Helper for safe API requests"""
    try:
        res = requests.get(f"{BASE_URL}{endpoint}", timeout=8)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return fallback or {}

@signals_bp.route("/signals/alpha", methods=["GET"])
def get_alpha_signals():
    """
    Combine liquidity, social, and sentiment data into alpha rankings.
    Returns the top emerging tokens gaining traction across data layers.
    """

    # ✅ Step 3: Try to serve from cache first
    cached = get_cache("alpha_signals")
    if cached:
        return jsonify(cached)

    # Fetch underlying MirrorX data sources
    fusion_data = safe_get("/api/fusion/market-intel", {}).get("data", [])
    intel_summary = safe_get("/intel/summary", {})
    twitter_likes = safe_get("/twitterRapid/likes?pid=mirrorx_demo_post", {})

    # Ensure we have fusion data (core metrics)
    if not fusion_data:
        return jsonify({
            "error": "Fusion data unavailable",
            "signals": [],
            "status": "degraded"
        }), 200

    # ✅ Sentiment enrichment
    sentiment_scores = fetch_sentiment_scores([t.get("symbol") for t in fusion_data[:50]])

    signals = []
    for token in fusion_data[:50]:  # limit to top 50 for performance
        symbol = token.get("symbol") or token.get("name")
        if not symbol:
            continue

        liquidity = float(token.get("liquidity_usd", 0))
        volume_24h = float(token.get("volume_24h", 0))
        price_change = float(token.get("price_change_24h", 0))
        social_boost = 1.0

        # Optionally merge in social signals if available
        if intel_summary and "social_scores" in intel_summary:
            social_boost = intel_summary["social_scores"].get(symbol.lower(), 1.0)

        # Merge in sentiment multiplier
        sentiment = sentiment_scores.get(symbol.lower(), 1.0)

        # Base scoring formula: liquidity + momentum + sentiment blend
        alpha_score = (
            math.log1p(liquidity / 1000) * 0.4 +
            math.log1p(volume_24h / 1000) * 0.3 +
            (price_change / 10) * 0.2 +
            (social_boost * sentiment) * 0.1
        )

        signals.append({
            "symbol": symbol,
            "alpha_score": round(alpha_score, 3),
            "liquidity_usd": liquidity,
            "volume_24h": volume_24h,
            "price_change_24h": price_change,
            "social_boost": social_boost,
            "sentiment": sentiment
        })

    # Sort signals by strength
    ranked = sorted(signals, key=lambda x: x["alpha_score"], reverse=True)[:10]

    # ✅ Step 3: Cache result
    result = {
        "system": "MirrorX Alpha Signal Engine v2",
        "status": "operational",
        "total_tokens_scanned": len(signals),
        "top_signals": ranked
    }
    set_cache("alpha_signals", result)

    # ✅ Step 7: Telegram broadcast (only if configured)
    try:
        send_alpha_alert(ranked)
    except Exception as e:
        print("Telegram broadcast skipped or failed:", e)

    return jsonify(result)
