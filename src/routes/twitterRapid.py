# src/routes/twitterRapid.py
from flask import Blueprint, request, jsonify
from src.services.twitterRapid import get_twitterRapid_likes

twitter_bp = Blueprint("twitterRapid", __name__)

@twitter_bp.route("/api/twitterRapid/likes", methods=["GET"])
def twitter_likes():
    """
    Fetch real Twitter-Rapid likes data from RapidAPI or mirror source.
    """
    try:
        pid = request.args.get("pid", "mirrorx_trending")
        count = int(request.args.get("count", 10))
        data = get_twitterRapid_likes(pid, count)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
