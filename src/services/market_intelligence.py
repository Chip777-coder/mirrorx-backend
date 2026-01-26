# src/services/market_intelligence.py

from datetime import datetime, timezone
import math

# ===============================
# CONFIDENCE DECAY ENGINE
# ===============================

def apply_confidence_decay(confidence: float, created_ts: str) -> float:
    """
    Applies exponential decay to confidence over time.
    Older signals lose confidence automatically.
    """

    try:
        created = datetime.fromisoformat(created_ts)
        now = datetime.now(timezone.utc)
        minutes_passed = (now - created).total_seconds() / 60

        # Half-life: ~45 minutes
        decay_rate = 0.015

        decayed = confidence * math.exp(-decay_rate * minutes_passed)
        return round(max(decayed, 0), 2)

    except Exception:
        return confidence


# ===============================
# MARKET REGIME DETECTION
# ===============================

def detect_market_regime(recent_signals: list[dict]) -> str:
    """
    Determines current market regime based on recent activity.
    """

    if not recent_signals:
        return "unknown"

    avg_move = sum(s.get("change_1h", 0) for s in recent_signals) / len(recent_signals)
    avg_vol = sum(s.get("volume_1h", 0) for s in recent_signals) / len(recent_signals)

    if avg_move < 5 and avg_vol < 100_000:
        return "dead"

    if avg_move < 20:
        return "choppy"

    if avg_move < 60:
        return "momentum"

    return "mania"


# ===============================
# CONFIDENCE NORMALIZER
# ===============================

def adjust_confidence_by_regime(confidence: float, regime: str) -> float:
    """
    Adjust confidence based on market regime.
    """

    if regime == "dead":
        return confidence * 0.5
    if regime == "choppy":
        return confidence * 0.75
    if regime == "momentum":
        return confidence * 1.0
    if regime == "mania":
        return confidence * 1.15

    return confidence
