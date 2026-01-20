# src/services/alerts_store.py
import json
import os
import time
from pathlib import Path
from threading import Lock

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

FILE = DATA_DIR / "alerts_store.json"
_LOCK = Lock()

COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "2700"))  # 45 min
MAX_RECENT_ALERTS = int(os.getenv("ALERTS_API_LIMIT", "50"))


def _load():
    if not FILE.exists():
        return {}
    try:
        return json.loads(FILE.read_text())
    except Exception:
        return {}


def _save(data):
    FILE.write_text(json.dumps(data))


def can_alert(key: str, strength: float = 0) -> bool:
    """
    Cooldown gate with escalation support.
    """
    now = time.time()
    with _LOCK:
        data = _load()
        prev = data.get(key)

        if prev:
            elapsed = now - prev.get("ts", 0)
            if elapsed < COOLDOWN_SECONDS and strength <= prev.get("strength", 0):
                return False

        data[key] = {"ts": now, "strength": strength}
        _save(data)
        return True


def get_recent_alerts(limit: int = MAX_RECENT_ALERTS) -> list[dict]:
    """
    Used by alerts_api.py
    Returns recent alerts in reverse chronological order.
    """
    data = _load()
    rows = []

    for key, meta in data.items():
        rows.append({
            "key": key,
            "ts": meta.get("ts"),
            "strength": meta.get("strength", 0),
        })

    rows.sort(key=lambda x: x["ts"], reverse=True)
    return rows[: max(1, int(limit))]


def add_alert(source: str, payload: dict):
    """
    Kept for backward compatibility.
    Alerts are controlled via can_alert().
    """
    return
