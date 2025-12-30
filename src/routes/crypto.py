from flask import Blueprint, jsonify

crypto_bp = Blueprint("crypto", __name__)

@crypto_bp.route("/")
def placeholder():
    return jsonify({"status": "Crypto route active ✅"})
