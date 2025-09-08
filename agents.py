from flask import Blueprint, jsonify

agents_bp = Blueprint("agents_bp", __name__)

@agents_bp.route("/agents/ping")
def ping_agents():
    return jsonify({"ok": True, "module": "agents"})
