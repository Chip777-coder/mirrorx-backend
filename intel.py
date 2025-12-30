from flask import Blueprint, jsonify
from redis import Redis
import json, os

intel_bp = Blueprint("intel", __name__)
redis_client = Redis.from_url(os.getenv("REDIS_URL"), decode_responses=True)

@intel_bp.route("/summary", methods=["GET"])
def summary():
    cached = redis_client.get("intel_summary")
    if cached:
        return jsonify(json.loads(cached))
    return jsonify({"message": "No cached intelligence summary found"}), 404

@intel_bp.route("/full", methods=["GET"])
def full():
    cached = redis_client.get("intel_full")
    if cached:
        return jsonify(json.loads(cached))
    return jsonify({"message": "No full intelligence dataset found"}), 404
