from flask import Blueprint, request, jsonify
from services.dispatch import send_alert

alerts_bp = Blueprint("alerts_bp", __name__)

@alerts_bp.route("/alerts/ingest", methods=["POST"])
def ingest():
    data = request.get_json(silent=True) or {}
    ok, err = send_alert(data)
    if not ok:
        return jsonify({"ok": False, "error": err}), 400
    return jsonify({"ok": True})
