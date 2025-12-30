from flask import Blueprint, jsonify

crypto_bp = Blueprint("crypto", __name__)

@crypto_bp.route("/", methods=["GET"])
def root():
    return jsonify({"status": "Crypto route active ✅"})

@crypto_bp.route("/solana", methods=["GET"])
def solana():
    # Placeholder data until real Solana module is reconnected
    return jsonify({
        "ecosystem": "Solana",
        "tokens_tracked": 42,
        "status": "Solana data endpoint active (placeholder)"
    })
