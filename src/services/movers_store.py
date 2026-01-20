# src/services/movers_store.py
"""
Movers Store (Snapshot History)
-------------------------------
Stores small rolling snapshots so we can detect acceleration.
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
        data["records"] = recs[:MAX_RECORDS]
        _save(data)


def get_recent_by_address(address: str, limit: int = 50) -> list[dict]:
    if not address:
        return []
    address = address.strip()
    out = []
    for r in _load().get("records", []):
        d = (r.get("data") or {})
        if (d.get("address") or "").strip() == address:
            out.append(r)
            if len(out) >= limit:
                break
    return out


def compute_acceleration(address: str) -> dict:
    rows = get_recent_by_address(address, limit=10)

    # 🔧 MINIMAL EDIT: require 3 samples instead of 2
    if len(rows) < 3:
        return {
            "samples": len(rows),
            "accel_hint": "building"
        }

    latest = rows[0].get("data", {}) or {}
    older = rows[-1].get("data", {}) or {}

    ch5_latest = float(latest.get("changeM5", 0) or 0)
    ch5_older = float(older.get("changeM5", 0) or 0)
    ch1_latest = float(latest.get("changeH1", 0) or 0)
    ch1_older = float(older.get("changeH1", 0) or 0)

    accel_5m = ch5_latest - ch5_older
    accel_1h = ch1_latest - ch1_older

    hint = "flat"
    if accel_5m > 8 or accel_1h > 20:
        hint = "accelerating"
    elif accel_5m < -8 or accel_1h < -20:
        hint = "decelerating"

    return {
        "samples": len(rows),
        "change_m5_latest": round(ch5_latest, 3),
        "change_h1_latest": round(ch1_latest, 3),
        "accel_5m": round(accel_5m, 3),
        "accel_1h": round(accel_1h, 3),
        "accel_hint": hint,
    }
