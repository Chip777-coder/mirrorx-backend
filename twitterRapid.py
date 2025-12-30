from flask import Blueprint, jsonify, request
import requests, os

twitter_bp = Blueprint("twitterRapid", __name__)

@twitter_bp.route("/likes", methods=["GET"])
def likes():
    try:
        pid = request.args.get("pid")
        count = request.args.get("count", 10)
        headers = {
            "x-rapidapi-host": os.getenv("RAPIDAPI_HOST"),
            "x-rapidapi-key": os.getenv("RAPIDAPI_KEY"),
        }
        resp = requests.get(
            f"https://{os.getenv('RAPIDAPI_HOST')}/likes",
            headers=headers,
            params={"pid": pid, "count": count}
        )
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500
