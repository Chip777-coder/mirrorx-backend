# src/services/mirrorstock_detector.py
"""
MirrorStock Detector (Penny Rocket Mode + Market Gainers + Elite Add-ons)
-----------------------------------------------------------------------
MirrorX-style pipeline, tuned for stocks:

A) Penny Rocket Mode:
   - Penny-band focus + stricter quality gates + moonshot exception

B) Market Gainers Mode:
   - Not limited to penny stocks
   - Push alerts for 5–10%+ gain signals with reasonable participation

ELITE ADD-ONS (SAFE / EDUCATIONAL):
✅ Confidence score (0–100)
✅ Early / Mid / Late tagging
✅ Reversal warning
✅ Exhaustion detection
✅ Acute volume surge trigger (volume shock)
✅ Performance tracking hooks (simulated)
✅ Paper-trading mode (simulated entry/TP/SL; no real trades)
✅ Optional chart image (PNG) via chart_render.py

Educational tooling only. Not trade advice.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.services.telegram_alerts import send_telegram_message, send_telegram_photo
from src.services.movers_store import record_snapshot, compute_acceleration

# NEW: Modular radar + chart rendering
from src.services.stock_radar import discover_candidates, enrich_ticker
from src.services.chart_render import render_price_volume_chart_png_bytes


# Optional alert store (safe if file doesn't exist)
try:
    from src.services.alerts_store import add_alert  # type: ignore
except Exception:
    def add_alert(_source: str, _payload: dict):
        return


# ============================================================
# Config (env-driven)
# ============================================================

# --- Penny stock "focus band"
PENNY_MAX_PRICE = float(os.getenv("STOCK_PENNY_MAX_PRICE", "5.00"))
PENNY_MIN_PRICE = float(os.getenv("STOCK_PENNY_MIN_PRICE", "0.10"))

# --- Penny Rocket gates
MIN_DOLLAR_VOL_1H = float(os.getenv("STOCK_MIN_DOLLAR_VOL_1H", "250000"))
MIN_DOLLAR_VOL_DAY = float(os.getenv("STOCK_MIN_DOLLAR_VOL_DAY", "1500000"))
MIN_REL_VOL = float(os.getenv("STOCK_MIN_REL_VOL", "2.0"))
MIN_PCT_CHANGE_5M = float(os.getenv("STOCK_MIN_PCT_CHANGE_5M", "1.0"))
MIN_PCT_CHANGE_1H = float(os.getenv("STOCK_MIN_PCT_CHANGE_1H", "5.0"))
MIN_PCT_CHANGE_DAY = float(os.getenv("STOCK_MIN_PCT_CHANGE_DAY", "15.0"))

# --- Moonshot exception rules (penny style)
MOONSHOT_MIN_PCT_DAY = float(os.getenv("STOCK_MOONSHOT_MIN_PCT_DAY", "80.0"))
MOONSHOT_MIN_DOLLAR_VOL_DAY = float(os.getenv("STOCK_MOONSHOT_MIN_DOLLAR_VOL_DAY", "500000"))
MOONSHOT_MIN_PRICE = float(os.getenv("STOCK_MOONSHOT_MIN_PRICE", "0.03"))

# --- Market Gainers Mode
MARKET_GAINERS_ENABLE = os.getenv("STOCK_MARKET_GAINERS_ENABLE", "1") == "1"
MARKET_MIN_PCT_5M = float(os.getenv("STOCK_MARKET_MIN_PCT_CHANGE_5M", "5.0"))
MARKET_MIN_PCT_1H = float(os.getenv("STOCK_MARKET_MIN_PCT_CHANGE_1H", "10.0"))
MARKET_MIN_PCT_DAY = float(os.getenv("STOCK_MARKET_MIN_PCT_CHANGE_DAY", "15.0"))
MARKET_MIN_DOLLAR_VOL_1H = float(os.getenv("STOCK_MARKET_MIN_DOLLAR_VOL_1H", "150000"))
MARKET_MIN_DOLLAR_VOL_DAY = float(os.getenv("STOCK_MARKET_MIN_DOLLAR_VOL_DAY", "750000"))
MARKET_MAX_ALERTS = int(os.getenv("STOCK_MARKET_MAX_ALERTS", "5"))

# How many alerts per run (penny)
MAX_ALERTS = int(os.getenv("STOCK_MAX_ALERTS", "5"))

# Discovery scan size
RADAR_LIMIT = int(os.getenv("STOCK_RADAR_LIMIT", "60"))

# Throttling
SLEEP_BETWEEN_CALLS = float(os.getenv("STOCK_SLEEP_BETWEEN_CALLS", "0.10"))

# ELITE: Acute volume surge trigger
VOL_SHOCK_ENABLE = os.getenv("STOCK_VOL_SHOCK_ENABLE", "1") == "1"
VOL_SHOCK_MIN_DV1H = float(os.getenv("STOCK_VOL_SHOCK_MIN_DOLLAR_VOL_1H", "100000"))
VOL_SHOCK_RATIO_MIN = float(os.getenv("STOCK_VOL_SHOCK_RATIO_MIN", "2.0"))  # last-15m vs prior-45m ratio

# ELITE: Reversal/exhaustion heuristics
EXHAUSTION_ENABLE = os.getenv("STOCK_EXHAUSTION_ENABLE", "1") == "1"
EXHAUSTION_M5_EXTEND = float(os.getenv("STOCK_EXHAUSTION_M5_EXTEND", "8.0"))

# ELITE: Confidence score shaping
CONF_BASELINE_DV_DAY = float(os.getenv("STOCK_CONF_BASELINE_DV_DAY", "1500000"))
CONF_BASELINE_DV_1H = float(os.getenv("STOCK_CONF_BASELINE_DV_1H", "250000"))

# ELITE: Chart pics (optional)
CHART_ENABLE = os.getenv("STOCK_CHART_ENABLE", "1") == "1"
CHART_AGG_MINUTES = int(os.getenv("STOCK_CHART_AGG_MINUTES", "5"))  # matches stock_radar default

# ELITE: Paper trading (simulated)
PAPER_ENABLE = os.getenv("STOCK_PAPER_ENABLE", "1") == "1"
PAPER_R_MULT_TP = float(os.getenv("STOCK_PAPER_R_MULT_TP", "2.0"))
PAPER_R_MULT_SL = float(os.getenv("STOCK_PAPER_R_MULT_SL", "1.0"))


# ============================================================
# Helpers
# ============================================================

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default

def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def _fmt_money(x: float) -> str:
    if x >= 1_000_000_000:
        return f"${x/1_000_000_000:.2f}B"
    if x >= 1_000_000:
        return f"${x/1_000_000:.2f}M"
    if x >= 1_000:
        return f"${x/1_000:.1f}K"
    return f"${x:,.0f}"


# ============================================================
# ELITE signal derivation (from stock_radar enrichment output)
# ============================================================

def _derive_elite_from_aggs(x: Dict[str, Any]) -> None:
    """
    Uses x["_aggs_5m_desc"] (newest-first) from stock_radar.enrich_ticker()
    to compute:
      - vol_surge_ratio_15m (last 15m vs prior 45m)
      - micro_reversal_hint
      - range_proxy (ATR-ish proxy)
    """
    bars = x.get("_aggs_5m_desc") or []
    if not isinstance(bars, list) or len(bars) < 12:
        x["vol_surge_ratio_15m"] = 0.0
        x["micro_reversal_hint"] = False
        x["range_proxy"] = 0.0
        return

    v_last_15 = sum(_safe_float(r.get("v"), 0.0) for r in bars[:3])
    v_prev_45 = sum(_safe_float(r.get("v"), 0.0) for r in bars[3:12])
    x["vol_surge_ratio_15m"] = (v_last_15 / v_prev_45) if v_prev_45 > 0 else 0.0

    if len(bars) >= 3:
        c0 = _safe_float(bars[0].get("c"), 0.0)
        c1 = _safe_float(bars[1].get("c"), 0.0)
        c2 = _safe_float(bars[2].get("c"), 0.0)
        x["micro_reversal_hint"] = bool((c0 < c1) and (c1 > c2))
    else:
        x["micro_reversal_hint"] = False

    ranges = []
    for r in bars[:20]:
        h = _safe_float(r.get("h"), 0.0)
        l = _safe_float(r.get("l"), 0.0)
        if h > 0 and l > 0 and h >= l:
            ranges.append(h - l)
    x["range_proxy"] = (sum(ranges) / len(ranges)) if ranges else 0.0


def _stage_tag(x: Dict[str, Any]) -> str:
    chd = _safe_float(x.get("day_change_pct"), 0.0)
    ch1 = _safe_float(x.get("change_1h"), 0.0)
    ch5 = _safe_float(x.get("change_5m"), 0.0)

    if chd < 20.0 and (ch1 >= 8.0 or ch5 >= 2.5):
        return "EARLY"
    if chd >= 80.0:
        return "LATE"
    return "MID"


def _volume_shock(x: Dict[str, Any]) -> bool:
    if not VOL_SHOCK_ENABLE:
        return False
    dv1h = _safe_float(x.get("dollar_vol_1h"), 0.0)
    ratio = _safe_float(x.get("vol_surge_ratio_15m"), 0.0)
    return bool(dv1h >= VOL_SHOCK_MIN_DV1H and ratio >= VOL_SHOCK_RATIO_MIN)


def _confidence_score(x: Dict[str, Any]) -> float:
    ch5 = max(_safe_float(x.get("change_5m"), 0.0), 0.0)
    ch1 = max(_safe_float(x.get("change_1h"), 0.0), 0.0)
    chd = max(_safe_float(x.get("day_change_pct"), 0.0), 0.0)

    dv1 = max(_safe_float(x.get("dollar_vol_1h"), 0.0), 0.0)
    dvd = max(_safe_float(x.get("dollar_vol_day"), 0.0), 0.0)
    rvol = max(_safe_float(x.get("rel_vol"), 0.0), 0.0)

    surge = max(_safe_float(x.get("vol_surge_ratio_15m"), 0.0), 0.0)
    shock = 1.0 if bool(x.get("volume_shock", False)) else 0.0

    dv1_n = _clamp(dv1 / max(CONF_BASELINE_DV_1H, 1.0), 0.0, 6.0)
    dvd_n = _clamp(dvd / max(CONF_BASELINE_DV_DAY, 1.0), 0.0, 6.0)
    rvol_n = _clamp(rvol, 0.0, 10.0)

    mom = (ch1 * 0.55) + (ch5 * 0.25) + (chd * 0.20)
    mom_n = _clamp(mom / 25.0, 0.0, 6.0)

    surge_n = _clamp(surge / 2.0, 0.0, 4.0)

    raw = (
        mom_n * 14.0 +
        dv1_n * 9.0 +
        dvd_n * 6.0 +
        rvol_n * 2.0 +
        surge_n * 4.0 +
        shock * 6.0
    )

    if bool(x.get("exhaustion", False)):
        raw *= 0.78
    if bool(x.get("reversal_warning", False)):
        raw *= 0.88

    return float(_clamp(raw, 0.0, 100.0))


def _apply_elite_signals(x: Dict[str, Any]) -> Dict[str, Any]:
    _derive_elite_from_aggs(x)

    if EXHAUSTION_ENABLE:
        ch5 = _safe_float(x.get("change_5m"), 0.0)
        chd = _safe_float(x.get("day_change_pct"), 0.0)
        dv1 = _safe_float(x.get("dollar_vol_1h"), 0.0)
        micro_rev = bool(x.get("micro_reversal_hint", False))
        extended = (ch5 >= EXHAUSTION_M5_EXTEND) or (chd >= 80.0)
        x["exhaustion"] = bool(extended and (micro_rev or dv1 < CONF_BASELINE_DV_1H * 0.75))
    else:
        x["exhaustion"] = False

    x["reversal_warning"] = bool(x.get("exhaustion", False) or x.get("micro_reversal_hint", False))
    x["stage_tag"] = _stage_tag(x)
    x["volume_shock"] = _volume_shock(x)
    x["confidence"] = _confidence_score(x)
    return x


# ============================================================
# Gates
# ============================================================

def _is_penny_band(price: float) -> bool:
    return (price >= PENNY_MIN_PRICE) and (price <= PENNY_MAX_PRICE)

def passes_penny_gates(x: Dict[str, Any]) -> bool:
    price = _safe_float(x.get("price"), 0.0)
    if price <= 0 or not _is_penny_band(price):
        return False

    dv1h = _safe_float(x.get("dollar_vol_1h"), 0.0)
    dvday = _safe_float(x.get("dollar_vol_day"), 0.0)
    rvol = _safe_float(x.get("rel_vol"), 0.0)

    ch5 = _safe_float(x.get("change_5m"), 0.0)
    ch1 = _safe_float(x.get("change_1h"), 0.0)
    chd = _safe_float(x.get("day_change_pct"), 0.0)

    moving = (ch5 >= MIN_PCT_CHANGE_5M) or (ch1 >= MIN_PCT_CHANGE_1H) or (chd >= MIN_PCT_CHANGE_DAY)
    if not moving:
        return False

    if not (dv1h >= MIN_DOLLAR_VOL_1H or dvday >= MIN_DOLLAR_VOL_DAY):
        return False

    if rvol < MIN_REL_VOL:
        return False

    return True

def moonshot_exception(x: Dict[str, Any]) -> bool:
    price = _safe_float(x.get("price"), 0.0)
    chd = _safe_float(x.get("day_change_pct"), 0.0)
    dvday = _safe_float(x.get("dollar_vol_day"), 0.0)
    if price < MOONSHOT_MIN_PRICE:
        return False
    return (chd >= MOONSHOT_MIN_PCT_DAY and dvday >= MOONSHOT_MIN_DOLLAR_VOL_DAY)

def passes_market_gainer_gates(x: Dict[str, Any]) -> bool:
    price = _safe_float(x.get("price"), 0.0)
    if price <= 0:
        return False

    dv1h = _safe_float(x.get("dollar_vol_1h"), 0.0)
    dvday = _safe_float(x.get("dollar_vol_day"), 0.0)

    ch5 = _safe_float(x.get("change_5m"), 0.0)
    ch1 = _safe_float(x.get("change_1h"), 0.0)
    chd = _safe_float(x.get("day_change_pct"), 0.0)

    moving = (ch5 >= MARKET_MIN_PCT_5M) or (ch1 >= MARKET_MIN_PCT_1H) or (chd >= MARKET_MIN_PCT_DAY)
    if not moving:
        return False

    if not (dv1h >= MARKET_MIN_DOLLAR_VOL_1H or dvday >= MARKET_MIN_DOLLAR_VOL_DAY):
        return False

    return True


# ============================================================
# Scoring + Paper-trade plan (simulated)
# ============================================================

def rocket_score_penny(x: Dict[str, Any]) -> float:
    conf = _safe_float(x.get("confidence"), 0.0)
    ch5 = max(_safe_float(x.get("change_5m"), 0.0), 0.0)
    ch1 = max(_safe_float(x.get("change_1h"), 0.0), 0.0)
    chd = max(_safe_float(x.get("day_change_pct"), 0.0), 0.0)
    dv1 = _safe_float(x.get("dollar_vol_1h"), 0.0)
    dvd = _safe_float(x.get("dollar_vol_day"), 0.0)
    rvol = _safe_float(x.get("rel_vol"), 0.0)

    score = 0.0
    score += conf * 1.25
    score += ch5 * 0.9
    score += ch1 * 0.6
    score += chd * 0.25
    score += min(dv1 / 500_000.0, 8.0) * 6.0
    score += min(dvd / 2_000_000.0, 8.0) * 5.0
    score += min(rvol, 10.0) * 3.0
    if bool(x.get("volume_shock", False)):
        score += 12.0
    return float(score)

def score_market_gainer(x: Dict[str, Any]) -> float:
    conf = _safe_float(x.get("confidence"), 0.0)
    ch1 = max(_safe_float(x.get("change_1h"), 0.0), 0.0)
    dv1 = _safe_float(x.get("dollar_vol_1h"), 0.0)
    shock = 1.0 if bool(x.get("volume_shock", False)) else 0.0
    return (conf * 1.3) + (ch1 * 0.35) + (dv1 / 400_000.0) + (shock * 8.0)

def _paper_trade_plan(x: Dict[str, Any]) -> Dict[str, Any]:
    entry = _safe_float(x.get("price"), 0.0)
    rp = _safe_float(x.get("range_proxy"), 0.0)
    if entry <= 0:
        return {}

    R = rp if rp > 0 else max(entry * 0.02, 0.01)
    tp = entry + (R * PAPER_R_MULT_TP)
    sl = max(0.0, entry - (R * PAPER_R_MULT_SL))

    return {"paper_entry": entry, "paper_tp": tp, "paper_sl": sl, "paper_r": R}


# ============================================================
# Alert Formatting
# ============================================================

def _elite_lines(x: Dict[str, Any]) -> str:
    conf = _safe_float(x.get("confidence"), 0.0)
    stage = (x.get("stage_tag") or "MID").upper()
    vol_shock = "YES" if bool(x.get("volume_shock", False)) else "no"
    rev = "⚠️ YES" if bool(x.get("reversal_warning", False)) else "no"
    exh = "⚠️ YES" if bool(x.get("exhaustion", False)) else "no"
    surge = _safe_float(x.get("vol_surge_ratio_15m"), 0.0)
    return (
        f"🧠 Confidence: <b>{conf:.1f}/100</b>\n"
        f"🔥 Stage: <b>{stage}</b>\n"
        f"📉 Exhaustion: <b>{exh}</b>\n"
        f"🔁 Reversal Warning: <b>{rev}</b>\n"
        f"⚡ Volume Shock: <b>{vol_shock}</b> (15m surge x{surge:.2f})\n"
    )

def format_penny_alert(x: Dict[str, Any]) -> str:
    ticker = x.get("ticker", "UNKNOWN")
    price = _safe_float(x.get("price"), 0.0)
    ch5 = _safe_float(x.get("change_5m"), 0.0)
    ch1 = _safe_float(x.get("change_1h"), 0.0)
    chd = _safe_float(x.get("day_change_pct"), 0.0)
    dv1 = _safe_float(x.get("dollar_vol_1h"), 0.0)
    dvd = _safe_float(x.get("dollar_vol_day"), 0.0)
    rvol = _safe_float(x.get("rel_vol"), 0.0)

    accel = compute_acceleration(ticker)
    accel_hint = accel.get("accel_hint", "n/a")

    gate = "normal"
    if moonshot_exception(x) and not passes_penny_gates(x):
        gate = "moonshot_exception"

    url = x.get("url") or f"https://www.tradingview.com/symbols/{ticker}/"

    paper = _paper_trade_plan(x) if PAPER_ENABLE else {}
    paper_line = ""
    if paper:
        paper_line = (
            f"🤖 Paper Plan: entry ${paper['paper_entry']:.4f} | "
            f"TP ${paper['paper_tp']:.4f} | SL ${paper['paper_sl']:.4f}\n"
        )

    return (
        f"<b>📈 MirrorStock Rocket Alert</b>\n"
        f"🔑 Ticker: <b>{ticker}</b>\n"
        f"⚡ Gate: <b>{gate}</b>\n"
        f"💵 Price: ${price:.4f}\n"
        f"📈 5m: {ch5:.2f}% | 1h: {ch1:.2f}% | Day: {chd:.2f}%\n"
        f"💰 $Vol 1h: {_fmt_money(dv1)} | Day: {_fmt_money(dvd)}\n"
        f"📊 RVOL (heuristic): {rvol:.2f}\n"
        f"🚀 Acceleration: <b>{accel_hint}</b>\n\n"
        f"{_elite_lines(x)}"
        f"{paper_line}\n"
        f"🔎 Confirm catalysts/news + spreads/halts. Pennies can reverse violently.\n"
        f"<a href='{url}'>Open chart</a>\n\n"
        f"⚠️ Educational alert only."
    )

def format_market_alert(x: Dict[str, Any]) -> str:
    ticker = x.get("ticker", "UNKNOWN")
    price = _safe_float(x.get("price"), 0.0)
    ch5 = _safe_float(x.get("change_5m"), 0.0)
    ch1 = _safe_float(x.get("change_1h"), 0.0)
    chd = _safe_float(x.get("day_change_pct"), 0.0)
    dv1 = _safe_float(x.get("dollar_vol_1h"), 0.0)
    dvd = _safe_float(x.get("dollar_vol_day"), 0.0)

    accel = compute_acceleration(ticker)
    accel_hint = accel.get("accel_hint", "n/a")

    url = x.get("url") or f"https://www.tradingview.com/symbols/{ticker}/"

    paper = _paper_trade_plan(x) if PAPER_ENABLE else {}
    paper_line = ""
    if paper:
        paper_line = (
            f"🤖 Paper Plan: entry ${paper['paper_entry']:.4f} | "
            f"TP ${paper['paper_tp']:.4f} | SL ${paper['paper_sl']:.4f}\n"
        )

    return (
        f"<b>📊 MirrorStock Market Gainer</b>\n"
        f"🔑 Ticker: <b>{ticker}</b>\n"
        f"💵 Price: ${price:.4f}\n"
        f"📈 5m: {ch5:.2f}% | 1h: {ch1:.2f}% | Day: {chd:.2f}%\n"
        f"💰 $Vol 1h: {_fmt_money(dv1)} | Day: {_fmt_money(dvd)}\n"
        f"🚀 Acceleration: <b>{accel_hint}</b>\n\n"
        f"{_elite_lines(x)}"
        f"{paper_line}\n"
        f"🔎 Confirm catalyst + liquidity/spreads (halts possible). Manage risk.\n"
        f"<a href='{url}'>Open chart</a>\n\n"
        f"⚠️ Educational alert only."
    )


# ============================================================
# Pipelines
# ============================================================

def detect_penny_rockets(limit: int = RADAR_LIMIT) -> List[Dict[str, Any]]:
    cands = discover_candidates(limit=limit) or []
    if not cands:
        return []

    found: List[Dict[str, Any]] = []

    for c in cands:
        tk = (c.get("ticker") or "").upper().strip()
        if not tk:
            continue

        enriched = enrich_ticker(tk)
        if not enriched:
            continue

        enriched = _apply_elite_signals(enriched)

        ok = passes_penny_gates(enriched) or moonshot_exception(enriched)
        if not ok:
            continue

        record_snapshot("mirrorstock_detector", {
            "address": tk,
            "symbol": tk,
            "priceUsd": _safe_float(enriched.get("price"), 0.0),
            "volumeH1": _safe_float(enriched.get("dollar_vol_1h"), 0.0),
            "volumeH24": _safe_float(enriched.get("dollar_vol_day"), 0.0),
            "changeM5": _safe_float(enriched.get("change_5m"), 0.0),
            "changeH1": _safe_float(enriched.get("change_1h"), 0.0),
            "changeH24": _safe_float(enriched.get("day_change_pct"), 0.0),
            "confidence": _safe_float(enriched.get("confidence"), 0.0),
            "stage": enriched.get("stage_tag"),
            "volumeShock": bool(enriched.get("volume_shock", False)),
            "reversalWarning": bool(enriched.get("reversal_warning", False)),
            "exhaustion": bool(enriched.get("exhaustion", False)),
            "url": enriched.get("url"),
            "ts": _now_iso(),
        })

        enriched["source"] = c.get("source")
        found.append(enriched)
        time.sleep(SLEEP_BETWEEN_CALLS)

    found.sort(key=rocket_score_penny, reverse=True)
    return found

def detect_market_gainers(limit: int = RADAR_LIMIT) -> List[Dict[str, Any]]:
    if not MARKET_GAINERS_ENABLE:
        return []

    cands = discover_candidates(limit=limit) or []
    if not cands:
        return []

    found: List[Dict[str, Any]] = []

    for c in cands:
        tk = (c.get("ticker") or "").upper().strip()
        if not tk:
            continue

        enriched = enrich_ticker(tk)
        if not enriched:
            continue

        enriched = _apply_elite_signals(enriched)

        if not passes_market_gainer_gates(enriched):
            continue

        record_snapshot("mirrorstock_market", {
            "address": tk,
            "symbol": tk,
            "priceUsd": _safe_float(enriched.get("price"), 0.0),
            "volumeH1": _safe_float(enriched.get("dollar_vol_1h"), 0.0),
            "volumeH24": _safe_float(enriched.get("dollar_vol_day"), 0.0),
            "changeM5": _safe_float(enriched.get("change_5m"), 0.0),
            "changeH1": _safe_float(enriched.get("change_1h"), 0.0),
            "changeH24": _safe_float(enriched.get("day_change_pct"), 0.0),
            "confidence": _safe_float(enriched.get("confidence"), 0.0),
            "stage": enriched.get("stage_tag"),
            "volumeShock": bool(enriched.get("volume_shock", False)),
            "reversalWarning": bool(enriched.get("reversal_warning", False)),
            "exhaustion": bool(enriched.get("exhaustion", False)),
            "url": enriched.get("url"),
            "ts": _now_iso(),
        })

        enriched["source"] = c.get("source")
        found.append(enriched)
        time.sleep(SLEEP_BETWEEN_CALLS)

    found.sort(key=score_market_gainer, reverse=True)
    return found


def _dispatch_alert_with_optional_chart(msg: str, ticker: str, enriched: Dict[str, Any]) -> None:
    """
    Sends message and (optionally) chart image.
    IMPORTANT: routes through Telegram channel="mirrorstock" (no default).
    """
    if CHART_ENABLE:
        bars = enriched.get("_aggs_5m_desc") or []
        img = render_price_volume_chart_png_bytes(ticker=ticker, aggs_desc=bars, minutes=CHART_AGG_MINUTES)
        if img:
            ok = send_telegram_photo(img, caption=msg, channel="mirrorstock")
            if ok:
                return

    # text fallback (still MirrorStock channel)
    send_telegram_message(msg, channel="mirrorstock")


def push_mirrorstock_alerts():
    print("[SCHEDULER] Running MirrorStock Detector...")

    penny = detect_penny_rockets(limit=RADAR_LIMIT)
    market = detect_market_gainers(limit=RADAR_LIMIT)

    if not penny and not market:
        print("[MirrorStock] No standout signals.")
        return

    sent = 0
    seen = set()

    # 1) penny rockets first
    for x in penny[:MAX_ALERTS]:
        tk = (x.get("ticker") or "").upper().strip()
        if not tk or tk in seen:
            continue
        seen.add(tk)

        msg = format_penny_alert(x)

        # simulated performance tracking hook
        if PAPER_ENABLE:
            paper = _paper_trade_plan(x)
            if paper:
                record_snapshot("mirrorstock_paper_trade_open", {
                    "symbol": tk,
                    "entry": paper.get("paper_entry"),
                    "tp": paper.get("paper_tp"),
                    "sl": paper.get("paper_sl"),
                    "r": paper.get("paper_r"),
                    "confidence": _safe_float(x.get("confidence"), 0.0),
                    "stage": x.get("stage_tag"),
                    "ts": _now_iso(),
                })

        try:
            add_alert("mirrorstock_detector", {
                "symbol": tk,
                "address": tk,
                "url": x.get("url"),
                "message": msg,
            })
        except Exception:
            pass

        _dispatch_alert_with_optional_chart(msg, tk, x)
        sent += 1
        print(f"[MirrorStock] Sent penny alert for {tk}")

    # 2) then market gainers
    for x in market[:MARKET_MAX_ALERTS]:
        tk = (x.get("ticker") or "").upper().strip()
        if not tk or tk in seen:
            continue
        seen.add(tk)

        msg = format_market_alert(x)

        if PAPER_ENABLE:
            paper = _paper_trade_plan(x)
            if paper:
                record_snapshot("mirrorstock_paper_trade_open", {
                    "symbol": tk,
                    "entry": paper.get("paper_entry"),
                    "tp": paper.get("paper_tp"),
                    "sl": paper.get("paper_sl"),
                    "r": paper.get("paper_r"),
                    "confidence": _safe_float(x.get("confidence"), 0.0),
                    "stage": x.get("stage_tag"),
                    "ts": _now_iso(),
                })

        try:
            add_alert("mirrorstock_market", {
                "symbol": tk,
                "address": tk,
                "url": x.get("url"),
                "message": msg,
            })
        except Exception:
            pass

        _dispatch_alert_with_optional_chart(msg, tk, x)
        sent += 1
        print(f"[MirrorStock] Sent market alert for {tk}")

    print(f"[MirrorStock] Total alerts sent: {sent}")


if __name__ == "__main__":
    push_mirrorstock_alerts()
