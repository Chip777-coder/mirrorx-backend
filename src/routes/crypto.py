# src/routes/crypto.py
from flask import Blueprint, jsonify
from src.services.solana import get_solana_trending

crypto_bp = Blueprint("crypto", __name__)

@crypto_bp.route("/api/crypto/solana", methods=["GET"])
def solana_tokens():
    """
    Live Solana token metrics and trending pairs.
    """
    try:
        data = get_solana_trending() or []
        response = {
            "updated": "now",
            "ecosystem": "solana",
            "count": len(data),
            "tokens": data
        }
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
