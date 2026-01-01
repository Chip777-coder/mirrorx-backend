# src/routes/signal_history.py
from flask import Blueprint, jsonify
from datetime import datetime
import os, json

signal_history_bp = Blueprint("signal_history_bp", __name__)
HISTORY_FILE = os.path.join(os.path.dirname(__file__), "..", "analytics", "signal_history.json")

@signal_history_bp.route("/signals/history", methods=["GET"])
def get_signal_history():
    """Return stored alpha signal history snapshots."""
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            data = json.load(f)
    else:
        data = []
    return jsonify({"records": data})

def log_signals(data):
    """Append new signal snapshot."""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
    entry = {"timestamp": datetime.utcnow().isoformat(), "data": data}
    history.append(entry)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history[-50:], f)  # keep latest 50 entries
