# src/services/alerts_store.py
"""
Simple alert store (JSON file) so the backend + GPT can read recent alerts.

- add_alert(source, data)
- get_recent_alerts(limit=50, source=None)
- clear_alerts()
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Store in: src/data/alerts/alerts.json
BASE_DIR = Path(__file__).resolve().parent.parent  # .../src
ALERTS_DIR = BASE_DIR / "data" / "alerts"
ALERTS_FILE = ALERTS_DIR / "alerts.json"

DEFAULT_MAX_RECORDS = int(os.getenv("ALERTS_MAX_RECORDS", "500"))


def _ensure_store():
    ALERTS_DIR.mkdir(parents=True, exist_ok=True)
    if not ALERTS_FILE.exists():
        ALERTS_FILE.write_text(json.dumps({"records": []}, indent=2))


def _read_store() -> Dict[str, Any]:
    _ensure_store()
    try:
        with open(ALERTS_FILE, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"records": []}
        if "records" not in data or not isinstance(data["records"], list):
            return {"records": []}
        return data
    except Exception:
        return {"records": []}


def _write_store(data: Dict[str, Any]) -> None:
    _ensure_store()
    tmp = str(ALERTS_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, ALERTS_FILE)


def add_alert(source: str, payload: Dict[str, Any], max_records: Optional[int] = None) -> Dict[str, Any]:
    """Append an alert record. Best-effort file persistence."""
    max_records = max_records or DEFAULT_MAX_RECORDS

    store = _read_store()
    records: List[Dict[str, Any]] = store.get("records", [])

    record = {
        "id": uuid.uuid4().hex[:12],
        "timestamp": payload.get("timestamp") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": source,
        "data": payload,
    }

    records.insert(0, record)  # newest first
    if len(records) > max_records:
        records = records[:max_records]

    store["records"] = records
    _write_store(store)
    return record


def get_recent_alerts(limit: int = 50, source: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return recent alerts (newest first)."""
    store = _read_store()
    records: List[Dict[str, Any]] = store.get("records", [])

    if source:
        source_u = source.strip().lower()
        records = [r for r in records if (r.get("source", "") or "").lower() == source_u]

    limit = max(1, min(int(limit), 200))
    return records[:limit]


def clear_alerts() -> None:
    """Clear store (use carefully)."""
    _write_store({"records": []})
