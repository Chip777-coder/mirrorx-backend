# src/routes/dex_proxy.py
from flask import Blueprint, request, jsonify
from src.services.dex_proxy import (
    dex_token_profiles_latest,
    dex_community_takeovers_latest,
    dex_ads_latest,
    dex_token_boosts_latest,
    dex_token_boosts_top,
    dex_orders,
    dex_pair,
    dex_search,
    dex_token_pairs,
    dex_tokens,
)

dex_proxy_bp = Blueprint("dex_proxy_bp", __name__)

@dex_proxy_bp.get("/dex/token-profiles/latest")
def token_profiles_latest():
    return jsonify(dex_token_profiles_latest())

@dex_proxy_bp.get("/dex/community-takeovers/latest")
def community_takeovers_latest():
    return jsonify(dex_community_takeovers_latest())

@dex_proxy_bp.get("/dex/ads/latest")
def ads_latest():
    return jsonify(dex_ads_latest())

@dex_proxy_bp.get("/dex/token-boosts/latest")
def token_boosts_latest():
    return jsonify(dex_token_boosts_latest())

@dex_proxy_bp.get("/dex/token-boosts/top")
def token_boosts_top():
    return jsonify(dex_token_boosts_top())

@dex_proxy_bp.get("/dex/orders")
def orders():
    chain_id = request.args.get("chainId", "").strip()
    token_address = request.args.get("tokenAddress", "").strip()
    if not chain_id or not token_address:
        return jsonify({"error": "Missing required query params: chainId, tokenAddress"}), 400
    return jsonify(dex_orders(chain_id, token_address))

@dex_proxy_bp.get("/dex/pair")
def pair():
    chain_id = request.args.get("chainId", "").strip()
    pair_id = request.args.get("pairId", "").strip()
    if not chain_id or not pair_id:
        return jsonify({"error": "Missing required query params: chainId, pairId"}), 400
    return jsonify(dex_pair(chain_id, pair_id))

@dex_proxy_bp.get("/dex/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "Missing required query param: q"}), 400
    return jsonify(dex_search(q))

@dex_proxy_bp.get("/dex/token-pairs")
def token_pairs():
    chain_id = request.args.get("chainId", "").strip()
    token_address = request.args.get("tokenAddress", "").strip()
    if not chain_id or not token_address:
        return jsonify({"error": "Missing required query params: chainId, tokenAddress"}), 400
    return jsonify(dex_token_pairs(chain_id, token_address))

@dex_proxy_bp.get("/dex/tokens")
def tokens():
    chain_id = request.args.get("chainId", "").strip()
    token_addresses = request.args.get("tokenAddresses", "").strip()
    if not chain_id or not token_addresses:
        return jsonify({"error": "Missing required query params: chainId, tokenAddresses"}), 400
    return jsonify(dex_tokens(chain_id, token_addresses))
