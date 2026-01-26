# src/services/performance_tracker.py
from __future__ import annotations

import os
import json
import time
from typing import Any, Dict, List, Optional

import requests


# ============================================================
# Paper Trading / Performance Tracking (Simulated)
# ============================================================
# Stores signals and periodically re-checks the price to compute ROI.
#
# Safe:
# - Does NOT execute trades.
# - Only records and measures performance.
# ============================================================

DEX_BASE = "https://api.dexscreener.com"
DEX_TOKEN_PAIRS = f"{DEX_BASE}/latest/dex/tokens/"

PAPER_TRADING_ENABLE = os.getenv("ALPHA_PAPER_TRADING_ENABLE", "1") == "1"
PAPER_TRADES_FILE = os.getenv("ALPHA_PAPER_TRADES_FILE", "/opt/render/project/src/paper_trades.json")

DEX_TIMEOUT = int(os.getenv("DEX_HTTP_TIMEOUT", "12"))


def _safe_float(x: Any, d: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return d


def _fetch_pairs(token_address: str) -> List[dict]:
    try:
        r = requests.get(f"{DEX_TOKEN_PAIRS}{token_address}", timeout=DEX_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        pairs = data.get("pairs", []) if isinstance(data, dict) else []
        return pairs if isinstance(pairs, list) else []
    except Exception:
        return []


def _best_pair_price_usd(pairs: List[dict]) -> float:
    """
    Picks the best pair by liquidity and returns priceUsd.
    """
    if not pairs:
        return 0.0

    def score(p: dict) -> float:
        liq = _safe_float((p.get("liquidity") or {}).get("usd"))
        vol = _safe_float((p.get("volume") or {}).get("h1"))
        return liq + (vol * 0.05)

    best = sorted(pairs, key=score, reverse=True)[0]
    return _safe_float(best.get("priceUsd"), 0.0)


def _read_trades() -> List[dict]:
    if not os.path.exists(PAPER_TRADES_FILE):
        return []
    try:
        with open(PAPER_TRADES_FILE, "r", encoding="utf-8") as f:
            raw = f.read().strip()
            if not raw:
                return []
            data = json.loads(raw)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _write_trades(trades: List[dict]) -> None:
    try:
        with open(PAPER_TRADES_FILE, "w", encoding="utf-8") as f:
            json.dump(trades, f, indent=2)
    except Exception:
        pass


def record_signal(token: Dict[str, Any]) -> None:
    """
    Saves a signal entry for later performance evaluation.
    """
    if not PAPER_TRADING_ENABLE:
        return

    mint = token.get("mint") or token.get("address")
    if not mint:
        return

    trades = _read_trades()

    entry = {
        "ts": token.get("ts") or time.time(),
        "mint": mint,
        "symbol": token.get("symbol", "UNKNOWN"),
        "tier": token.get("tier", "UNKNOWN"),
        "confidence": token.get("confidence", 0),
        "entry_price": _safe_float(token.get("price"), 0.0),
        "best_price": _safe_float(token.get("price"), 0.0),
        "last_price": _safe_float(token.get("price"), 0.0),
        "last_checked": time.time(),
        "status": "open",
        "url": token.get("url", ""),
    }

    trades.append(entry)

    # keep list from growing forever
    if len(trades) > 2500:
        trades = trades[-2500:]

    _write_trades(trades)


def update_performance(limit: int = 60) -> Dict[str, Any]:
    """
    Checks latest prices of recent signals and updates ROI.
    """
    trades = _read_trades()
    if not trades:
        return {"updated": 0, "total": 0}

    # update only most recent N
    recent = trades[-limit:]
    updated = 0

    for t in recent:
        mint = t.get("mint")
        if not mint:
            continue

        pairs = _fetch_pairs(mint)
        price_now = _best_pair_price_usd(pairs)
        if price_now <= 0:
            continue

        entry = _safe_float(t.get("entry_price"), 0.0)
        best = _safe_float(t.get("best_price"), entry)

        t["last_price"] = price_now
        t["best_price"] = max(best, price_now)
        t["last_checked"] = time.time()

        if entry > 0:
            t["roi_now_pct"] = round(((price_now - entry) / entry) * 100, 2)
            t["roi_best_pct"] = round(((t["best_price"] - entry) / entry) * 100, 2)

        updated += 1

    # write back
    trades[-limit:] = recent
    _write_trades(trades)

    return {"updated": updated, "total": len(trades)}
