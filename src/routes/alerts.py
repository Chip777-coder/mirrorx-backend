# src/routes/alerts.py
from flask import Blueprint, request, jsonify
import requests
from ..config import settings

alerts_bp = Blueprint("alerts_bp", __name__)

@alerts_bp.route("/alerts", methods=["POST"])
def ingest_alert():
    """
    Example alert ingestion endpoint.
    If Supabase keys are set, pushes alerts into Supabase.
    Otherwise, just echoes the alert back.
    """
    data = request.json or {}

    if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY:
        try:
            resp = requests.post(
                f"{settings.SUPABASE_URL}/rest/v1/alerts",
                headers={
                    "apikey": settings.SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                    "Content-Type": "application/json",
                },
                json=data,
                timeout=6,
            )
            resp.raise_for_status()
            return jsonify({"status": "stored", "supabase": True})
        except Exception as e:
            return jsonify({"status": "failed", "error": str(e)}), 500

    return jsonify({"status": "ok", "supabase": False, "data": data})
