from flask import Blueprint, jsonify
import requests, os

crypto_bp = Blueprint("crypto", __name__)

@crypto_bp.route("/solana", methods=["GET"])
def solana():
    try:
        resp = requests.get(
            f"{os.getenv('COINGECKO_BASE_URL')}/coins/markets",
            params={"vs_currency": "usd", "category": "solana-ecosystem"}
        )
        return jsonify(resp.json()[:10])
    except Exception as e:
        return jsonify({"error": str(e)}), 500
