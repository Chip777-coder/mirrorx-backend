# src/services/mirrorstock_detector.py
"""
MirrorStock Detector (Penny Rocket Mode)
----------------------------------------
MirrorX-style pipeline, tuned for penny stocks:

1) Discovery (universe building):
   - "Top gainers" / "unusual volume" / "market movers" endpoints (API-dependent)
2) Enrich (quotes + volume)
3) Gates (quality filters for penny stocks)
4) Snapshot store (acceleration tracking)
5) Alerts (Telegram + alerts_store)

Educational tooling only. Not trade advice.
"""

from __future__ import annotations

import os
import time
import math
import requests
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.services.telegram_alerts import send_telegram_message
from src.services.movers_store import record_snapshot, compute_acceleration

# Optional alert store (safe if file doesn't exist)
try:
    from src.services.alerts_store import add_alert  # type: ignore
except Exception:
    def add_alert(_source: str, _payload: dict):  # fallback no-op
        return


# ============================================================
# Config (env-driven)
# ============================================================

# Where to post (separate channel recommended)
MIRRORSTOCK_CHAT_ID = os.getenv("MIRRORSTOCK_TELEGRAM_CHAT_ID", "").strip()

# --- Penny stock "focus band"
# Keep this narrow if you want true penny specialization.
PENNY_MAX_PRICE = float(os.getenv("STOCK_PENNY_MAX_PRICE", "5.00"))
PENNY_MIN_PRICE = float(os.getenv("STOCK_PENNY_MIN_PRICE", "0.10"))

# --- Quality gates (tune aggressively to avoid junk)
MIN_DOLLAR_VOL_1H = float(os.getenv("STOCK_MIN_DOLLAR_VOL_1H", "250000"))   # $250k
MIN_DOLLAR_VOL_DAY = float(os.getenv("STOCK_MIN_DOLLAR_VOL_DAY", "1500000")) # $1.5M
MIN_REL_VOL = float(os.getenv("STOCK_MIN_REL_VOL", "2.0"))                 # RVOL >= 2
MIN_PCT_CHANGE_5M = float(os.getenv("STOCK_MIN_PCT_CHANGE_5M", "1.0"))      # 5m change >= 1%
MIN_PCT_CHANGE_1H = float(os.getenv("STOCK_MIN_PCT_CHANGE_1H", "5.0"))      # 1h change >= 5%
MIN_PCT_CHANGE_DAY = float(os.getenv("STOCK_MIN_PCT_CHANGE_DAY", "15.0"))   # day change >= 15%

# --- Moonshot exception rules (penny style)
# Allows catching insane movers even if some gates fail, but still guards against pure noise.
MOONSHOT_MIN_PCT_DAY = float(os.getenv("STOCK_MOONSHOT_MIN_PCT_DAY", "80.0"))   # +80% day
MOONSHOT_MIN_DOLLAR_VOL_DAY = float(os.getenv("STOCK_MOONSHOT_MIN_DOLLAR_VOL_DAY", "500000"))  # $500k day
MOONSHOT_MIN_PRICE = float(os.getenv("STOCK_MOONSHOT_MIN_PRICE", "0.03"))      # ignore sub-3c garbage

# How many alerts per run
MAX_ALERTS = int(os.getenv("STOCK_MAX_ALERTS", "5"))

# Discovery scan size
RADAR_LIMIT = int(os.getenv("STOCK_RADAR_LIMIT", "60"))

# API selection
STOCK_DATA_PROVIDER = os.getenv("STOCK_DATA_PROVIDER", "polygon").lower().strip()

# Polygon (recommended)
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "").strip()
POLYGON_BASE = "https://api.polygon.io"

# Optional throttling (avoid rate limits)
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

def _safe_int(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        return int(float(x))
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

def _market_session_hint() -> str:
    # simple hint, not exchange-perfect
    # You can later swap to real market calendar logic.
    return "US"


# ============================================================
# Discovery
# ============================================================

def discover_candidates(limit: int = 60) -> List[Dict[str, Any]]:
    """
    Return a list of candidate tickers to evaluate.
    We keep this provider-specific, but output shape is stable:
      [{"ticker":"XYZ","source":"gainers"}, ...]
    """
    limit = max(1, int(limit))

    if STOCK_DATA_PROVIDER == "polygon":
        return _discover_polygon(limit=limit)

    # Fallback stub (so code doesn't break if provider not yet configured)
    return []


def _discover_polygon(limit: int = 60) -> List[Dict[str, Any]]:
    """
    Polygon has "gainers/losers" style endpoints under /v2/snapshot/locale/us/markets/stocks/gainers
    and snapshots for tickers. Response shapes can vary; handle defensively.

    NOTE: if your plan doesn't include this endpoint, you'll replace this with whatever you have
    (e.g., "most active", "unusual volume", scanner endpoints, etc.)
    """
    if not POLYGON_API_KEY:
        return []

    out: List[Dict[str, Any]] = []

    # 1) Try gainers endpoint
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

    # 2) If empty, try "tickers snapshot" and derive movers (best effort)
    # Some Polygon plans support snapshots endpoint:
    # /v2/snapshot/locale/us/markets/stocks/tickers
    if not out:
        try:
            url = f"{POLYGON_BASE}/v2/snapshot/locale/us/markets/stocks/tickers"
            data = _http_get(url, params={"apiKey": POLYGON_API_KEY})
            tickers = data.get("tickers") if isinstance(data, dict) else None
            if isinstance(tickers, list):
                # crude mover scoring: percent change from day's open/close if available
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

    # Dedupe + trim
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
# Enrichment + Analysis
# ============================================================

def enrich_ticker(ticker: str) -> Dict[str, Any]:
    """
    Return normalized market fields needed for gating/scoring.

    Output shape (stable):
      {
        ticker, price, day_change_pct, vol_day, dollar_vol_day,
        vol_1h, dollar_vol_1h, rel_vol, change_5m, change_1h,
        session, url
      }

    Provider-specific implementations can fill what they can.
    Missing fields default to 0.
    """
    ticker = (ticker or "").upper().strip()
    if not ticker:
        return {}

    if STOCK_DATA_PROVIDER == "polygon":
        return _enrich_polygon(ticker)

    return {"ticker": ticker}


def _enrich_polygon(ticker: str) -> Dict[str, Any]:
    if not POLYGON_API_KEY:
        return {}

    # We'll use:
    # - snapshot ticker endpoint (day + prevDay)
    # - optional aggregates for 5m and 1h intraday if available
    #   /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}
    # Intraday aggregation can be heavy; we keep it minimal and best-effort.

    out: Dict[str, Any] = {
        "ticker": ticker,
        "session": _market_session_hint(),
        "url": f"https://www.tradingview.com/symbols/{ticker}/",  # safe default
    }

    # 1) Snapshot for price/day/volume
    try:
        url = f"{POLYGON_BASE}/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}"
        snap = _http_get(url, params={"apiKey": POLYGON_API_KEY})
        data = snap.get("ticker") if isinstance(snap, dict) else None
        if isinstance(data, dict):
            day = data.get("day") or {}
            prev = data.get("prevDay") or {}

            price = _safe_float((data.get("min") or {}).get("o"), 0.0)  # fallback
            # better: day close if present
            price = _safe_float(day.get("c"), price)

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

    # Throttle a hair
    time.sleep(SLEEP_BETWEEN_CALLS)

    # 2) Intraday aggregates (best effort)
    # We compute approximate 5m change + 1h change by pulling recent candles.
    # If your Polygon plan doesn't allow this, it will just stay 0 and still work.
    try:
        # last ~1 day window; polygon uses dates. We'll use "today" UTC (best effort).
        # You can improve by using exchange timezone later.
        to = datetime.utcnow().strftime("%Y-%m-%d")
        frm = to  # same day
        url = f"{POLYGON_BASE}/v2/aggs/ticker/{ticker}/range/5/minute/{frm}/{to}"
        aggs = _http_get(url, params={"adjusted": "true", "sort": "desc", "limit": 30, "apiKey": POLYGON_API_KEY})
        results = aggs.get("results") if isinstance(aggs, dict) else None

        if isinstance(results, list) and len(results) >= 2:
            # newest first because sort=desc
            newest = results[0]
            older = results[-1]
            new_close = _safe_float(newest.get("c"), 0.0)
            old_close = _safe_float(older.get("c"), 0.0)
            ch_5m = _pct_change(new_close, old_close)
            out["change_5m"] = ch_5m

        # 1h: reuse 5m candles (12 candles ~ 60m)
        if isinstance(results, list) and len(results) >= 12:
            new_close = _safe_float(results[0].get("c"), 0.0)
            old_close = _safe_float(results[11].get("c"), 0.0)
            ch_1h = _pct_change(new_close, old_close)
            out["change_1h"] = ch_1h
    except Exception:
        pass

    # 3) Approx 1h volume + RVOL (best-effort)
    # Polygon doesn't always provide average volume without another endpoint.
    # We'll approximate:
    # - vol_1h: sum last 12x5m volumes if we have them
    # - rel_vol: dollar_vol_day vs (a simple heuristic baseline) to avoid missing RVOL entirely
    try:
        # if we have recent aggs in scope, we don't; so we re-fetch small limit.
        to = datetime.utcnow().strftime("%Y-%m-%d")
        frm = to
        url = f"{POLYGON_BASE}/v2/aggs/ticker/{ticker}/range/5/minute/{frm}/{to}"
        aggs = _http_get(url, params={"adjusted": "true", "sort": "desc", "limit": 12, "apiKey": POLYGON_API_KEY})
        results = aggs.get("results") if isinstance(aggs, dict) else None
        if isinstance(results, list) and results:
            vol_1h = sum(_safe_float(r.get("v"), 0.0) for r in results[:12])
            price = _safe_float(out.get("price"), 0.0)
            out["vol_1h"] = vol_1h
            out["dollar_vol_1h"] = vol_1h * price

        # Heuristic RVOL: compare current day dollar vol to a soft baseline
        # (Replace later with a real 10/20-day average volume endpoint when you provide your API.)
        dv_day = _safe_float(out.get("dollar_vol_day"), 0.0)
        baseline = float(os.getenv("STOCK_RVOL_BASELINE_DOLLAR_VOL", "750000"))  # $750k baseline
        out["rel_vol"] = dv_day / baseline if baseline > 0 else 0.0
    except Exception:
        pass

    return out


# ============================================================
# Gates + Moonshot exceptions
# ============================================================

def _is_penny_band(price: float) -> bool:
    return (price >= PENNY_MIN_PRICE) and (price <= PENNY_MAX_PRICE)

def passes_gates(x: Dict[str, Any]) -> bool:
    """
    Standard penny gates to reduce noise.
    """
    price = _safe_float(x.get("price"), 0.0)
    if price <= 0:
        return False

    # Primary scope: penny band
    if not _is_penny_band(price):
        return False

    dv1h = _safe_float(x.get("dollar_vol_1h"), 0.0)
    dvday = _safe_float(x.get("dollar_vol_day"), 0.0)
    rvol = _safe_float(x.get("rel_vol"), 0.0)

    ch5 = _safe_float(x.get("change_5m"), 0.0)
    ch1 = _safe_float(x.get("change_1h"), 0.0)
    chd = _safe_float(x.get("day_change_pct"), 0.0)

    # Movement requirement
    moving = (ch5 >= MIN_PCT_CHANGE_5M) or (ch1 >= MIN_PCT_CHANGE_1H) or (chd >= MIN_PCT_CHANGE_DAY)
    if not moving:
        return False

    # Participation requirement (avoid ghost moves)
    if not (dv1h >= MIN_DOLLAR_VOL_1H or dvday >= MIN_DOLLAR_VOL_DAY):
        return False

    # RVOL quality
    if rvol < MIN_REL_VOL:
        return False

    return True


def moonshot_exception(x: Dict[str, Any]) -> bool:
    """
    Moonshot exception: catch extreme day movers in penny space
    even if some standard gates fail, but keep safety guards.

    Intended to catch those 500% / 2000% rippers early.
    """
    price = _safe_float(x.get("price"), 0.0)
    chd = _safe_float(x.get("day_change_pct"), 0.0)
    dvday = _safe_float(x.get("dollar_vol_day"), 0.0)

    if price < MOONSHOT_MIN_PRICE:
        return False

    if chd >= MOONSHOT_MIN_PCT_DAY and dvday >= MOONSHOT_MIN_DOLLAR_VOL_DAY:
        return True

    return False


# ============================================================
# Scoring + Alert formatting
# ============================================================

def rocket_score(x: Dict[str, Any]) -> float:
    """
    Educational scoring. Not trade advice.
    We rank:
      - short-term change (5m, 1h)
      - day % change
      - dollar volume (1h + day)
      - RVOL
    """
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
    score += min(dv1 / 500_000.0, 8.0) * 10.0    # up to 80
    score += min(dvd / 2_000_000.0, 8.0) * 8.0   # up to 64
    score += min(rvol, 10.0) * 6.0               # up to 60
    return float(score)


def _fmt_money(x: float) -> str:
    if x >= 1_000_000_000:
        return f"${x/1_000_000_000:.2f}B"
    if x >= 1_000_000:
        return f"${x/1_000_000:.2f}M"
    if x >= 1_000:
        return f"${x/1_000:.1f}K"
    return f"${x:,.0f}"


def format_stock_alert(x: Dict[str, Any]) -> str:
    ticker = x.get("ticker", "UNKNOWN")
    price = _safe_float(x.get("price"), 0.0)

    ch5 = _safe_float(x.get("change_5m"), 0.0)
    ch1 = _safe_float(x.get("change_1h"), 0.0)
    chd = _safe_float(x.get("day_change_pct"), 0.0)

    dv1 = _safe_float(x.get("dollar_vol_1h"), 0.0)
    dvd = _safe_float(x.get("dollar_vol_day"), 0.0)
    rvol = _safe_float(x.get("rel_vol"), 0.0)

    accel = compute_acceleration(ticker)  # using ticker as "address key"
    accel_hint = accel.get("accel_hint", "n/a")

    gate = "normal"
    if moonshot_exception(x) and not passes_gates(x):
        gate = "moonshot_exception"

    url = x.get("url") or f"https://www.tradingview.com/symbols/{ticker}/"

    msg = (
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
    return msg


# ============================================================
# Main pipeline
# ============================================================

def detect_penny_rockets(limit: int = RADAR_LIMIT) -> List[Dict[str, Any]]:
    """
    1) Discover tickers
    2) Enrich
    3) Apply gates or moonshot exceptions
    4) Record snapshots for acceleration
    5) Rank
    """
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

        ok = passes_gates(enriched) or moonshot_exception(enriched)
        if not ok:
            continue

        # record snapshot (use ticker as the key)
        record_snapshot("mirrorstock_detector", {
            "address": tk,  # reuse field name; it's just the key used for acceleration
            "symbol": tk,
            "priceUsd": _safe_float(enriched.get("price"), 0.0),
            "liquidityUsd": 0.0,  # N/A for stocks; keep schema stable
            "volumeH1": _safe_float(enriched.get("dollar_vol_1h"), 0.0),
            "volumeH24": _safe_float(enriched.get("dollar_vol_day"), 0.0),
            "changeM5": _safe_float(enriched.get("change_5m"), 0.0),
            "changeH1": _safe_float(enriched.get("change_1h"), 0.0),
            "changeH24": _safe_float(enriched.get("day_change_pct"), 0.0),
            "url": enriched.get("url"),
            "ts": _now_iso(),
        })

        # attach source
        enriched["source"] = c.get("source")
        found.append(enriched)

        time.sleep(SLEEP_BETWEEN_CALLS)

    found.sort(key=rocket_score, reverse=True)
    return found


def push_mirrorstock_alerts():
    """
    Run detector and push top alerts.
    Uses MirrorStock chat ID if set, otherwise falls back to your default telegram config.
    """
    print("[SCHEDULER] Running MirrorStock Detector...")
    detected = detect_penny_rockets(limit=RADAR_LIMIT)

    if not detected:
        print("[MirrorStock] No standout penny rockets.")
        return

    top = detected[:MAX_ALERTS]
    for x in top:
        msg = format_stock_alert(x)

        # store
        try:
            add_alert("mirrorstock_detector", {
                "symbol": x.get("ticker"),
                "address": x.get("ticker"),
                "url": x.get("url"),
                "message": msg,
            })
        except Exception:
            pass

        # send message
        # If you want to route to a separate channel without changing telegram_alerts.py,
        # you can update telegram_alerts.py to accept optional chat_id.
        #
        # For now: if MIRRORSTOCK_CHAT_ID is set, we append it into env routing by temporarily
        # using a lightweight direct call pattern (optional).
        if MIRRORSTOCK_CHAT_ID:
            _send_telegram_direct(msg, chat_id=MIRRORSTOCK_CHAT_ID, parse_mode="HTML")
        else:
            send_telegram_message(msg)

        print(f"[MirrorStock] Sent alert for {x.get('ticker')}")


def _send_telegram_direct(text: str, chat_id: str, parse_mode: str = "HTML") -> None:
    """
    Direct Telegram send to specific chat_id (channel) without touching your existing sender.
    Requires TELEGRAM_TOKEN in env.
    """
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
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


if __name__ == "__main__":
    push_mirrorstock_alerts()
