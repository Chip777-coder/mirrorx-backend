# src/services/telegram_alerts.py
import os
import requests

TELEGRAM_API_BASE = "https://api.telegram.org"

def send_telegram_message(message: str):
    """Send a message to the configured Telegram chat."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("[WARN] Telegram credentials not configured.")
        return False

    try:
        url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        response = requests.post(url, data=payload, timeout=10)
        if response.status_code == 200:
            print(f"[TELEGRAM] Alert sent successfully → {chat_id}")
            return True
        else:
            print(f"[TELEGRAM] Failed → {response.text}")
            return False
    except Exception as e:
        print(f"[ERROR] Telegram alert failed: {e}")
        return False
