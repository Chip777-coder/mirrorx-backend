from flask import Blueprint, request, jsonify

alerts_bp = Blueprint("alerts_bp", __name__)

@alerts_bp.route("/alerts/ingest", methods=["POST"])
def ingest():
    data = request.get_json(silent=True) or {}
    # no-op: just echo back for now (wire Discord/Telegram later)
    return jsonify({"ok": True, "received": data})
