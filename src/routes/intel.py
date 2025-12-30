from flask import Blueprint, jsonify

intel_bp = Blueprint("intel", __name__)

@intel_bp.route("/", methods=["GET"])
def root():
    return jsonify({"status": "Intel route active ✅"})

@intel_bp.route("/summary", methods=["GET"])
def summary():
    return jsonify({
        "summary": "Intel summary placeholder",
        "status": "OK"
    })

@intel_bp.route("/full", methods=["GET"])
def full():
    return jsonify({
        "details": "Intel full dataset placeholder",
        "status": "OK"
    })
