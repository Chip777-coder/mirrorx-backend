# src/routes/dex_proxy.py
"""
DexScreener Proxy Routes (MirrorX)
----------------------------------
Why: keep GPT Actions + clients calling ONLY your backend host,
and let your backend fetch DexScreener safely (timeouts, params, etc.)
"""

from flask import Blueprint, jsonify, request
import requests

dex_proxy_bp = Blueprint("dex_proxy_bp", __name__)

DEX_BASE = "https://api.dexscreener.com"


def _get(path: str, params: dict | None = None, timeout: int = 12):
    url = f"{DEX_BASE}{path}"
    r = requests.get(url, params=params or {}, timeout=timeout)
    r.raise_for_status()
    return r.json()


@dex_proxy_bp.route("/api/dex/token-boosts/top", methods=["GET"])
def dex_token_boosts_top():
    try:
        data = _get("/token-boosts/top/v1")
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dex_proxy_bp.route("/api/dex/token-boosts/latest", methods=["GET"])
def dex_token_boosts_latest():
    try:
        data = _get("/token-boosts/latest/v1")
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dex_proxy_bp.route("/api/dex/token-profiles/latest", methods=["GET"])
def dex_token_profiles_latest():
    try:
        data = _get("/token-profiles/latest/v1")
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dex_proxy_bp.route("/api/dex/community-takeovers/latest", methods=["GET"])
def dex_community_takeovers_latest():
    try:
        data = _get("/community-takeovers/latest/v1")
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dex_proxy_bp.route("/api/dex/latest/dex/search", methods=["GET"])
def dex_search():
    """
    Proxy for /latest/dex/search?q=...
    """
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"error": "missing query param q"}), 400
    try:
        data = _get("/latest/dex/search", params={"q": q})
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dex_proxy_bp.route("/api/dex/tokens/v1/<chain_id>/<token_addresses>", methods=["GET"])
def dex_tokens_v1(chain_id: str, token_addresses: str):
    """
    Proxy for /tokens/v1/{chainId}/{tokenAddresses}
    token_addresses should be comma-separated.
    """
    try:
        data = _get(f"/tokens/v1/{chain_id}/{token_addresses}")
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@dex_proxy_bp.route("/api/dex/token-pairs/v1/<chain_id>/<token_address>", methods=["GET"])
def dex_token_pairs(chain_id: str, token_address: str):
    """
    Proxy for /token-pairs/v1/{chainId}/{tokenAddress}
    """
    try:
        data = _get(f"/token-pairs/v1/{chain_id}/{token_address}")
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
