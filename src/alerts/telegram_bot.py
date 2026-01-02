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
# src/alerts/telegram_bot.py
import requests
import os
from datetime import datetime, timezone

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_trend_alert(trends: dict):
    """
    Send a summarized trend update to Telegram.
    Expected 'trends' is the JSON response from /api/signals/trends.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[BROADCAST] Telegram not configured; skipping trend alert.")
        return False

    try:
        emerging = trends.get("emerging", [])[:3]
        fading = trends.get("fading", [])[:3]
        ts = trends.get("timestamp", datetime.now(timezone.utc).isoformat())

        msg = "📈 *MirrorX Alpha Trend Update*\n\n"
        msg += f"🕒 `{ts}`\n\n"

        if emerging:
            msg += "🔥 *Top Emerging Tokens:*\n"
            for t in emerging:
                msg += f"• {t['symbol']} (`{t['trend_pct']}`)\n"
            msg += "\n"

        if fading:
            msg += "⚠️ *Top Fading Tokens:*\n"
            for t in fading:
                msg += f"• {t['symbol']} (`{t['trend_pct']}`)\n"

        msg += "\n🧠 MirrorX Alpha Trend Engine is live."

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown"
        }
        res = requests.post(url, json=payload, timeout=10)
        res.raise_for_status()
        print("[BROADCAST] Trend alert sent successfully.")
        return True
    except Exception as e:
        print(f"[WARN] Trend alert failed: {e}")
        return False
