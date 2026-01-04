# src/routes/alerts_api.py
from flask import Blueprint, request, jsonify
from src.services.telegram_alerts import send_telegram_message
from src.services.alerts_store import add_alert, recent_alerts

alerts_api_bp = Blueprint("alerts_api_bp", __name__)

@alerts_api_bp.post("/alerts/telegram/send")
def telegram_send():
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    parse_mode = (body.get("parse_mode") or "Markdown").strip()

    if not text:
        return jsonify({"ok": False, "detail": "Missing required field: text"}), 400

    # store + send
    add_alert("telegram_manual", {"text": text, "parse_mode": parse_mode})
    send_telegram_message(text)  # your existing function; uses HTML in many setups—still fine
    return jsonify({"ok": True, "detail": "sent"})

@alerts_api_bp.get("/alerts/recent")
def alerts_recent():
    limit = request.args.get("limit", "25")
    kind = request.args.get("kind")
    return jsonify({"ok": True, "records": recent_alerts(limit=limit, kind=kind)})
