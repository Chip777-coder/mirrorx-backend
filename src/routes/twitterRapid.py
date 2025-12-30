from flask import Blueprint, jsonify

twitter_bp = Blueprint("twitterRapid", __name__)

@twitter_bp.route("/")
def placeholder():
    return jsonify({"status": "TwitterRapid route active ✅"})
