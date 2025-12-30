from flask import Blueprint, jsonify

intel_bp = Blueprint("intel", __name__)

@intel_bp.route("/")
def placeholder():
    return jsonify({"status": "Intel route active ✅"})
