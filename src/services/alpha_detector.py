from __future__ import annotations

import os
import time
import random
import math
import requests
from datetime import datetime, timezone

from src.services.telegram_alerts import send_telegram_message
from src.services.dex_radar import get_top_candidates
from src.services.movers_store import record_snapshot
from src.services.alerts_store import can_alert
from src.services.market_intelligence import (
    apply_confidence_decay,
    detect_market_regime,
    adjust_confidence_by_regime
)
try:
    from src.services.alerts_store import add_alert
except Exception:
    def add_alert(_source: str, _payload: dict):
        return


# ============================================================
# CONFIG
# ============================================================

DEX_BASE = "https://api.dexscreener.com"
DEX_TOKEN_PAIRS = f"{DEX_BASE}/latest/dex/tokens/"

MIN_LIQ_USD = float(os.getenv("ALPHA_MIN_LIQ_USD", "30000"))
MIN_VOL_1H = float(os.getenv("ALPHA_MIN_VOL_1H", "150000"))
MIN_VOL_24H = float(os.getenv("ALPHA_MIN_VOL_24H", "750000"))

MOONSHOT_MIN_LIQ = 8000
MOONSHOT_MIN_VOL = 25000
MOONSHOT_CH_M5 = 80
MOONSHOT_CH_1H = 250

RADAR_LIMIT = int(os.getenv("ALPHA_RADAR_LIMIT", "60"))
MAX_ALERTS = int(os.getenv("ALPHA_MAX_ALERTS", "5"))

DEX_TIMEOUT = 12
DEX_BACKOFF = 2.2
DEX_RETRIES = 2

# ============================================================
# HELPERS
# ============================================================

def _now():
    return datetime.now(timezone.utc).isoformat()

def _safe(x, d=0.0):
    try:
        return float(x)
    except:
        return d

def _sleep():
    time.sleep(random.uniform(0.05, 0.12))

def _fetch(url):
    for i in range(DEX_RETRIES + 1):
        try:
            r = requests.get(url, timeout=DEX_TIMEOUT)
            if r.status_code == 429:
                time.sleep(DEX_BACKOFF * (i + 1))
                continue
            r.raise_for_status()
            return r.json()
        except:
            time.sleep(0.2)
    return None

# ============================================================
# PAIR SELECTION
# ============================================================

def fetch_pairs(address):
    data = _fetch(f"{DEX_TOKEN_PAIRS}{address}")
    return data.get("pairs", []) if data else []

def best_pair(pairs):
    def score(p):
        liq = _safe(p.get("liquidity", {}).get("usd"))
        v1 = _safe(p.get("volume", {}).get("h1"))
        m5 = _safe(p.get("priceChange", {}).get("m5"))
        h1 = _safe(p.get("priceChange", {}).get("h1"))
        return m5 * 1.4 + h1 * 0.9 + (liq / 20000) + (v1 / 50000)

    return sorted(pairs, key=score, reverse=True)[0] if pairs else None

# ============================================================
# CORE ANALYSIS
# ============================================================

def analyze_pair(pair):
    base = pair.get("baseToken") or {}

    liq = _safe(pair.get("liquidity", {}).get("usd"))
    v1 = _safe(pair.get("volume", {}).get("h1"))
    v24 = _safe(pair.get("volume", {}).get("h24"))

    m5 = _safe(pair.get("priceChange", {}).get("m5"))
    h1 = _safe(pair.get("priceChange", {}).get("h1"))
    h24 = _safe(pair.get("priceChange", {}).get("h24"))

    # --- Tier Logic ---
    if m5 > 300 and v1 > 150_000:
        tier = "rocket"
    elif m5 > 120 or h1 > 250:
        tier = "moonshot"
    elif m5 > 40 or h1 > 80:
        tier = "momentum"
    else:
        tier = "watch"

    if liq < MIN_LIQ_USD:
        return None
    if v1 < MIN_VOL_1H and v24 < MIN_VOL_24H:
        return None
    if max(m5, h1, h24) < 25:
        return None

    # Confidence Score
    confidence = min(
        100,
        (m5 * 0.4) +
        (h1 * 0.3) +
        (v1 / 5000) +
        (liq / 25000)
    )

    return {
        "symbol": base.get("symbol"),
        "mint": base.get("address"),
        "price": _safe(pair.get("priceUsd")),
        "liquidity": liq,
        "volume_1h": v1,
        "volume_24h": v24,
        "change_m5": m5,
        "change_1h": h1,
        "change_24h": h24,
        "tier": tier,
        "confidence": round(confidence, 2),
        "url": pair.get("url"),
    }

# ============================================================
# ALERT FORMAT
# ============================================================

def format_alert(t):
    return (
        f"🚨 *MirrorX Alert*\n\n"
        f"🪙 {t['symbol']}\n"
        f"🔑 Mint: {t['mint']}\n"
        f"🧠 Market Regime: {regime.upper()}\n"
        f"📊 Confidence: {token['confidence']:.2f}/100\n"
        f"⚡ Tier: {t['tier'].upper()}\n\n"
        f"💧 Liquidity: ${int(t['liquidity']):,}\n"
        f"📈 5m: {t['change_m5']:.2f}%\n"
        f"📈 1h: {t['change_1h']:.2f}%\n"
        f"📈 24h: {t['change_24h']:.2f}%\n\n"
        f"🔗 {t['url']}"
    )

# ============================================================
# MAIN LOOP
# ============================================================

def detect_alpha_tokens():
    found = []
    candidates = get_top_candidates(limit=RADAR_LIMIT)

    for c in candidates:
        pairs = fetch_pairs(c.get("address"))
        best = best_pair(pairs)
        if not best:
            continue

        token = analyze_pair(best)
        if not token:
            continue

        record_snapshot("alpha_detector", {
            **token,
            "ts": _now()
        })

        found.append(token)
        _sleep()

    return sorted(found, key=lambda x: x["confidence"], reverse=True)

# ============================================================
# DISPATCH
# ============================================================
# Determine current market regime
regime = detect_market_regime(detected)

# Apply confidence decay + regime adjustment
token["confidence"] = apply_confidence_decay(
    token["confidence"],
    token.get("ts", "")
)

token["confidence"] = adjust_confidence_by_regime(
    token["confidence"],
    regime
)
def push_alpha_alerts():
    tokens = detect_alpha_tokens()
    if not tokens:
        return

    for t in tokens[:MAX_ALERTS]:
        if not can_alert(t["mint"], t["confidence"]):
            continue

        msg = format_alert(t)

        try:
            add_alert("alpha_detector", {
                "mint": t["mint"],
                "symbol": t["symbol"],
                "confidence": t["confidence"],
                "tier": t["tier"]
            })
        except:
            pass

        send_telegram_message(msg)

if __name__ == "__main__":
    push_alpha_alerts()
