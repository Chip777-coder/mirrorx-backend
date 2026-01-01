# src/routes/signals.py
"""
MirrorX Alpha Signals Route
Aggregates on-chain, market, and social data into ranked alpha signals.
"""

from flask import Blueprint, jsonify
import requests
import math

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

    # Fetch underlying MirrorX streams
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

        # Base scoring formula: liquidity + momentum + sentiment blend
        alpha_score = (
            math.log1p(liquidity / 1000) * 0.4 +
            math.log1p(volume_24h / 1000) * 0.3 +
            (price_change / 10) * 0.2 +
            social_boost * 0.1
        )

        signals.append({
            "symbol": symbol,
            "alpha_score": round(alpha_score, 3),
            "liquidity_usd": liquidity,
            "volume_24h": volume_24h,
            "price_change_24h": price_change,
            "social_boost": social_boost
        })

    # Sort signals by strength
    ranked = sorted(signals, key=lambda x: x["alpha_score"], reverse=True)[:10]

    return jsonify({
        "system": "MirrorX Alpha Signal Engine",
        "status": "operational",
        "total_tokens_scanned": len(signals),
        "top_signals": ranked
    })
