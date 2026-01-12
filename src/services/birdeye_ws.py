# src/services/birdeye_ws.py
"""
Birdeye WebSocket Listener (Solana)
----------------------------------
- SUBSCRIBE_NEW_PAIR: discover new pools (pump.fun etc)
- SUBSCRIBE_PRICE: subscribe to up to 100 addresses for real-time OHLCV

This feeds MirrorX "Ignition Engine" to catch early-stage moonshots.

Educational tooling only. Not trade advice.
"""

from __future__ import annotations
import os
import json
import time
import threading
from typing import Dict, Any, List, Set, Optional

import websocket  # websocket-client
import requests

from src.services.telegram_alerts import send_telegram_message
from src.services.birdeye_ignition import ingest_ohlcv

BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY", "").strip()
BIRDEYE_CHAIN = os.getenv("BIRDEYE_CHAIN", "solana").strip()
WS_URL = f"wss://public-api.birdeye.so/socket/{BIRDEYE_CHAIN}?x-api-key={BIRDEYE_API_KEY}"

# Watchlist management
WATCHLIST_MAX = int(os.getenv("BIRDEYE_WATCHLIST_MAX", "80"))     # keep under 100
PAIR_MIN_LIQ = float(os.getenv("BIRDEYE_NEWPAIR_MIN_LIQ", "1000"))  # Birdeye liquidity filter units as per docs
PAIR_MAX_LIQ = float(os.getenv("BIRDEYE_NEWPAIR_MAX_LIQ", "50000"))

# Reconnect behavior
PING_INTERVAL = int(os.getenv("BIRDEYE_PING_INTERVAL", "25"))
RECONNECT_DELAY = int(os.getenv("BIRDEYE_RECONNECT_DELAY", "5"))

# Thread-safe state
_lock = threading.Lock()
_watchlist: Set[str] = set()      # addresses to subscribe (token or pair addresses)
_started = False


def _ws_headers() -> List[str]:
    # Birdeye requires headers per docs
    return [
        "Origin: ws://public-api.birdeye.so",
        "Sec-WebSocket-Origin: ws://public-api.birdeye.so",
        "Sec-WebSocket-Protocol: echo-protocol",
    ]


def _send(ws, obj: Dict[str, Any]) -> None:
    try:
        ws.send(json.dumps(obj))
    except Exception:
        return


def _subscribe_new_pairs(ws) -> None:
    msg = {
        "type": "SUBSCRIBE_NEW_PAIR",
        "min_liquidity": PAIR_MIN_LIQ,
        "max_liquidity": PAIR_MAX_LIQ,
    }
    _send(ws, msg)


def _subscribe_prices(ws, addresses: List[str]) -> None:
    # Complex query to subscribe multiple (limit 100)
    # Use 1m USD chart where possible
    parts = []
    for a in addresses:
        a = a.strip()
        if not a:
            continue
        parts.append(f"(address = {a} AND chartType = 1m AND currency = usd)")
    if not parts:
        return
    query = " OR ".join(parts)
    msg = {"type": "SUBSCRIBE_PRICE", "data": {"queryType": "complex", "query": query}}
    _send(ws, msg)


def _refresh_price_subscriptions(ws) -> None:
    with _lock:
        addrs = list(_watchlist)[: min(len(_watchlist), 100)]
    _subscribe_prices(ws, addrs)


def add_to_watchlist(address: str) -> bool:
    address = (address or "").strip()
    if not address:
        return False
    with _lock:
        if address in _watchlist:
            return True
        if len(_watchlist) >= WATCHLIST_MAX:
            return False
        _watchlist.add(address)
        return True


def get_watchlist() -> List[str]:
    with _lock:
        return list(_watchlist)


def _format_ignite_alert(p: Dict[str, Any]) -> str:
    sym = p.get("symbol", "UNKNOWN")
    addr = p.get("address", "")
    ch1m = p.get("change_1m", 0)
    reason = p.get("reason", "ignite")
    accel = (p.get("accel") or {}).get("accel_hint", "n/a")
    url = p.get("url") or ""
    return (
        f"<b>🚨 MirrorX Ignition Alert</b>\n"
        f"Token: <b>{sym}</b>\n"
        f"Mint: <code>{addr}</code>\n"
        f"1m Impulse: <b>{ch1m}%</b>\n"
        f"Acceleration: <b>{accel}</b>\n"
        f"Rule: <b>{reason}</b>\n\n"
        f"<a href='{url}'>Open on Birdeye</a>\n\n"
        f"⚠️ Educational alert only. Early movers can reverse hard."
    )


def _on_open(ws):
    print("[BirdeyeWS] Connected.")
    _subscribe_new_pairs(ws)
    _refresh_price_subscriptions(ws)


def _on_message(ws, message: str):
    try:
        event = json.loads(message)
    except Exception:
        return

    et = event.get("type")

    # 1) New pair discovery
    if et == "NEW_PAIR_DATA":
        data = event.get("data") or {}
        base = (data.get("base") or {})
        base_addr = (base.get("address") or "").strip()
        base_sym = (base.get("symbol") or "").strip()
        src = (data.get("source") or "").strip()

        if base_addr:
            added = add_to_watchlist(base_addr)
            if added:
                print(f"[BirdeyeWS] Watching new base token {base_sym} {base_addr} src={src}")
                # refresh subscriptions to include it
                _refresh_price_subscriptions(ws)
        return

    # 2) Price updates → ignition engine
    if et in ("PRICE_DATA", "BASE_QUOTE_PRICE_DATA"):
        payload = ingest_ohlcv(event)
        if payload:
            msg = _format_ignite_alert(payload)
            send_telegram_message(msg)
        return


def _on_error(ws, error):
    print(f"[BirdeyeWS] Error: {error}")


def _on_close(ws, status_code, msg):
    print(f"[BirdeyeWS] Closed: {status_code} {msg}")


def run_birdeye_ws_forever():
    """
    Blocking loop with reconnect.
    """
    if not BIRDEYE_API_KEY:
        print("[BirdeyeWS] Missing BIRDEYE_API_KEY; not starting.")
        return

    while True:
        try:
            ws = websocket.WebSocketApp(
                WS_URL,
                header=_ws_headers(),
                on_open=_on_open,
                on_message=_on_message,
                on_error=_on_error,
                on_close=_on_close,
            )
            ws.run_forever(ping_interval=PING_INTERVAL, ping_timeout=10)
        except Exception as e:
            print(f"[BirdeyeWS] run_forever exception: {e}")

        time.sleep(RECONNECT_DELAY)


def start_birdeye_ws_thread():
    global _started
    if _started:
        return
    _started = True
    t = threading.Thread(target=run_birdeye_ws_forever, daemon=True)
    t.start()
    print("[BirdeyeWS] Thread started.")
