# telegram_bot.py
import requests
import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_parlay_message(parlay):
    message = "🔥 *Mirabets Daily Parlay* 🔥\n\n"

    for leg in parlay:
        message += f"*Leg {leg['leg']}*: {leg['pick']}\n"
        message += f"Confidence: {leg['confidence']}%\n"
        message += f"Rationale: {leg['rationale']}\n"
        if leg['fade_flag']:
            message += "⚠️ Fade Logic Triggered\n"
        if leg['edge_flag']:
            message += "✅ Edge Confidence\n"
        message += "\n"

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, data={
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    })
