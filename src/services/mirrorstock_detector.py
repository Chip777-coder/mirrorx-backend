# src/services/mirrorstock_detector.py
"""
MirrorStock Detector (Penny Rocket Mode + Market Gainers)
--------------------------------------------------------
MirrorX-style pipeline, tuned for stocks:

A) Penny Rocket Mode (original):
   - Penny-band focus + stricter quality gates

B) Market Gainers Mode (NEW):
   - Not limited to penny stocks
   - Push alerts for 5–10%+ gain signals with reasonable participation

Educational tooling only. Not trade advice.
"""

from __future__ import annotations

import os
import time
import requests
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.services.telegram_alerts import send_telegram_message
from src.services.movers_store import record_snapshot, compute_acceleration

# Optional alert store (safe if file doesn't exist)
try:
    from src.services.alerts_store import add_alert  # type: ignore
except Exception:
    def add_alert(_source: str, _payload: dict):
        return


# ============================================================
# Config (env-driven)
# ============================================================

# MirrorStock Telegram routing (separate bot/channel supported)
MIRRORSTOCK_CHAT_ID = os.getenv("MIRRORSTOCK_TELEGRAM_CHAT_ID", "").strip()
MIRRORSTOCK_TELEGRAM_TOKEN = os.getenv("MIRRORSTOCK_TELEGRAM_TOKEN", "").strip()  # <-- NEW
DEFAULT_TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()

# --- Penny stock "focus band"
PENNY_MAX_PRICE = float(os.getenv("STOCK_PENNY_MAX_PRICE", "5.00"))
PENNY_MIN_PRICE = float(os.getenv("STOCK_PENNY_MIN_PRICE", "0.10"))

# --- Penny Rocket gates (original behavior)
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

# --- Market Gainers Mode (NEW)
MARKET_GAINERS_ENABLE = os.getenv("STOCK_MARKET_GAINERS_ENABLE", "1") == "1"
MARKET_MIN_PCT_5M = float(os.getenv("STOCK_MARKET_MIN_PCT_CHANGE_5M", "5.0"))   # 5m >= 5%
MARKET_MIN_PCT_1H = float(os.getenv("STOCK_MARKET_MIN_PCT_CHANGE_1H", "10.0"))  # 1h >= 10%
MARKET_MIN_PCT_DAY = float(os.getenv("STOCK_MARKET_MIN_PCT_CHANGE_DAY", "15.0"))# day >= 15%
MARKET_MIN_DOLLAR_VOL_1H = float(os.getenv("STOCK_MARKET_MIN_DOLLAR_VOL_1H", "150000"))
MARKET_MIN_DOLLAR_VOL_DAY = float(os.getenv("STOCK_MARKET_MIN_DOLLAR_VOL_DAY", "750000"))
MARKET_MAX_ALERTS = int(os.getenv("STOCK_MARKET_MAX_ALERTS", "5"))

# How many alerts per run (penny)
MAX_ALERTS = int(os.getenv("STOCK_MAX_ALERTS", "5"))

# Discovery scan size
RADAR_LIMIT = int(os.getenv("STOCK_RADAR_LIMIT", "60"))

# API selection
STOCK_DATA_PROVIDER = os.getenv("STOCK_DATA_PROVIDER", "polygon").lower().strip()

# Polygon
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "").strip()
POLYGON_BASE = "https://api.polygon.io"

# Throttling
HTTP_TIMEOUT = int(os.getenv("STOCK_HTTP_TIMEOUT", "12"))
SLEEP_BETWEEN_CALLS = float(os.getenv("STOCK_SLEEP_BETWEEN_CALLS", "0.10"))


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

def _http_get(url: str, params: Optional[dict] = None) -> Any:
    r = requests.get(url, params=params or {}, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()

def _pct_change(new: float, old: float) -> float:
    if old == 0:
        return 0.0
    return ((new - old) / old) * 100.0


def _fmt_money(x: float) -> str:
    if x >= 1_000_000_000:
        return f"${x/1_000_000_000:.2f}B"
    if x >= 1_000_000:
        return f"${x/1_000_000:.2f}M"
    if x >= 1_000:
        return f"${x/1_000:.1f}K"
    return f"${x:,.0f}"


def _send_telegram_direct(text: str, chat_id: str, parse_mode: str = "HTML") -> None:
    """
    Direct Telegram send to a specific chat_id using MirrorStock bot token if set,
    otherwise fallback to default TELEGRAM_TOKEN.
    """
    token = MIRRORSTOCK_TELEGRAM_TOKEN or DEFAULT_TELEGRAM_TOKEN
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": False,
        }, timeout=HTTP_TIMEOUT)
    except Exception:
        return


# ============================================================
# Discovery (Polygon)
# ============================================================

def discover_candidates(limit: int = 60) -> List[Dict[str, Any]]:
    limit = max(1, int(limit))
    if STOCK_DATA_PROVIDER == "polygon":
        return _discover_polygon(limit=limit)
    return []

def _discover_polygon(limit: int = 60) -> List[Dict[str, Any]]:
    if not POLYGON_API_KEY:
        return []

    out: List[Dict[str, Any]] = []

    # 1) gainers endpoint (best)
    try:
        url = f"{POLYGON_BASE}/v2/snapshot/locale/us/markets/stocks/gainers"
        data = _http_get(url, params={"apiKey": POLYGON_API_KEY})
        tickers = data.get("tickers") if isinstance(data, dict) else None
        if isinstance(tickers, list):
            for t in tickers:
                tk = (t.get("ticker") or "").upper().strip()
                if tk:
                    out.append({"ticker": tk, "source": "gainers", "raw": t})
    except Exception:
        pass

    # 2) fallback: tickers snapshot and sort by day % change
    if not out:
        try:
            url = f"{POLYGON_BASE}/v2/snapshot/locale/us/markets/stocks/tickers"
            data = _http_get(url, params={"apiKey": POLYGON_API_KEY})
            tickers = data.get("tickers") if isinstance(data, dict) else None
            if isinstance(tickers, list):
                scored = []
                for t in tickers:
                    tk = (t.get("ticker") or "").upper().strip()
                    day = t.get("day") or {}
                    prev = t.get("prevDay") or {}
                    c = _safe_float(day.get("c"), 0.0)
                    pc = _safe_float(prev.get("c"), 0.0)
                    ch = _pct_change(c, pc)
                    if tk:
                        scored.append((ch, tk, t))
                scored.sort(key=lambda x: x[0], reverse=True)
                for ch, tk, raw in scored[: max(10, limit)]:
                    out.append({"ticker": tk, "source": "snapshot_movers", "raw": raw})
        except Exception:
            pass

    # dedupe + trim
    seen = set()
    deduped = []
    for c in out:
        tk = c.get("ticker")
        if not tk or tk in seen:
            continue
        seen.add(tk)
        deduped.append(c)
        if len(deduped) >= limit:
            break
    return deduped


# ============================================================
# Enrichment (Polygon)
# ============================================================

def enrich_ticker(ticker: str) -> Dict[str, Any]:
    ticker = (ticker or "").upper().strip()
    if not ticker:
        return {}
    if STOCK_DATA_PROVIDER == "polygon":
        return _enrich_polygon(ticker)
    return {"ticker": ticker}

def _enrich_polygon(ticker: str) -> Dict[str, Any]:
    if not POLYGON_API_KEY:
        return {}

    out: Dict[str, Any] = {
        "ticker": ticker,
        "url": f"https://www.tradingview.com/symbols/{ticker}/",
    }

    # snapshot for price/day/volume
    try:
        url = f"{POLYGON_BASE}/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}"
        snap = _http_get(url, params={"apiKey": POLYGON_API_KEY})
        data = snap.get("ticker") if isinstance(snap, dict) else None
        if isinstance(data, dict):
            day = data.get("day") or {}
            prev = data.get("prevDay") or {}

            price = _safe_float(day.get("c"), 0.0)
            prev_close = _safe_float(prev.get("c"), 0.0)
            day_change = _pct_change(price, prev_close)

            vol_day = _safe_float(day.get("v"), 0.0)
            dollar_vol_day = vol_day * price

            out.update({
                "price": price,
                "day_change_pct": day_change,
                "vol_day": vol_day,
                "dollar_vol_day": dollar_vol_day,
            })
    except Exception:
        pass

    time.sleep(SLEEP_BETWEEN_CALLS)

    # intraday aggs for 5m + 1h change + 1h volume (best effort)
    try:
        to = datetime.utcnow().strftime("%Y-%m-%d")
        frm = to
        url = f"{POLYGON_BASE}/v2/aggs/ticker/{ticker}/range/5/minute/{frm}/{to}"
        aggs = _http_get(url, params={"adjusted": "true", "sort": "desc", "limit": 30, "apiKey": POLYGON_API_KEY})
        results = aggs.get("results") if isinstance(aggs, dict) else None

        if isinstance(results, list) and len(results) >= 2:
            new_close = _safe_float(results[0].get("c"), 0.0)
            old_close = _safe_float(results[-1].get("c"), 0.0)
            out["change_5m"] = _pct_change(new_close, old_close)

        if isinstance(results, list) and len(results) >= 12:
            new_close = _safe_float(results[0].get("c"), 0.0)
            old_close = _safe_float(results[11].get("c"), 0.0)
            out["change_1h"] = _pct_change(new_close, old_close)

        if isinstance(results, list) and results:
            vol_1h = sum(_safe_float(r.get("v"), 0.0) for r in results[:12])
            price = _safe_float(out.get("price"), 0.0)
            out["vol_1h"] = vol_1h
            out["dollar_vol_1h"] = vol_1h * price
    except Exception:
        pass

    # heuristic RVOL (kept for penny gates)
    try:
        dv_day = _safe_float(out.get("dollar_vol_day"), 0.0)
        baseline = float(os.getenv("STOCK_RVOL_BASELINE_DOLLAR_VOL", "750000"))
        out["rel_vol"] = dv_day / baseline if baseline > 0 else 0.0
    except Exception:
        out["rel_vol"] = 0.0

    return out


# ============================================================
# Gates
# ============================================================

def _is_penny_band(price: float) -> bool:
    return (price >= PENNY_MIN_PRICE) and (price <= PENNY_MAX_PRICE)

def passes_penny_gates(x: Dict[str, Any]) -> bool:
    price = _safe_float(x.get("price"), 0.0)
    if price <= 0:
        return False
    if not _is_penny_band(price):
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
    """
    NEW: market-wide gain signals, not restricted to penny band.
    Targets 5–10%+ pops with participation.
    """
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
# Scoring + Formatting
# ============================================================

def rocket_score_penny(x: Dict[str, Any]) -> float:
    ch5 = max(_safe_float(x.get("change_5m"), 0.0), 0.0)
    ch1 = max(_safe_float(x.get("change_1h"), 0.0), 0.0)
    chd = max(_safe_float(x.get("day_change_pct"), 0.0), 0.0)
    dv1 = _safe_float(x.get("dollar_vol_1h"), 0.0)
    dvd = _safe_float(x.get("dollar_vol_day"), 0.0)
    rvol = _safe_float(x.get("rel_vol"), 0.0)

    score = 0.0
    score += ch5 * 1.2
    score += ch1 * 0.8
    score += chd * 0.35
    score += min(dv1 / 500_000.0, 8.0) * 10.0
    score += min(dvd / 2_000_000.0, 8.0) * 8.0
    score += min(rvol, 10.0) * 6.0
    return float(score)

def score_market_gainer(x: Dict[str, Any]) -> float:
    ch5 = max(_safe_float(x.get("change_5m"), 0.0), 0.0)
    ch1 = max(_safe_float(x.get("change_1h"), 0.0), 0.0)
    chd = max(_safe_float(x.get("day_change_pct"), 0.0), 0.0)
    dv1 = _safe_float(x.get("dollar_vol_1h"), 0.0)
    dvd = _safe_float(x.get("dollar_vol_day"), 0.0)

    # bias slightly toward 1h pop + real participation
    return (
        ch5 * 0.8 +
        ch1 * 1.2 +
        chd * 0.25 +
        (dv1 / 300_000.0) +
        (dvd / 2_000_000.0)
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

    return (
        f"<b>📈 MirrorStock Rocket Alert</b>\n"
        f"Ticker: <b>{ticker}</b>\n"
        f"Gate: <b>{gate}</b>\n"
        f"Price: ${price:.4f}\n"
        f"5m: {ch5:.2f}% | 1h: {ch1:.2f}% | Day: {chd:.2f}%\n"
        f"Dollar Vol 1h: {_fmt_money(dv1)} | Day: {_fmt_money(dvd)}\n"
        f"RVOL (heuristic): {rvol:.2f}\n"
        f"Acceleration: <b>{accel_hint}</b>\n\n"
        f"🔎 Review catalysts/news + spreads/halts. Penny movers can reverse violently.\n"
        f"<a href='{url}'>Open chart</a>\n\n"
        f"⚠️ Educational alert only. Use strict risk controls."
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

    return (
        f"<b>📊 MirrorStock Market Gainer</b>\n"
        f"Ticker: <b>{ticker}</b>\n"
        f"Price: ${price:.4f}\n"
        f"5m: {ch5:.2f}% | 1h: {ch1:.2f}% | Day: {chd:.2f}%\n"
        f"Dollar Vol 1h: {_fmt_money(dv1)} | Day: {_fmt_money(dvd)}\n"
        f"Acceleration: <b>{accel_hint}</b>\n\n"
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

        ok = passes_penny_gates(enriched) or moonshot_exception(enriched)
        if not ok:
            continue

        record_snapshot("mirrorstock_detector", {
            "address": tk,
            "symbol": tk,
            "priceUsd": _safe_float(enriched.get("price"), 0.0),
            "liquidityUsd": 0.0,
            "volumeH1": _safe_float(enriched.get("dollar_vol_1h"), 0.0),
            "volumeH24": _safe_float(enriched.get("dollar_vol_day"), 0.0),
            "changeM5": _safe_float(enriched.get("change_5m"), 0.0),
            "changeH1": _safe_float(enriched.get("change_1h"), 0.0),
            "changeH24": _safe_float(enriched.get("day_change_pct"), 0.0),
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

        if not passes_market_gainer_gates(enriched):
            continue

        record_snapshot("mirrorstock_market", {
            "address": tk,
            "symbol": tk,
            "priceUsd": _safe_float(enriched.get("price"), 0.0),
            "liquidityUsd": 0.0,
            "volumeH1": _safe_float(enriched.get("dollar_vol_1h"), 0.0),
            "volumeH24": _safe_float(enriched.get("dollar_vol_day"), 0.0),
            "changeM5": _safe_float(enriched.get("change_5m"), 0.0),
            "changeH1": _safe_float(enriched.get("change_1h"), 0.0),
            "changeH24": _safe_float(enriched.get("day_change_pct"), 0.0),
            "url": enriched.get("url"),
            "ts": _now_iso(),
        })

        enriched["source"] = c.get("source")
        found.append(enriched)
        time.sleep(SLEEP_BETWEEN_CALLS)

    found.sort(key=score_market_gainer, reverse=True)
    return found


def push_mirrorstock_alerts():
    """
    Runs:
      1) Penny rockets (strict)
      2) Market gainers (5–10%+ signals) (NEW)
    Routes alerts to MIRRORSTOCK_TELEGRAM_CHAT_ID using MIRRORSTOCK_TELEGRAM_TOKEN if provided.
    """
    print("[SCHEDULER] Running MirrorStock Detector...")

    penny = detect_penny_rockets(limit=RADAR_LIMIT)
    market = detect_market_gainers(limit=RADAR_LIMIT)

    if not penny and not market:
        print("[MirrorStock] No standout signals.")
        return

    sent = 0
    seen = set()

    # 1) send penny rockets first
    for x in penny[:MAX_ALERTS]:
        tk = x.get("ticker")
        if tk in seen:
            continue
        seen.add(tk)

        msg = format_penny_alert(x)

        try:
            add_alert("mirrorstock_detector", {
                "symbol": tk,
                "address": tk,
                "url": x.get("url"),
                "message": msg,
            })
        except Exception:
            pass

        if MIRRORSTOCK_CHAT_ID:
            _send_telegram_direct(msg, chat_id=MIRRORSTOCK_CHAT_ID, parse_mode="HTML")
        else:
            send_telegram_message(msg)

        sent += 1
        print(f"[MirrorStock] Sent penny alert for {tk}")

    # 2) then market gainers
    for x in market[:MARKET_MAX_ALERTS]:
        tk = x.get("ticker")
        if tk in seen:
            continue
        seen.add(tk)

        msg = format_market_alert(x)

        try:
            add_alert("mirrorstock_market", {
                "symbol": tk,
                "address": tk,
                "url": x.get("url"),
                "message": msg,
            })
        except Exception:
            pass

        if MIRRORSTOCK_CHAT_ID:
            _send_telegram_direct(msg, chat_id=MIRRORSTOCK_CHAT_ID, parse_mode="HTML")
        else:
            send_telegram_message(msg)

        sent += 1
        print(f"[MirrorStock] Sent market alert for {tk}")

    print(f"[MirrorStock] Total alerts sent: {sent}")


if __name__ == "__main__":
    push_mirrorstock_alerts()
