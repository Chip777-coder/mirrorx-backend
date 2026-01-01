# src/routes/status.py
from flask import Blueprint, jsonify
import requests

status_bp = Blueprint("status_bp", __name__)

# Define the core endpoints we want to monitor
ENDPOINTS = {
    "healthz": "/api/healthz",
    "fusion_market": "/api/fusion/market-intel",
    "intel_summary": "/api/intel/summary",
    "intel_full": "/api/intel/full",
    "solana": "/api/crypto/solana",
    "twitter_likes": "/api/twitterRapid/likes?pid=mirrorx_demo_post"
}

BASE_URL = "https://mirrorx-backend.onrender.com"


def check_endpoint(name, path):
    """Ping an endpoint and return status info (non-blocking)."""
    try:
        res = requests.get(f"{BASE_URL}{path}", timeout=6)
        res.raise_for_status()
        return {"status": "ok", "code": res.status_code}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@status_bp.route("/status", methods=["GET"])
def get_system_status():
    """Aggregate status of major MirrorX services into one unified report."""
    results = {name: check_endpoint(name, path) for name, path in ENDPOINTS.items()}
    healthy = [k for k, v in results.items() if v.get("status") == "ok"]
    degraded = [k for k, v in results.items() if v.get("status") != "ok"]

    overall_status = "operational" if len(degraded) == 0 else "degraded"
    uptime_signal = round(len(healthy) / len(ENDPOINTS), 2)

    return jsonify({
        "system": "MirrorX Intelligence API",
        "overall_status": overall_status,
        "healthy_services": healthy,
        "degraded_services": degraded,
        "endpoint_results": results,
        "uptime_signal": uptime_signal
    })
