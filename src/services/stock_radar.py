# src/services/stock_radar.py
"""
Stock Radar (Discovery + Enrichment + Aggs)
------------------------------------------
Provider-agnostic helpers for MirrorStock.

What this file gives you:
✅ discover_candidates(limit)  -> [{"ticker": "XYZ", "source": "...", "raw": {...}}, ...]
✅ enrich_ticker("XYZ")        -> dict with price, changes, dollar volumes, rel_vol, url, aggs
✅ get_aggs_5m_desc("XYZ")     -> list of Polygon agg bars (newest-first)

Primary provider implemented: Polygon (free-ish tier depending on plan).
Safe-fails if key missing or API errors.

Educational tooling only. Not trade advice.
"""

from __future__ import annotations

import os
import time
import requests
from datetime import datetime
from typing import Any, Dict, List, Optional


# ============================================================
# Config
# ============================================================

STOCK_DATA_PROVIDER = os.getenv("STOCK_DATA_PROVIDER", "polygon").lower().strip()

POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "").strip()
POLYGON_BASE = "https://api.polygon.io"

HTTP_TIMEOUT = int(os.getenv("STOCK_HTTP_TIMEOUT", "12"))
SLEEP_BETWEEN_CALLS = float(os.getenv("STOCK_SLEEP_BETWEEN_CALLS", "0.10"))

# Heuristic RVOL baseline (dollar volume/day)
RVOL_BASELINE_DOLLAR_VOL = float(os.getenv("STOCK_RVOL_BASELINE_DOLLAR_VOL", "750000"))

# Agg settings (5m bars)
CHART_AGG_MINUTES = int(os.getenv("STOCK_CHART_AGG_MINUTES", "5"))
CHART_BARS = int(os.getenv("STOCK_CHART_BARS", "78"))


# ============================================================
# Helpers
# ============================================================

def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default

def _pct_change(new: float, old: float) -> float:
    if old == 0:
        return 0.0
    return ((new - old) / old) * 100.0

def _http_get(url: str, params: Optional[dict] = None) -> Any:
    r = requests.get(url, params=params or {}, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r.json()

def _today_utc_ymd() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


# ============================================================
# Public API
# ============================================================

def discover_candidates(limit: int = 60) -> List[Dict[str, Any]]:
    """
    Returns [{"ticker": "XYZ", "source": "...", "raw": {...}}, ...]
    """
    limit = max(1, int(limit))
    if STOCK_DATA_PROVIDER == "polygon":
        return _discover_polygon(limit=limit)
    return []

def enrich_ticker(ticker: str) -> Dict[str, Any]:
    """
    Returns a dict enriched with:
      ticker, url,
      price, day_change_pct, dollar_vol_day,
      change_5m, change_1h, dollar_vol_1h,
      rel_vol,
      _aggs_5m_desc (optional)
    """
    tk = (ticker or "").upper().strip()
    if not tk:
        return {}
    if STOCK_DATA_PROVIDER == "polygon":
        return _enrich_polygon(tk)
    return {"ticker": tk, "url": f"https://www.tradingview.com/symbols/{tk}/"}

def get_aggs_5m_desc(ticker: str, bars: int = CHART_BARS) -> List[Dict[str, Any]]:
    tk = (ticker or "").upper().strip()
    if not tk:
        return []
    if STOCK_DATA_PROVIDER == "polygon":
        return _polygon_aggs_minutes_desc(tk, minutes=CHART_AGG_MINUTES, limit=int(bars))
    return []


# ============================================================
# Polygon: Discovery
# ============================================================

def _discover_polygon(limit: int = 60) -> List[Dict[str, Any]]:
    if not POLYGON_API_KEY:
        return []

    out: List[Dict[str, Any]] = []

    # 1) gainers endpoint
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
# Polygon: Aggs
# ============================================================

def _polygon_aggs_minutes_desc(ticker: str, minutes: int, limit: int) -> List[Dict[str, Any]]:
    if not POLYGON_API_KEY:
        return []
    try:
        to = _today_utc_ymd()
        frm = to
        url = f"{POLYGON_BASE}/v2/aggs/ticker/{ticker}/range/{int(minutes)}/minute/{frm}/{to}"
        aggs = _http_get(url, params={
            "adjusted": "true",
            "sort": "desc",
            "limit": int(limit),
            "apiKey": POLYGON_API_KEY
        })
        results = aggs.get("results") if isinstance(aggs, dict) else None
        return results if isinstance(results, list) else []
    except Exception:
        return []


# ============================================================
# Polygon: Enrichment
# ============================================================

def _enrich_polygon(ticker: str) -> Dict[str, Any]:
    if not POLYGON_API_KEY:
        return {}

    out: Dict[str, Any] = {
        "ticker": ticker,
        "url": f"https://www.tradingview.com/symbols/{ticker}/",
    }

    # Snapshot: price/day/volume
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

    # Aggs: compute *true* 5m and 1h changes + 1h dollar vol
    aggs = _polygon_aggs_minutes_desc(ticker, minutes=CHART_AGG_MINUTES, limit=max(30, CHART_BARS))
    if aggs:
        # newest-first
        if len(aggs) >= 2:
            c0 = _safe_float(aggs[0].get("c"), 0.0)
            c1 = _safe_float(aggs[1].get("c"), 0.0)
            out["change_5m"] = _pct_change(c0, c1)

        # 1h = 12 bars of 5m
        if len(aggs) >= 13:
            c0 = _safe_float(aggs[0].get("c"), 0.0)
            c12 = _safe_float(aggs[12].get("c"), 0.0)
            out["change_1h"] = _pct_change(c0, c12)

        vol_1h = sum(_safe_float(r.get("v"), 0.0) for r in aggs[:12])
        price = _safe_float(out.get("price"), 0.0)
        out["vol_1h"] = vol_1h
        out["dollar_vol_1h"] = vol_1h * price

        out["_aggs_5m_desc"] = aggs[:CHART_BARS]

    # Heuristic rel vol
    try:
        dv_day = _safe_float(out.get("dollar_vol_day"), 0.0)
        out["rel_vol"] = dv_day / RVOL_BASELINE_DOLLAR_VOL if RVOL_BASELINE_DOLLAR_VOL > 0 else 0.0
    except Exception:
        out["rel_vol"] = 0.0

    return out
