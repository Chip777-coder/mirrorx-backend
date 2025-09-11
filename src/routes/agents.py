from flask import Blueprint, jsonify
import requests
from ..config import settings

agents_bp = Blueprint("agents_bp", __name__)

@agents_bp.route("/agents/status")
def agents_status():
    checks = {}

    # Moralis (optional)
    if settings.MORALIS_API_KEY:
        try:
            resp = requests.get(
                "https://deep-index.moralis.io/api/v2/dateToBlock",
                headers={"X-API-Key": settings.MORALIS_API_KEY},
                params={"chain": "eth", "date": "2020-01-01"},
                timeout=6,
            )
            checks["moralis"] = resp.status_code
        except Exception as e:
            checks["moralis"] = f"error: {e}"
    else:
        checks["moralis"] = "not configured"

    # CoinGecko (public)
    try:
        resp = requests.get(f"{settings.COINGECKO_API_BASE}/ping", timeout=6)
        checks["coingecko"] = resp.json()
    except Exception as e:
        checks["coingecko"] = f"error: {e}"

    return jsonify(checks)
