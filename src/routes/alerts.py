# src/routes/alerts.py
from flask import Blueprint, request, jsonify
import os, json, time, threading

alerts_bp = Blueprint("alerts_bp", __name__)

# Config
DAILY_CAP = int(os.getenv("ALERTS_DAILY_CAP", "5"))
HI_CONF_THRESHOLD = float(os.getenv("HI_CONF_THRESHOLD", "0.9"))
HI_CONF_OVERFLOW = int(os.getenv("HI_CONF_OVERFLOW", "2"))

COUNTER_PATH = "/tmp/alerts_counter.json"
_lock = threading.Lock()

def _today_key():
    return time.strftime("%Y-%m-%d")

def _load_counts():
    try:
        with open(COUNTER_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_counts(data):
    tmp = COUNTER_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, COUNTER_PATH)

def _can_emit(score: float):
    with _lock:
        data = _load_counts()
        day = _today_key()
        rec = data.get(day, {"normal": 0, "overflow": 0})
        normal_used, overflow_used = rec["normal"], rec["overflow"]

        if normal_used < DAILY_CAP:
            rec["normal"] = normal_used + 1
            data[day] = rec
            _save_counts(data)
            return True, "normal", rec

        if score is not None and score >= HI_CONF_THRESHOLD and overflow_used < HI_CONF_OVERFLOW:
            rec["overflow"] = overflow_used + 1
            data[day] = rec
            _save_counts(data)
            return True, "overflow", rec

        return False, "blocked", rec

@alerts_bp.route("/alerts/emit", methods=["POST"])
def emit_alert():
    """
    Expected JSON:
      {
        "symbol": "...",
        "reason": "...",
        "score": 0.0-1.0,   # optional but enables overflow bypass
        "data": {...}       # anything else you want to attach
      }
    """
    payload = request.get_json(force=True, silent=True) or {}
    score = payload.get("score", None)
    ok, mode, rec = _can_emit(float(score) if score is not None else -1.0)
    if not ok:
        return jsonify({
            "ok": False,
            "mode": mode,
            "cap": DAILY_CAP,
            "used": rec,
            "message": "Daily cap reached; high-confidence overflow not available or score too low."
        }), 200

    # TODO: fanout to Discord/Telegram/webhook here if enabled
    return jsonify({
        "ok": True,
        "mode": mode,
        "used": rec,
        "alert": payload
    }), 200

@alerts_bp.route("/alerts/quota", methods=["GET"])
def quota():
    data = _load_counts()
    rec = data.get(_today_key(), {"normal": 0, "overflow": 0})
    return jsonify({
        "date": _today_key(),
        "cap": DAILY_CAP,
        "hi_conf_threshold": HI_CONF_THRESHOLD,
        "hi_conf_overflow_cap": HI_CONF_OVERFLOW,
        "used": rec
    })
