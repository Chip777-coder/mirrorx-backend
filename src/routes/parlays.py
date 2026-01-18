from flask import Blueprint, jsonify
from analytics.mirrax.parlay_builder import generate_multiple_parlays

parlays_bp = Blueprint("parlays", __name__)

@parlays_bp.route("/parlay/today", methods=["GET"])
def get_parlays():
    return jsonify(generate_multiple_parlays())
