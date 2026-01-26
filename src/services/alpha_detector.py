# src/services/alpha_detector.py
from __future__ import annotations

import os
import time
import random
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from src.services.dex_radar import get_top_candidates
from src.services.movers_store import record_snapshot
from src.services.alerts_store import can_alert

from src.services.telegram_router import send_to_tier
from src.services.performance_tracker import record_signal
from src.services.wallet_intel import get_top_holders, whale_score_from_holders

# Optional alerts store persistence (safe no-op if missing)
try:
    from src.services.alerts_store import add_alert  # type: ignore
except Exception:
    def add_alert(_source: str, _payload: dict):
        return


# ============================================================
# CONFIG
# ============================================================

DEX_BASE = "https://api.dexscreener.com"
DEX_TOKEN_PAIRS = f"{DEX_BASE}/latest/dex/tokens/"

# Normal gate
MIN_LIQ_USD = float(os.getenv("ALPHA_MIN_LIQ_USD", "30000"))
MIN_VOL_1H = float(os.getenv("ALPHA_MIN_VOL_1H", "150000"))
MIN_VOL_24H = float(os.getenv("ALPHA_MIN_VOL_24H", "750000"))
MIN_MOVE_ANY = float(os.getenv("ALPHA_MIN_MOVE_ANY", "25"))

# Moonshot V1 (original Jan 6/7 behavior)
MOONSHOT_V1_ENABLE = os.getenv("ALPHA_MOONSHOT_V1_ENABLE", "1") == "1"
MOONSHOT_V1_MIN_LIQ_USD = float(os.getenv("ALPHA_MOONSHOT_V1_MIN_LIQ_USD", "8000"))
MOONSHOT_V1_MIN_VOL_1H = float(os.getenv("ALPHA_MOONSHOT_V1_MIN_VOL_1H", "25000"))
MOONSHOT_V1_MIN_VOL_24H = float(os.getenv("ALPHA_MOONSHOT_V1_MIN_VOL_24H", "150000"))
MOONSHOT_V1_CH_M5 = float(os.getenv("ALPHA_MOONSHOT_V1_CH_M5", "80"))
MOONSHOT_V1_CH_1H = float(os.getenv("ALPHA_MOONSHOT_V1_CH_1H", "250"))

# Moonshot V2 (newer stricter variation)
MOONSHOT_V2_ENABLE = os.getenv("ALPHA_MOONSHOT_V2_ENABLE", "1") == "1"
MOONSHOT_V2_MIN_LIQ_USD = float(os.getenv("ALPHA_MOONSHOT_V2_MIN_LIQ_USD", "12000"))
MOONSHOT_V2_MIN_VOL_1H = float(os.getenv("ALPHA_MOONSHOT_V2_MIN_VOL_1H", "40000"))
MOONSHOT_V2_CH_M5 = float(os.getenv("ALPHA_MOONSHOT_V2_CH_M5", "120"))
MOONSHOT_V2_CH_1H = float(os.getenv("ALPHA_MOONSHOT_V2_CH_1H", "300"))

# Scan + alerts
RADAR_LIMIT = int(os.getenv("ALPHA_RADAR_LIMIT", "60"))
MAX_ALERTS = int(os.getenv("ALPHA_MAX_ALERTS", "8"))  # ✅ more than 5

# Dex safety
DEX_HTTP_TIMEOUT = int(os.getenv("DEX_HTTP_TIMEOUT", "12"))
DEX_FETCH_PAUSE_SECONDS = float(os.getenv("ALPHA_DEX_FETCH_PAUSE_SECONDS", "0.08"))
DEX_429_BACKOFF_SECONDS = float(os.getenv("ALPHA_DEX_429_BACKOFF_SECONDS", "2.25"))
DEX_429_MAX_RETRIES = int(os.getenv("ALPHA_DEX_429_MAX_RETRIES", "2"))


# ============================================================
# HELPERS
# ============================================================

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _sleep_jitter(base: float) -> None:
    time.sleep(max(0.0, base + random.uniform(-0.03, 0.06)))


def _get_json_with_backoff(url: str) -> Optional[dict]:
    for attempt in range(DEX_429_MAX_RETRIES + 1):
        try:
            r = requests.get(url, timeout=DEX_HTTP_TIMEOUT)
            if r.status_code == 429:
                _sleep_jitter(DEX_429_BACKOFF_SECONDS * (attempt + 1))
                continue
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, dict) else None
        except Exception:
            _sleep_jitter(0.2)
    return None


def fetch_pairs_by_address(token_address: str) -> List[dict]:
    data = _get_json_with_backoff(f"{DEX_TOKEN_PAIRS}{token_address}")
    pairs = data.get("pairs", []) if isinstance(data, dict) else []
    return pairs if isinstance(pairs, list) else []


def _best_pair_combo(pairs: List[dict]) -> dict:
    if not pairs:
        return {}

    def score(p: dict) -> float:
        liq = _safe_float((p.get("liquidity") or {}).get("usd"))
        v1 = _safe_float((p.get("volume") or {}).get("h1"))
        ch5 = _safe_float((p.get("priceChange") or {}).get("m5"))
        ch1 = _safe_float((p.get("priceChange") or {}).get("h1"))
        s = ch5 * 1.45 + ch1 * 0.85 + (liq / 20000.0) + (v1 / 50000.0)

        if liq < 4000 and (ch5 > 80 or ch1 > 200):
            s *= 0.25
        return s

    return sorted(pairs, key=score, reverse=True)[0]


def _age_tag(pair_created_at_ms: Any) -> str:
    try:
        if not pair_created_at_ms:
            return "Unknown"
        created = int(pair_created_at_ms) / 1000.0
        age_sec = max(0.0, time.time() - created)

        if age_sec < 60 * 30:
            return "EARLY (≤30m)"
        if age_sec < 60 * 60 * 6:
            return "EARLY (≤6h)"
        if age_sec < 60 * 60 * 24:
            return "MID (≤24h)"
        if age_sec < 60 * 60 * 24 * 3:
            return "MID (≤3d)"
        return "LATE (3d+)"
    except Exception:
        return "Unknown"


def _accel_label(ch_m5: float, ch_1h: float) -> str:
    try:
        delta = ch_m5 - (ch_1h / 12.0)
        if delta > 8:
            return "⬆️ ACCEL UP"
        if delta < -8:
            return "⬇️ ACCEL DOWN"
        return "➡️ FLAT"
    except Exception:
        return "➡️ FLAT"


def _reversal_warning(ch_m5: float, ch_1h: float, vol_1h: float, liq: float) -> str:
    warn = False
    if ch_m5 >= 150 and ch_1h < 60:
        warn = True
    if liq < 15000 and ch_m5 > 80:
        warn = True
    if ch_m5 > 120 and vol_1h < 20000:
        warn = True
    return "🔁 Reversal Warning: YES" if warn else "🔁 Reversal Warning: NO"


def _exhaustion_detection(ch_m5: float, ch_1h: float, liq: float, vol_1h: float) -> str:
    exhaustion = False
    if ch_m5 > 250 and liq < 20000:
        exhaustion = True
    if ch_m5 > 200 and vol_1h < 30000:
        exhaustion = True
    if ch_1h > 300 and liq < 25000:
        exhaustion = True
    return "📉 Exhaustion: HIGH" if exhaustion else "📉 Exhaustion: LOW"


def _confidence_score(
    ch_m5: float,
    ch_1h: float,
    ch_24h: float,
    vol_1h: float,
    vol_24h: float,
    liq: float,
    age_tag: str,
) -> Dict[str, Any]:
    move_score = min(40.0, max(0.0, (ch_m5 * 0.18) + (ch_1h * 0.10)))
    vol_score = min(35.0, max(0.0, (vol_1h / 8000.0) + (vol_24h / 100000.0)))
    liq_score = min(25.0, max(0.0, liq / 2500.0))

    age_bias = 0.0
    if "EARLY" in age_tag:
        age_bias = 3.0
    elif "MID" in age_tag:
        age_bias = 1.5

    raw = move_score + vol_score + liq_score + age_bias
    conf = int(max(0, min(100, round(raw))))

    return {
        "confidence": conf,
        "breakdown": {
            "move": int(round(move_score)),
            "vol": int(round(vol_score)),
            "liq": int(round(liq_score)),
            "age_bias": int(round(age_bias)),
        }
    }


# ============================================================
# GATES
# ============================================================

def _passes_normal_gate(liq_usd: float, vol_1h: float, vol_24h: float) -> bool:
    if liq_usd < MIN_LIQ_USD:
        return False
    if vol_1h < MIN_VOL_1H and vol_24h < MIN_VOL_24H:
        return False
    return True


def _passes_moonshot_v1(liq_usd: float, vol_1h: float, vol_24h: float, ch_m5: float, ch_1h: float) -> bool:
    if not MOONSHOT_V1_ENABLE:
        return False
    if liq_usd < MOONSHOT_V1_MIN_LIQ_USD:
        return False
    if not (vol_1h >= MOONSHOT_V1_MIN_VOL_1H or vol_24h >= MOONSHOT_V1_MIN_VOL_24H):
        return False
    return (ch_m5 >= MOONSHOT_V1_CH_M5) or (ch_1h >= MOONSHOT_V1_CH_1H)


def _passes_moonshot_v2(liq_usd: float, vol_1h: float, ch_m5: float, ch_1h: float) -> bool:
    if not MOONSHOT_V2_ENABLE:
        return False
    if liq_usd < MOONSHOT_V2_MIN_LIQ_USD:
        return False
    if vol_1h < MOONSHOT_V2_MIN_VOL_1H:
        return False
    return (ch_m5 >= MOONSHOT_V2_CH_M5) or (ch_1h >= MOONSHOT_V2_CH_1H)


# ============================================================
# ANALYSIS
# ============================================================

def analyze_pair(pair: dict) -> Optional[dict]:
    try:
        if not isinstance(pair, dict):
            return None

        base = pair.get("baseToken") or {}
        mint = base.get("address") or ""
        symbol = (base.get("symbol") or "UNKNOWN").upper()

        liq_usd = _safe_float((pair.get("liquidity") or {}).get("usd"))
        vol_1h = _safe_float((pair.get("volume") or {}).get("h1"))
        vol_24h = _safe_float((pair.get("volume") or {}).get("h24"))

        ch_m5 = _safe_float((pair.get("priceChange") or {}).get("m5"))
        ch_1h = _safe_float((pair.get("priceChange") or {}).get("h1"))
        ch_24h = _safe_float((pair.get("priceChange") or {}).get("h24"))

        price = _safe_float(pair.get("priceUsd"))

        if max(ch_m5, ch_1h, ch_24h) < MIN_MOVE_ANY:
            return None

        normal_ok = _passes_normal_gate(liq_usd, vol_1h, vol_24h)
        moon_v1_ok = _passes_moonshot_v1(liq_usd, vol_1h, vol_24h, ch_m5, ch_1h)
        moon_v2_ok = _passes_moonshot_v2(liq_usd, vol_1h, ch_m5, ch_1h)

        if not (normal_ok or moon_v1_ok or moon_v2_ok):
            return None

        if ch_m5 > 300 and vol_1h > 150_000:
            tier = "ROCKET"
        elif moon_v2_ok:
            tier = "MOONSHOT-V2"
        elif moon_v1_ok:
            tier = "MOONSHOT-V1"
        elif ch_m5 > 40 or ch_1h > 80:
            tier = "MOMENTUM"
        else:
            tier = "WATCH"

        age = _age_tag(pair.get("pairCreatedAt"))
        accel = _accel_label(ch_m5, ch_1h)
        reversal = _reversal_warning(ch_m5, ch_1h, vol_1h, liq_usd)
        exhaustion = _exhaustion_detection(ch_m5, ch_1h, liq_usd, vol_1h)
        conf_pack = _confidence_score(ch_m5, ch_1h, ch_24h, vol_1h, vol_24h, liq_usd, age)

        # Whale intel (optional)
        holders = get_top_holders(mint, top_n=8)
        whale_score = whale_score_from_holders(holders)

        return {
            "mint": mint,
            "address": mint,
            "symbol": symbol,
            "price": price,
            "liquidity": liq_usd,
            "volume_1h": vol_1h,
            "volume_24h": vol_24h,
            "change_m5": ch_m5,
            "change_1h": ch_1h,
            "change_24h": ch_24h,
            "url": pair.get("url"),
            "tier": tier,
            "age_tag": age,
            "accel": accel,
            "reversal": reversal,
            "exhaustion": exhaustion,
            "confidence": conf_pack["confidence"],
            "confidence_breakdown": conf_pack["breakdown"],
            "whale_score": whale_score,
            "ts": _now_iso(),
        }

    except Exception as e:
        print("❌ analyze_pair failed:", e)
        return None


# ============================================================
# ALERT FORMATS
# ============================================================

def format_alert_legacy(token: dict) -> str:
    return (
        f"🚀 *MirrorX Rocket Alert*\n\n"
        f"🪙 *{token.get('symbol','UNKNOWN')}*\n"
        f"Mint: {token.get('mint','')}\n"
        f"⚡ Tier: *{token.get('tier','').upper()}*\n"
        f"🧠 Confidence: *{int(token.get('confidence',0))}/100*\n"
        f"🕒 Stage: *{token.get('age_tag','Unknown')}*\n\n"
        f"💧 Liquidity: ${int(token.get('liquidity',0)):,}\n"
        f"📊 Vol 1H: ${int(token.get('volume_1h',0)):,}\n"
        f"📈 5m: {token.get('change_m5',0):.2f}%\n"
        f"📈 1H: {token.get('change_1h',0):.2f}%\n"
        f"📈 24H: {token.get('change_24h',0):.2f}%\n\n"
        f"{token.get('accel','➡️ FLAT')}\n"
        f"🔗 {token.get('url','')}"
    )


def format_alert_elite(token: dict) -> str:
    bd = token.get("confidence_breakdown") or {}
    whale_score = int(token.get("whale_score", 0))
    return (
        f"🚨 *MirrorX Alpha Detected*\n\n"
        f"🪙 *{token.get('symbol','UNKNOWN')}*\n"
        f"Mint: {token.get('mint','')}\n"
        f"⚡ Tier: *{token.get('tier','').upper()}*\n"
        f"🧠 Confidence: *{int(token.get('confidence',0))}/100* "
        f"(Move {bd.get('move',0)} | Vol {bd.get('vol',0)} | Liq {bd.get('liq',0)})\n"
        f"🐋 Whale Score: *{whale_score}/100*\n"
        f"🕒 Tag: *{token.get('age_tag','Unknown')}*\n\n"
        f"💧 Liquidity: ${int(token.get('liquidity',0)):,}\n"
        f"📊 Vol 1H: ${int(token.get('volume_1h',0)):,}\n"
        f"📊 Vol 24H: ${int(token.get('volume_24h',0)):,}\n\n"
        f"📈 5m: {token.get('change_m5',0):.2f}%\n"
        f"📈 1H: {token.get('change_1h',0):.2f}%\n"
        f"📈 24H: {token.get('change_24h',0):.2f}%\n\n"
        f"{token.get('accel','➡️ FLAT')}\n"
        f"{token.get('reversal','🔁 Reversal Warning: NO')}\n"
        f"{token.get('exhaustion','📉 Exhaustion: LOW')}\n\n"
        f"🔗 {token.get('url','')}\n"
        f"⚠️ Educational alert only."
    )


# ============================================================
# DETECTION LOOP
# ============================================================

def detect_alpha_tokens() -> List[dict]:
    candidates = get_top_candidates(limit=RADAR_LIMIT) or []
    found: List[dict] = []

    for c in candidates:
        addr = c.get("address")
        if not addr:
            continue

        pairs = fetch_pairs_by_address(addr)
        best = _best_pair_combo(pairs)
        if not best:
            _sleep_jitter(DEX_FETCH_PAUSE_SECONDS)
            continue

        # Pre-gate snapshot for acceleration history
        try:
            base = best.get("baseToken") or {}
            record_snapshot("alpha_pre_gate", {
                "address": base.get("address"),
                "symbol": (base.get("symbol") or "").upper(),
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
            _sleep_jitter(DEX_FETCH_PAUSE_SECONDS)
            continue

        record_snapshot("alpha_detector", {
            "mint": token.get("mint"),
            "symbol": token.get("symbol"),
            "priceUsd": token.get("price"),
            "liquidityUsd": token.get("liquidity"),
            "volumeH1": token.get("volume_1h"),
            "volumeH24": token.get("volume_24h"),
            "changeM5": token.get("change_m5"),
            "changeH1": token.get("change_1h"),
            "changeH24": token.get("change_24h"),
            "tier": token.get("tier"),
            "confidence": token.get("confidence"),
            "whale_score": token.get("whale_score"),
            "ts": _now_iso(),
        })

        found.append(token)
        _sleep_jitter(DEX_FETCH_PAUSE_SECONDS)

    # Rank by confidence then 5m
    return sorted(found, key=lambda t: (_safe_float(t.get("confidence"), 0), _safe_float(t.get("change_m5"), 0)), reverse=True)


def push_alpha_alerts() -> None:
    detected = detect_alpha_tokens()
    if not detected:
        return

    top = detected[:MAX_ALERTS]

    for token in top:
        mint = token.get("mint") or ""
        strength = _safe_float(token.get("confidence"), _safe_float(token.get("change_1h"), 0))

        if not can_alert(mint, strength):
            continue

        # Persist alert (optional)
        try:
            add_alert("alpha_detector", {
                "mint": mint,
                "symbol": token.get("symbol"),
                "tier": token.get("tier"),
                "confidence": token.get("confidence"),
                "whale_score": token.get("whale_score"),
                "ts": _now_iso(),
            })
        except Exception:
            pass

        # Record signal for performance tracking
        try:
            record_signal(token)
        except Exception:
            pass

        # ✅ Free tier gets legacy format
        send_to_tier(format_alert_legacy(token), "free")

        # ✅ Elite tier gets elite format
        send_to_tier(format_alert_elite(token), "elite")


if __name__ == "__main__":
    push_alpha_alerts()
