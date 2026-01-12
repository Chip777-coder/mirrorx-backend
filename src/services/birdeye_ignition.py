# src/services/birdeye_ignition.py
"""
Birdeye Ignition Engine (MirrorX Rocket Add-on)
----------------------------------------------
Consumes 1m OHLCV updates (from Birdeye WS) and detects early-stage "ignite" events.

Goal: catch the *start* of 200% day moves before they become 1k%+.

Educational tooling only. Not trade advice.
"""

from __future__ import annotations
import os
import time
from typing import Dict, Any, Optional

from src.services.movers_store import record_snapshot, compute_acceleration

# Optional alert store
try:
    from src.services.alerts_store import add_alert  # type: ignore
except Exception:
    def add_alert(_source: str, _payload: dict):
        return

# -------------------------
# Gates (tunable env vars)
# -------------------------
IGNITE_MIN_LIQ_USD = float(os.getenv("IGNITE_MIN_LIQ_USD", "15000"))          # if you enrich liquidity elsewhere
IGNITE_MIN_VOL_1M = float(os.getenv("IGNITE_MIN_VOL_1M", "5000"))            # $ volume in 1m candle
IGNITE_MIN_VOL_5M = float(os.getenv("IGNITE_MIN_VOL_5M", "25000"))           # $ volume across recent 5m
IGNITE_MIN_CH_5M = float(os.getenv("IGNITE_MIN_CH_5M", "8"))                 # % change over ~5m
IGNITE_MIN_CH_1H = float(os.getenv("IGNITE_MIN_CH_1H", "25"))                # % change over 1h-ish

# Moonshot exception: huge impulse even if some fields missing
MOONSHOT_MIN_CH_5M = float(os.getenv("IGNITE_MOONSHOT_MIN_CH_5M", "25"))      # % change in 5m
MOONSHOT_MIN_VOL_5M = float(os.getenv("IGNITE_MOONSHOT_MIN_VOL_5M", "50000")) # $ volume in 5m

# Cooldown per address to avoid spam
ALERT_COOLDOWN_SECONDS = int(os.getenv("IGNITE_ALERT_COOLDOWN_SECONDS", "1800"))  # 30 min

# In-memory cooldown map (best effort)
_last_alert_ts: Dict[str, float] = {}


def _cooldown_ok(key: str) -> bool:
    now = time.time()
    last = _last_alert_ts.get(key, 0.0)
    if now - last < ALERT_COOLDOWN_SECONDS:
        return False
    _last_alert_ts[key] = now
    return True


def ingest_ohlcv(event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    event example (Birdeye PRICE_DATA):
      {
        "type":"PRICE_DATA",
        "data":{
          "o":..., "h":..., "l":..., "c":..., "v":...,
          "type":"1m", "unixTime":..., "symbol":"SOL", "address":"..."
        }
      }
    Returns an alert payload dict when ignition detected, else None.
    """
    data = event.get("data") or {}
    addr = (data.get("address") or "").strip()
    if not addr:
        return None

    o = float(data.get("o") or 0)
    c = float(data.get("c") or 0)
    v = float(data.get("v") or 0)  # Birdeye sends volume for the interval (may be token amount)
    chart_type = data.get("type") or "1m"
    symbol = (data.get("symbol") or "UNKNOWN").strip()

    # We treat (c-o)/o as "1m change", then use movers_store to infer acceleration
    ch_1m = ((c - o) / o * 100.0) if o else 0.0

    # Record snapshot into movers_store
    record_snapshot("birdeye_ws", {
        "address": addr,
        "symbol": symbol,
        "priceUsd": c,
        "liquidityUsd": 0.0,    # can be enriched later
        "volumeH1": 0.0,        # can be enriched later
        "volumeH24": 0.0,       # can be enriched later
        "changeM5": 0.0,        # we’ll infer with acceleration + optional rolling buffers
        "changeH1": 0.0,
        "changeH24": 0.0,
        "rawVol": v,
        "ch1m": ch_1m,
        "chartType": chart_type,
        "unixTime": data.get("unixTime"),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })

    # Compute acceleration (from your existing store)
    accel = compute_acceleration(addr)
    hint = accel.get("accel_hint", "flat")

    # We can’t get true 5m/1h change from only one candle without storing rolling prices.
    # But we can use acceleration + a strong 1m impulse as ignition proxy.
    # (If you want true 5m/1h from WS, we can add a tiny rolling window later.)
    is_impulse = (ch_1m >= (IGNITE_MIN_CH_5M / 5.0))  # approx: 8% in 5m ~ 1.6%/min

    # Moonshot exception (big sudden candle)
    moonshot = (ch_1m >= (MOONSHOT_MIN_CH_5M / 5.0))  # proxy

    # If volume is token volume not USD, you can disable these gates or swap to tx websocket later
    vol_gate = v >= IGNITE_MIN_VOL_1M

    ignite = (hint == "accelerating" and is_impulse and vol_gate)
    if moonshot and vol_gate:
        ignite = True

    if not ignite:
        return None

    # Cooldown to avoid spam
    if not _cooldown_ok(addr):
        return None

    payload = {
        "address": addr,
        "symbol": symbol,
        "price": c,
        "change_1m": round(ch_1m, 3),
        "accel": accel,
        "url": f"https://birdeye.so/token/{addr}?chain=solana",
        "reason": "moonshot_exception" if moonshot else "ignite_acceleration",
    }

    # store alert
    try:
        add_alert("birdeye_ignition", {
            "symbol": symbol,
            "address": addr,
            "url": payload["url"],
            "message": f"IGNITION {symbol} {round(ch_1m,2)}% (1m) accel={hint}",
        })
    except Exception:
        pass

    return payload
