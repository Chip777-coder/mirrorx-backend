# src/services/movers_store.py
"""
Movers Store (Snapshot History)
-------------------------------
Stores small rolling snapshots so we can detect acceleration.
This helps identify early stages of large moves.

Best effort storage (JSON on disk). On Render free tiers,
disk may reset on redeploys, but this works well between scheduler runs.
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


def get_recent(limit: int = 200) -> list[dict]:
    with _LOCK:
        data = _load()
        return data.get("records", [])[: max(1, int(limit))]


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
    Compute acceleration from recent snapshots.

    Returns:
      samples
      accel_hint
      accel_5m / accel_1h when available
    """
    rows = get_recent_by_address(address, limit=10)

    # --- No history at all ---
    if not rows:
        return {"samples": 0, "accel_hint": "insufficient_history"}

    # --- Single snapshot fallback (STRUCTURAL MOMENTUM) ---
    if len(rows) == 1:
        d = rows[0].get("data", {}) or {}
        ch5 = float(d.get("changeM5", 0) or 0)
        ch1 = float(d.get("changeH1", 0) or 0)

        if ch5 >= 15:
            hint = "short_term_spike"
        elif ch5 >= 8 and ch1 > 0:
            hint = "momentum_building"
        else:
            hint = "building"

        return {
            "samples": 1,
            "change_m5_latest": round(ch5, 3),
            "change_h1_latest": round(ch1, 3),
            "accel_hint": hint,
        }

    # --- 2+ snapshots: TRUE acceleration ---
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
    elif accel_5m > 0:
        hint = "early_acceleration"

    return {
        "samples": len(rows),
        "change_m5_latest": round(ch5_latest, 3),
        "change_h1_latest": round(ch1_latest, 3),
        "accel_5m": round(accel_5m, 3),
        "accel_1h": round(accel_1h, 3),
        "accel_hint": hint,
    }
