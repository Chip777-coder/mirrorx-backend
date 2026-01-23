# src/services/alpha_detector.py
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

DEX_BASE = "https://api.dexscreener.com"
DEX_TOKEN_PAIRS = f"{DEX_BASE}/latest/dex/tokens/"

# ----------------------------
# Thresholds
# ----------------------------
MIN_LIQ_USD = float(os.getenv("ALPHA_MIN_LIQ_USD", "30000"))
MIN_VOL_1H = float(os.getenv("ALPHA_MIN_VOL_1H", "150000"))
MIN_VOL_24H = float(os.getenv("ALPHA_MIN_VOL_24H", "750000"))

MOONSHOT_ENABLE = os.getenv("ALPHA_MOONSHOT_ENABLE", "1") == "1"
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


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def _sleep_jitter(base: float):
    time.sleep(max(0.0, base + random.uniform(-0.03, 0.06)))


def _get_json_with_backoff(url: str):
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


def fetch_pairs_by_address(token_address: str):
    data = _get_json_with_backoff(f"{DEX_TOKEN_PAIRS}{token_address}")
    return data.get("pairs", []) if isinstance(data, dict) else []


def _best_pair_combo(pairs):
    if not pairs:
        return {}

    def score(p):
        liq = _safe_float((p.get("liquidity") or {}).get("usd"))
        v1 = _safe_float((p.get("volume") or {}).get("h1"))
        ch5 = _safe_float((p.get("priceChange") or {}).get("m5"))
        ch1 = _safe_float((p.get("priceChange") or {}).get("h1"))

        s = ch5 * 1.45 + ch1 * 0.85 + (liq / 20000) + (v1 / 50000)

        if liq < 4000 and (ch5 > 80 or ch1 > 200):
            s *= 0.25
        return s

    return sorted(pairs, key=score, reverse=True)[0]


# =================================================
# Alpha Analysis
# =================================================

def analyze_pair(pair):
    try:
        base = pair.get("baseToken") or {}

        liquidity = _safe_float((pair.get("liquidity") or {}).get("usd"))
        vol_1h = _safe_float((pair.get("volume") or {}).get("h1"))
        vol_24h = _safe_float((pair.get("volume") or {}).get("h24"))

        ch_m5 = _safe_float((pair.get("priceChange") or {}).get("m5"))
        ch_1h = _safe_float((pair.get("priceChange") or {}).get("h1"))
        ch_24h = _safe_float((pair.get("priceChange") or {}).get("h24"))

        # ---------- Acceleration Tier ----------
        if ch_m5 > 300 and vol_1h > 150_000:
            tier = "parabolic"
        elif ch_m5 > 120 or ch_1h > 250:
            tier = "moonshot"
        elif ch_m5 > 40 or ch_1h > 80:
            tier = "standard"
        else:
            tier = "watch"

        # ---------- Hard filters ----------
        if liquidity < MIN_LIQ_USD:
            return None

        if vol_1h < MIN_VOL_1H and vol_24h < MIN_VOL_24H:
            return None

        if max(ch_m5, ch_1h, ch_24h) < MIN_MOVE_ANY:
            return None

        return {
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
            "gate": tier,
            "acceleration": tier,
        }

    except Exception as e:
        print("❌ analyze_pair failed:", e)
        return None


# =================================================
# Alert Formatting
# =================================================

def format_alert(token: dict) -> str:
    return (
        f"🚨 *MirrorX Alpha Detected*\n\n"
        f"🪙 {token['symbol']}\n"
        f"🔑 Mint: `{token['mint']}`\n"
        f"💧 Liquidity: ${int(token['liquidity']):,}\n"
        f"📊 Vol 1H: ${int(token['volume_1h']):,}\n"
        f"📈 5m: {token['change_m5']:.2f}%\n"
        f"📈 1H: {token['change_1h']:.2f}%\n"
        f"📈 24H: {token['change_24h']:.2f}%\n\n"
        f"⚡ Tier: {token['gate'].upper()}\n"
        f"🔗 {token['url']}"
    )


# =================================================
# Detection Loop
# =================================================

def detect_alpha_tokens():
    candidates = get_top_candidates(limit=RADAR_LIMIT) or []
    found = []

    for c in candidates:
        addr = c.get("address")
        if not addr:
            continue

        pairs = fetch_pairs_by_address(addr)
        best = _best_pair_combo(pairs)
        if not best:
            continue

        # Snapshot (pre-gate)
        try:
            base = best.get("baseToken") or {}
            record_snapshot("alpha_pre_gate", {
                "address": base.get("address"),
                "symbol": base.get("symbol"),
                "priceUsd": _safe_float(best.get("priceUsd")),
                "liquidityUsd": _safe_float((best.get("liquidity") or {}).get("usd")),
                "volumeH1": _safe_float((best.get("volume") or {}).get("h1")),
                "volumeH24": _safe_float((best.get("volume") or {}).get("h24")),
                "changeM5": _safe_float((best.get("priceChange") or {}).get("m5")),
                "changeH1": _safe_float((best.get("priceChange") or {}).get("h1")),
                "changeH24": _safe_float((best.get("priceChange") or {}).get("h24")),
                "url": best.get("url"),
                "ts": _now_iso(),
                "stage": "pre_gate",
            })
        except Exception:
            pass

        token = analyze_pair(best)
        if not token:
            continue

        record_snapshot("alpha_detector", {
            "address": token["address"],
            "symbol": token["symbol"],
            "priceUsd": token["price"],
            "liquidityUsd": token["liquidity"],
            "volumeH1": token["volume_1h"],
            "volumeH24": token["volume_24h"],
            "changeM5": token["change_m5"],
            "changeH1": token["change_1h"],
            "changeH24": token["change_24h"],
            "gate": token["gate"],
            "ts": _now_iso(),
        })

        found.append(token)
        _sleep_jitter(DEX_FETCH_PAUSE_SECONDS)

    return sorted(found, key=lambda t: t["change_1h"], reverse=True)


def push_alpha_alerts():
    detected = detect_alpha_tokens()
    if not detected:
        return

    for token in detected[:MAX_ALERTS]:
        strength = _safe_float(token.get("change_1h"), 0)

        if not can_alert(token.get("address"), strength):
            continue

        msg = format_alert(token)

        try:
            add_alert("alpha_detector", {
                "address": token["address"],
                "symbol": token["symbol"],
                "message": msg,
            })
        except Exception:
            pass

        send_telegram_message(msg)


if __name__ == "__main__":
    push_alpha_alerts()
