from flask import Blueprint, jsonify
import datetime

health_bp = Blueprint('health', __name__)

@health_bp.route("/", methods=["GET"])
def health_check():
    return jsonify({
        "ok": True,
        "status": "operational",
        "time": datetime.datetime.utcnow().isoformat() + "Z"
    })
