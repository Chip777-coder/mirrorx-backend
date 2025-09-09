from flask import Blueprint, jsonify

alerts_bp = Blueprint("alerts_bp", __name__)

@alerts_bp.route("/alerts/ping")
def ping_alerts():
    return jsonify({"ok": True, "module": "alerts"})
