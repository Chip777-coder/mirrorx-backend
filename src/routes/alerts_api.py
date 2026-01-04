# src/routes/alerts_api.py
from flask import Blueprint, jsonify, request
from src.services.alerts_store import get_recent_alerts
from src.services.telegram_alerts import send_telegram_message

alerts_api_bp = Blueprint("alerts_api_bp", __name__)


@alerts_api_bp.route("/alerts/recent", methods=["GET"])
def alerts_recent():
    """
    Return recent stored alerts for dashboards / GPT.
    Query params:
      - limit (default 50, max 200)
      - source (optional)
    """
    limit = request.args.get("limit", "50")
    source = request.args.get("source", "").strip() or None
    try:
        alerts = get_recent_alerts(limit=int(limit), source=source)
        return jsonify({"ok": True, "count": len(alerts), "records": alerts})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@alerts_api_bp.route("/alerts/telegram/send", methods=["POST"])
def send_telegram_alert():
    """
    Optional explicit Telegram push endpoint.
    Body:
      { "text": "...", "parse_mode": "HTML" or "Markdown" }
    """
    try:
        body = request.get_json(force=True, silent=True) or {}
        text = body.get("text", "")
        parse_mode = body.get("parse_mode", "HTML")

        if not text or not isinstance(text, str):
            return jsonify({"ok": False, "error": "Missing 'text'"}), 400

        # Your send_telegram_message in repo appears to send HTML fine.
        # If your implementation supports parse_mode, pass it. If not, just send text.
        try:
            send_telegram_message(text, parse_mode=parse_mode)
        except TypeError:
            send_telegram_message(text)

        return jsonify({"ok": True, "detail": "sent"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
