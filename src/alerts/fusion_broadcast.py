# src/alerts/fusion_broadcast.py
import os, requests
from telegram import Bot

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID")
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

bot = Bot(token=TELEGRAM_TOKEN) if TELEGRAM_TOKEN else None

def broadcast_fusion(payload):
    """Send top fusion updates to Telegram & Discord."""
    if not payload:
        return
    try:
        summary = "\n".join(
            [f"{t.get('symbol')}: ${round(t.get('price',0),4)} | Δ24h {round(t.get('ccChange24h',0),2)}%"
             for t in payload]
        )
        text = f"🔥 *MirroraX Live Fusion Update*\n\n{summary}"

        # Telegram
        if bot and TELEGRAM_CHAT_ID:
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="Markdown")

        # Discord
        if DISCORD_WEBHOOK:
            requests.post(DISCORD_WEBHOOK, json={"content": text})

        print("[BROADCAST] Fusion alert sent successfully.")
    except Exception as e:
        print(f"[WARN] Fusion broadcast failed: {e}")
