from flask import Blueprint, jsonify, request

twitter_bp = Blueprint("twitterRapid", __name__)

@twitter_bp.route("/", methods=["GET"])
def root():
    return jsonify({"status": "TwitterRapid route active ✅"})

@twitter_bp.route("/likes", methods=["GET"])
def likes():
    pid = request.args.get("pid", "unknown")
    count = request.args.get("count", 5)
    return jsonify({
        "post_id": pid,
        "likes": int(count),
        "status": "TwitterRapid likes placeholder active"
    })
