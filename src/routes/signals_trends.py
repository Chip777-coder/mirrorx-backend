# src/routes/signals_trends.py
"""
MirrorX Alpha Trend Engine
Analyzes historical alpha signal snapshots to identify emerging and fading tokens.
"""

from flask import Blueprint, jsonify
from pathlib import Path
import json
from datetime import datetime, timezone

signals_trends_bp = Blueprint("signals_trends_bp", __name__)

# Path to the signal history data
HISTORY_FILE = Path(__file__).resolve().parent.parent / "data" / "signals" / "alpha_signals_history.json"


def _load_history():
    """Load alpha signal history safely."""
    if not HISTORY_FILE.exists():
        return {"records": []}
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"records": []}


def _normalize_symbol(symbol):
    return symbol.lower().strip() if symbol else None


# ✅ FIXED: blueprint is mounted at /api, so define relative path here
# Final URL becomes: /api/signals/trends
@signals_trends_bp.route("/signals/trends", methods=["GET"])
def get_signal_trends():
    """
    Compare recent alpha signal history snapshots and calculate per-token trend changes.
    Returns top 5 emerging and fading tokens based on momentum slope.
    """
    history = _load_history().get("records", [])
    if len(history) < 2:
        return jsonify({
            "system": "MirrorX Alpha Trend Engine",
            "status": "insufficient_history",
            "message": "Need at least 2 snapshots to calculate trends.",
            "emerging": [],
            "fading": []
        })

    # Build score history per token
    token_scores = {}
    for snapshot in history[:10]:  # last 10 snapshots max
        data = snapshot.get("data", {})
        top = data.get("top_signals", [])
        for t in top:
            sym = _normalize_symbol(t.get("symbol"))
            if not sym:
                continue
            token_scores.setdefault(sym, []).append(t.get("alpha_score", 0))

    # Compute trend deltas (difference between most recent and oldest in window)
    trends = []
    for sym, scores in token_scores.items():
        if len(scores) < 2:
            continue

        # Note: history ordering depends on how you append snapshots.
        # This keeps your original behavior but in a clean form.
        change = scores[0] - scores[-1]
        momentum = "rising" if change > 0 else "falling" if change < 0 else "flat"
        trend_pct = (change / (abs(scores[-1]) + 0.001)) * 100

        trends.append({
            "symbol": sym.upper(),
            "change": round(change, 3),
            "momentum": momentum,
            "trend_pct": f"{round(trend_pct, 2)}%"
        })

    emerging = sorted([t for t in trends if t["change"] > 0], key=lambda x: x["change"], reverse=True)[:5]
    fading = sorted([t for t in trends if t["change"] < 0], key=lambda x: x["change"])[:5]

    result = {
        "system": "MirrorX Alpha Trend Engine",
        "status": "operational",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "records_analyzed": len(history),
        "emerging": emerging,
        "fading": fading
    }

    # ✅ Optional: Auto Telegram Trend Broadcast
    try:
        from src.alerts.telegram_bot import send_trend_alert
        send_trend_alert(result)
    except Exception as e:
        print("Trend Telegram broadcast skipped or failed:", e)

    return jsonify(result)
