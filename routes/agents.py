# routes/agents.py
from flask import Blueprint, jsonify, request

agents_bp = Blueprint("agents_bp", __name__)

@agents_bp.route("/agents/ping", methods=["GET"])
def ping():
    return jsonify({"ok": True, "agent": "up"})

@agents_bp.route("/agents/run", methods=["POST"])
def run():
    payload = request.get_json(silent=True) or {}
    # TODO: plug your agent runner here
    return jsonify({"ok": True, "received": payload})
