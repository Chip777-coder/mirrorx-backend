# src/routes/signals_history.py
"""
MirrorX Alpha Signal History Route
Logs and serves historical alpha signal calculations for trend and performance insights.
"""

from flask import Blueprint, jsonify
import os, json, time
from datetime import datetime, timezone
from pathlib import Path

signals_history_bp = Blueprint("signals_history_bp", __name__)

# Directory where snapshots are stored
HISTORY_DIR = Path(os.path.join(os.path.dirname(__file__), "..", "data", "signals"))
HISTORY_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_FILE = HISTORY_DIR / "alpha_signals_history.json"

def _load_history():
    """Load history JSON file if exists."""
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"records": []}

def _save_history(data):
    """Write history back to disk."""
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print("[WARN] Failed to save alpha signal history:", e)

def log_alpha_snapshot(snapshot):
    """
    Save a new alpha signal snapshot entry.
    Called by the Alpha Engine after each successful /signals/alpha run.
    """
    history = _load_history()
    history.setdefault("records", [])
    history["records"].insert(0, {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": snapshot
    })
    # Keep last 100 records to avoid file bloat
    history["records"] = history["records"][:100]
    _save_history(history)

@signals_history_bp.route("/api/signals/history", methods=["GET"])
def get_signal_history():
    """
    Return recent alpha signal history.
    """
    history = _load_history()
    return jsonify({
        "system": "MirrorX Alpha Signal History",
        "status": "operational",
        "count": len(history.get("records", [])),
        "records": history.get("records", [])
    })
