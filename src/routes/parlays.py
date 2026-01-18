# parlays.py
from flask import Blueprint, jsonify
from analytics.mirrax.parlay_builder import build_parlay

parlays_bp = Blueprint('parlays', __name__)

@parlays_bp.route("/parlay/today", methods=["GET"])
def get_today_parlay():
    parlay = build_parlay()
    return jsonify(parlay)
