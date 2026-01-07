# src/services/movers_store.py
"""
Movers Store (Snapshot History)
-------------------------------
Stores small rolling snapshots so we can detect acceleration.
This is the piece that helps catch early stages of huge moves.

Storage is JSON on disk (like your signals history).
Best effort. On Render free tiers, disk is usually ephemeral across redeploys,
but this still helps *in-session* and between scheduler runs.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import threading

_LOCK = threading.Lock()

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "movers"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HISTORY_FILE = DATA_DIR / "movers_history.json"

MAX_RECORDS = int(os.getenv("MOVERS_MAX_RECORDS", "2000"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict:
    if not HISTORY_FILE.exists():
        return {"records": []}
    try:
        with open(HISTORY_FILE, "r") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("records"), list):
            return data
    except Exception:
        pass
    return {"records": []}


def _save(data: dict) -> None:
    tmp = str(HISTORY_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, HISTORY_FILE)


def record_snapshot(source: str, item: dict) -> None:
    """
    item should be small and JSON-safe.
    Example fields:
      address, symbol, priceUsd, liquidityUsd, volumeH1, volumeH24, changeM5, changeH1, url
    """
    if not isinstance(item, dict):
        return

    record = {
        "ts": _now_iso(),
        "source": source,
        "data": item,
    }

    with _LOCK:
        data = _load()
        recs = data.get("records", [])
        recs.insert(0, record)
        # trim
        data["records"] = recs[:MAX_RECORDS]
        _save(data)


def get_recent(limit: int = 200) -> list[dict]:
    with _LOCK:
        data = _load()
        recs = data.get("records", [])
        return recs[: max(1, int(limit))]


def get_recent_by_address(address: str, limit: int = 50) -> list[dict]:
    if not address:
        return []
    address = address.strip()
    out = []
    for r in get_recent(limit=2000):
        d = (r.get("data") or {})
        if (d.get("address") or "").strip() == address:
            out.append(r)
            if len(out) >= limit:
                break
    return out


def compute_acceleration(address: str) -> dict:
    """
    Compute simple acceleration signals from recent snapshots.
    Returns: {samples, change_m5_latest, change_h1_latest, accel_hint}
    """
    rows = get_recent_by_address(address, limit=10)
    if len(rows) < 2:
        return {"samples": len(rows), "accel_hint": "insufficient_history"}

    # newest first
    latest = rows[0].get("data", {}) or {}
    older = rows[-1].get("data", {}) or {}

    ch5_latest = float(latest.get("changeM5", 0) or 0)
    ch5_older = float(older.get("changeM5", 0) or 0)
    ch1_latest = float(latest.get("changeH1", 0) or 0)
    ch1_older = float(older.get("changeH1", 0) or 0)

    accel_5m = ch5_latest - ch5_older
    accel_1h = ch1_latest - ch1_older

    hint = "flat"
    if accel_5m > 10 or accel_1h > 25:
        hint = "accelerating"
    if accel_5m < -10 or accel_1h < -25:
        hint = "decelerating"

    return {
        "samples": len(rows),
        "change_m5_latest": round(ch5_latest, 3),
        "change_h1_latest": round(ch1_latest, 3),
        "accel_5m": round(accel_5m, 3),
        "accel_1h": round(accel_1h, 3),
        "accel_hint": hint,
    }
