# src/services/alerts_store.py
from pathlib import Path
import json
from datetime import datetime, timezone

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "alerts" / "recent_alerts.json"
DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

_MAX = 200  # keep last 200

def _load():
    if not DATA_FILE.exists():
        return {"records": []}
    try:
        return json.loads(DATA_FILE.read_text())
    except Exception:
        return {"records": []}

def add_alert(kind: str, payload: dict):
    db = _load()
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "payload": payload,
    }
    db["records"] = [rec] + db.get("records", [])
    db["records"] = db["records"][:_MAX]
    DATA_FILE.write_text(json.dumps(db, indent=2))
    return rec

def recent_alerts(limit: int = 25, kind: str | None = None):
    db = _load()
    recs = db.get("records", [])
    if kind:
        recs = [r for r in recs if r.get("kind") == kind]
    return recs[:max(1, min(int(limit), 100))]
