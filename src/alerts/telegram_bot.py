# src/alerts/telegram_bot.py
"""
MirrorX Telegram Alpha Broadcast Bot
Sends top alpha signal updates to a Telegram channel when new signals appear.
"""

import os, requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_alpha_alert(signals):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram broadcast skipped (no credentials).")
        return False

    top = signals[0]
    msg = (
        f"🚀 *MirrorX Alpha Signal Update*\n\n"
        f"Top Token: `{top['symbol']}`\n"
        f"Score: {top['alpha_score']}\n"
        f"Liquidity: ${top['liquidity_usd']:,.0f}\n"
        f"Volume: ${top['volume_24h']:,.0f}\n"
        f"Sentiment: {top['sentiment']}\n\n"
        f"View dashboard → https://mirrorx-backend.onrender.com/fusion-dashboard"
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
        print("[BROADCAST] Alpha alert sent successfully.")
        return True
    except Exception as e:
        print("Telegram broadcast error:", e)
        return False
