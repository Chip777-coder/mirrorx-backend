from __future__ import annotations

import os
import time
import random
import requests
from datetime import datetime, timezone

from src.services.telegram_alerts import send_telegram_message
from src.services.dex_radar import get_top_candidates
from src.services.movers_store import record_snapshot
from src.services.alerts_store import can_alert

try:
    from src.services.alerts_store import add_alert
except Exception:
    def add_alert(_source: str, _payload: dict):
        return


# ============================
# CONFIG
# ============================

DEX_BASE = "https://api.dexscreener.com"
DEX_TOKEN_PAIRS = f"{DEX_BASE}/latest/dex/tokens/"

MIN_LIQ_USD = float(os.getenv("ALPHA_MIN_LIQ_USD", "30000"))
MIN_VOL_1H = float(os.getenv("ALPHA_MIN_VOL_1H", "150000"))
MIN_VOL_24H = float(os.getenv("ALPHA_MIN_VOL_24H", "750000"))

MOONSHOT_MIN_LIQ_USD = float(os.getenv("ALPHA_MOONSHOT_MIN_LIQ_USD", "8000"))
MOONSHOT_MIN_VOL_1H = float(os.getenv("ALPHA_MOONSHOT_MIN_VOL_1H", "25000"))
MOONSHOT_MIN_VOL_24H = float(os.getenv("ALPHA_MOONSHOT_MIN_VOL_24H", "150000"))
MOONSHOT_CH_M5 = float(os.getenv("ALPHA_MOONSHOT_CH_M5", "80"))
MOONSHOT_CH_1H = float(os.getenv("ALPHA_MOONSHOT_CH_1H", "250"))

MIN_MOVE_ANY = float(os.getenv("ALPHA_MIN_MOVE_ANY", "25"))
RADAR_LIMIT = int(os.getenv("ALPHA_RADAR_LIMIT", "60"))
MAX_ALERTS = int(os.getenv("ALPHA_MAX_ALERTS", "5"))

DEX_HTTP_TIMEOUT = int(os.getenv("DEX_HTTP_TIMEOUT", "12"))
DEX_FETCH_PAUSE_SECONDS = float(os.getenv("ALPHA_DEX_FETCH_PAUSE_SECONDS", "0.08"))
DEX_429_BACKOFF_SECONDS = float(os.getenv("ALPHA_DEX_429_BACKOFF_SECONDS", "2.25"))
DEX_429_MAX_RETRIES = int(os.getenv("ALPHA_DEX_429_MAX_RETRIES", "2"))


# ============================
# UTILITIES
# ============================

def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def _sleep_jitter(base):
    time.sleep(max(0.0, base + random.uniform(-0.03, 0.06)))


def _get_json_with_backoff(url):
    for attempt in range(DEX_429_MAX_RETRIES + 1):
        try:
            r = requests.get(url, timeout=DEX_HTTP_TIMEOUT)
            if r.status_code == 429:
                _sleep_jitter(DEX_429_BACKOFF_SECONDS * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception:
            _sleep_jitter(0.2)
    return None


def fetch_pairs_by_address(token_address):
    data = _get_json_with_backoff(f"{DEX_TOKEN_PAIRS}{token_address}")
    return data.get("pairs", []) if isinstance(data, dict) else []


# ============================
# INTELLIGENCE LAYERS
# ============================

def compute_confidence(t):
    score = 0
    if t["volume_1h"] > 300_000:
        score += 25
    if t["liquidity"] > 100_000:
        score += 25
    if t["change_1h"] > 40:
        score += 25
    if t["change_m5"] > 15:
        score += 25
    return min(score, 100)


def classify_stage(t):
    if t["volume_1h"] < 50_000 and t["change_m5"] > 40:
        return "EARLY"
    if t["volume_1h"] < 300_000:
        return "MID"
    return "LATE"


def detect_reversal(t):
    if t["change_m5"] < 0 and t["change_1h"] > 60:
        return "Possible Reversal"
    if t["volume_1h"] < 20000:
        return "Weak Volume"
    return "OK"


def is_elite(t):
    return (
        t["confidence"] >= 80 and
        t["stage"] in ("EARLY", "MID") and
        t["volume_1h"] > 250_000
    )


def should_suppress(t):
    if t["confidence"] < 35:
        return True
    if t["stage"] == "LATE" and t["change_1h"] > 120:
        return True
    return False


def generate_reasoning(t):
    reasons = []
    if t["confidence"] > 80:
        reasons.append("Strong momentum + volume")
    if t["stage"] == "EARLY":
        reasons.append("Early-stage breakout")
    if t["reversal"] != "OK":
        reasons.append("Reversal risk detected")
    return " | ".join(reasons)


# ============================
# CORE ANALYSIS
# ============================

def analyze_pair(pair):
    try:
        base = pair.get("baseToken") or {}

        liquidity = _safe_float((pair.get("liquidity") or {}).get("usd"))
        vol_1h = _safe_float((pair.get("volume") or {}).get("h1"))
        vol_24h = _safe_float((pair.get("volume") or {}).get("h24"))

        ch_m5 = _safe_float((pair.get("priceChange") or {}).get("m5"))
        ch_1h = _safe_float((pair.get("priceChange") or {}).get("h1"))
        ch_24h = _safe_float((pair.get("priceChange") or {}).get("h24"))

        if liquidity < MIN_LIQ_USD:
            return None
        if vol_1h < MIN_VOL_1H and vol_24h < MIN_VOL_24H:
            return None
        if max(ch_m5, ch_1h, ch_24h) < MIN_MOVE_ANY:
            return None

        token = {
            "address": base.get("address"),
            "mint": base.get("address"),
            "symbol": base.get("symbol", "UNKNOWN"),
            "price": _safe_float(pair.get("priceUsd")),
            "liquidity": liquidity,
            "volume_1h": vol_1h,
            "volume_24h": vol_24h,
            "change_m5": ch_m5,
            "change_1h": ch_1h,
            "change_24h": ch_24h,
            "url": pair.get("url"),
        }

        token["confidence"] = compute_confidence(token)
        token["stage"] = classify_stage(token)
        token["reversal"] = detect_reversal(token)
        token["elite"] = is_elite(token)

        return token

    except Exception:
        return None


# ============================
# ALERT FORMAT
# ============================

def format_alert(t):
    return (
        f"🚨 *MirrorX Alpha Alert*\n\n"
        f"🪙 {t['symbol']}\n"
        f"🔑 Mint: {t['mint']}\n"
        f"💧 Liquidity: ${int(t['liquidity']):,}\n"
        f"📊 Vol 1H: ${int(t['volume_1h']):,}\n"
        f"📈 5m: {t['change_m5']:.2f}%\n"
        f"📈 1H: {t['change_1h']:.2f}%\n"
        f"📈 24H: {t['change_24h']:.2f}%\n\n"
        f"🧠 Confidence: {t['confidence']}/100\n"
        f"⏱ Stage: {t['stage']}\n"
        f"🔁 Risk: {t['reversal']}\n"
        f"🔥 Elite: {'YES' if t['elite'] else 'NO'}\n\n"
        f"🔗 {t['url']}"
    )


# ============================
# PIPELINE
# ============================

def detect_alpha_tokens():
    candidates = get_top_candidates(limit=RADAR_LIMIT) or []
    results = []

    for c in candidates:
        addr = c.get("address")
        if not addr:
            continue

        pairs = fetch_pairs_by_address(addr)
        if not pairs:
            continue

        best = sorted(pairs, key=lambda p: _safe_float((p.get("priceChange") or {}).get("h1")), reverse=True)[0]

        token = analyze_pair(best)
        if not token:
            continue

        if should_suppress(token):
            continue

        record_snapshot("alpha_detector", {
            **token,
            "ts": _now_iso()
        })

        results.append(token)
        _sleep_jitter(DEX_FETCH_PAUSE_SECONDS)

    return sorted(results, key=lambda t: t["confidence"], reverse=True)


def push_alpha_alerts():
    detected = detect_alpha_tokens()

    for token in detected[:MAX_ALERTS]:
        if not can_alert(token["address"], token["change_1h"]):
            continue

        msg = format_alert(token)

        try:
            add_alert("alpha_detector", {
                "address": token["address"],
                "symbol": token["symbol"],
                "confidence": token["confidence"],
                "stage": token["stage"],
                "elite": token["elite"],
                "message": msg,
            })
        except Exception:
            pass

        send_telegram_message(msg)


if __name__ == "__main__":
    push_alpha_alerts()
