# src/alerts/fusion_broadcast.py
import os
import time
import requests
from telegram import Bot

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

# Master switch: prevents spam during deploys / web traffic
ENABLE_BROADCAST = os.getenv("ENABLE_BROADCAST", "0") == "1"

# Simple in-process rate limit (best effort; resets per worker)
_MIN_SECONDS_BETWEEN_SENDS = int(os.getenv("BROADCAST_MIN_SECONDS", "180"))  # 3 minutes default
_last_sent_ts = 0.0


def _get_bot():
    """Create bot lazily (avoid import-time side effects in Gunicorn)."""
    if not TELEGRAM_TOKEN:
        return None
    try:
        return Bot(token=TELEGRAM_TOKEN)
    except Exception:
        return None


def broadcast_fusion(payload):
    """Send top fusion updates to Telegram & Discord."""
    global _last_sent_ts

    if not payload:
        return

    # Hard gate: do nothing unless explicitly enabled
    if not ENABLE_BROADCAST:
        print("[BROADCAST] Skipped (ENABLE_BROADCAST=0)")
        return

    # Rate limit (best effort)
    now = time.time()
    if _MIN_SECONDS_BETWEEN_SENDS > 0 and (now - _last_sent_ts) < _MIN_SECONDS_BETWEEN_SENDS:
        print("[BROADCAST] Skipped (rate-limited)")
        return

    try:
        summary = "\n".join(
            [
                f"{t.get('symbol')}: ${round(float(t.get('price', 0) or 0), 6)} | "
                f"Δ24h {round(float(t.get('ccChange24h', 0) or 0), 2)}%"
                for t in payload
            ]
        )
        text = f"🔥 *MirroraX Live Fusion Update*\n\n{summary}"

        # Telegram
        bot = _get_bot()
        if bot and TELEGRAM_CHAT_ID:
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="Markdown")

        # Discord
        if DISCORD_WEBHOOK:
            requests.post(DISCORD_WEBHOOK, json={"content": text}, timeout=10)

        _last_sent_ts = now
        print("[BROADCAST] Fusion alert sent successfully.")
    except Exception as e:
        print(f"[WARN] Fusion broadcast failed: {e}")
