from flask import Blueprint, request, jsonify
from services.registry import AVAILABLE_AGENTS

agents_bp = Blueprint("agents_bp", __name__)

@agents_bp.route("/agents/list")
def list_agents():
    return jsonify(sorted(list(AVAILABLE_AGENTS.keys())))

@agents_bp.route("/agents/run", methods=["POST"])
def run_agents():
    payload = request.get_json(silent=True) or {}
    names = payload.get("agents") or list(AVAILABLE_AGENTS.keys())
    params = payload.get("params") or {}

    results = {}
    for name in names:
        fn = AVAILABLE_AGENTS.get(name)
        if not fn:
            results[name] = {"ok": False, "error": "unknown agent"}
            continue
        try:
            results[name] = {"ok": True, "data": fn(**params)}
        except Exception as e:
            results[name] = {"ok": False, "error": str(e)}
    return jsonify(results)
