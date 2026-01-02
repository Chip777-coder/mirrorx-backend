# src/routes/alerts_test.py
from flask import Blueprint, jsonify
from src.services.telegram_alerts import send_telegram_message

alerts_test_bp = Blueprint("alerts_test_bp", __name__)

@alerts_test_bp.route("/api/alerts/test", methods=["GET"])
def test_alert():
    """Send a test alert to Telegram."""
    success = send_telegram_message("🚀 MirrorX Alert Test: Backend → Telegram OK ✅")
    return jsonify({
        "ok": success,
        "message": "Test alert sent!" if success else "Failed to send alert."
    })
