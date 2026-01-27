# src/services/stock_radar.py
"""
Stock Radar (Polygon)
--------------------
Provides:
  - discover_candidates(limit)
  - enrich_ticker(ticker)

Outputs are shaped similarly to MirrorX enrichment so detector can score + alert.

Educational tooling only. Not trade advice.
"""

from __future__ import annotations

import os
import time
import requests
from datetime import datetime
from typing import Any, Dict, List, Optional

POLYGON_BASE = "https://api.polygon.io"
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "").strip()

HTTP_TIMEOUT = int(os.getenv("STOCK_HTTP_TIMEOUT", "12"))
SLEEP_BETWEEN_CALLS = float(os.getenv("STOCK_SLEEP_BETWEEN_CALLS", "0.10"))

# Chart data defaults (5m candles)
CHART_AGG_MINUTES = int(os.getenv("STOCK_CHART_AGG_MINUTES", "5"))
CHART_BARS = int(os.getenv("STOCK_CHART_BARS", "78"))  # ~1 day of 5m bars


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


def discover_candidates(limit: int = 60) -> List[Dict[str, Any]]:
    """
    Returns list like:
      [{ "ticker": "XYZ", "source": "gainers", "raw": {...} }, ...]
    """
    limit = max(1, int(limit))
    if not POLYGON_API_KEY:
        return []

    out: List[Dict[str, Any]] = []

    # 1) best: gainers snapshot endpoint
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

    # 2) fallback: all tickers snapshot then sort by day % change
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
                for _, tk, raw in scored[: max(10, limit)]:
                    out.append({"ticker": tk, "source": "snapshot_movers", "raw": raw})
        except Exception:
            pass

    # dedupe + trim
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for c in out:
        tk = c.get("ticker")
        if not tk or tk in seen:
            continue
        seen.add(tk)
        deduped.append(c)
        if len(deduped) >= limit:
            break

    return deduped


def _polygon_aggs(ticker: str, minutes: int, limit: int) -> List[Dict[str, Any]]:
    """
    Returns newest-first list of bars (desc).
    """
    if not POLYGON_API_KEY:
        return []

    try:
        # "today" UTC date string
        to = datetime.utcnow().strftime("%Y-%m-%d")
        frm = to
        url = f"{POLYGON_BASE}/v2/aggs/ticker/{ticker}/range/{minutes}/minute/{frm}/{to}"
        data = _http_get(url, params={
            "adjusted": "true",
            "sort": "desc",
            "limit": int(limit),
            "apiKey": POLYGON_API_KEY,
        })
        results = data.get("results") if isinstance(data, dict) else None
        return results if isinstance(results, list) else []
    except Exception:
        return []


def enrich_ticker(ticker: str) -> Dict[str, Any]:
    """
    Returns dict like:
      {
        ticker, url, price, day_change_pct,
        vol_day, dollar_vol_day,
        change_5m, change_1h,
        vol_1h, dollar_vol_1h,
        rel_vol,
        _aggs_5m_desc: [...]
      }
    """
    ticker = (ticker or "").upper().strip()
    if not ticker or not POLYGON_API_KEY:
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

    # intraday aggs (5m bars) to compute true 5m + 1h changes and 1h volume
    bars = _polygon_aggs(ticker, minutes=CHART_AGG_MINUTES, limit=max(30, CHART_BARS))
    if bars:
        # True 5m change = bar0 close vs bar1 close
        if len(bars) >= 2:
            c0 = _safe_float(bars[0].get("c"), 0.0)
            c1 = _safe_float(bars[1].get("c"), 0.0)
            out["change_5m"] = _pct_change(c0, c1)

        # True 1h change = bar0 close vs bar12 close (12 * 5m)
        if len(bars) >= 13:
            c0 = _safe_float(bars[0].get("c"), 0.0)
            c12 = _safe_float(bars[12].get("c"), 0.0)
            out["change_1h"] = _pct_change(c0, c12)

        # 1h volume = sum first 12 bars
        vol_1h = sum(_safe_float(b.get("v"), 0.0) for b in bars[:12])
        price = _safe_float(out.get("price"), 0.0)
        out["vol_1h"] = vol_1h
        out["dollar_vol_1h"] = vol_1h * price

        # Keep bars for chart rendering (newest-first)
        out["_aggs_5m_desc"] = bars[:CHART_BARS]

    # heuristic RVOL
    try:
        dv_day = _safe_float(out.get("dollar_vol_day"), 0.0)
        baseline = float(os.getenv("STOCK_RVOL_BASELINE_DOLLAR_VOL", "750000"))
        out["rel_vol"] = dv_day / baseline if baseline > 0 else 0.0
    except Exception:
        out["rel_vol"] = 0.0

    return out
