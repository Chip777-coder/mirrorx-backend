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
    now = time.time()
    with _LOCK:
        data = _load()
        prev = data.get(key)

        if prev:
            elapsed = now - prev["ts"]
            # allow escalation
            if elapsed < COOLDOWN_SECONDS and strength <= prev.get("strength", 0):
                return False

        data[key] = {"ts": now, "strength": strength}
        _save(data)
        return True


def add_alert(source: str, payload: dict):
    return# src/services/alerts_store.py
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
    now = time.time()
    with _LOCK:
        data = _load()
        prev = data.get(key)

        if prev:
            elapsed = now - prev["ts"]
            # allow escalation
            if elapsed < COOLDOWN_SECONDS and strength <= prev.get("strength", 0):
                return False

        data[key] = {"ts": now, "strength": strength}
        _save(data)
        return True


def add_alert(source: str, payload: dict):
    return
