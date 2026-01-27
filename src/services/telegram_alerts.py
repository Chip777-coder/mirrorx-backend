# src/services/telegram_alerts.py
import os
import requests
from typing import Optional, Tuple

TELEGRAM_API_BASE = "https://api.telegram.org"


def _get_telegram_creds(channel: str = "default") -> Tuple[Optional[str], Optional[str], str]:
    """
    Resolve Telegram bot token + chat_id by channel.

    Backward compatible:
      - legacy -> TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID

    Primary channels:
      - mirrorx      -> MIRRORX_TELEGRAM_BOT_TOKEN / MIRRORX_TELEGRAM_CHAT_ID
      - mirrorstock  -> MIRRORSTOCK_TELEGRAM_BOT_TOKEN / MIRRORSTOCK_TELEGRAM_CHAT_ID

    Notes:
      - "default" routes to mirrorx (by design), so ALWAYS pass channel="mirrorstock"
        for MirrorStock messages.
    """
    ch = (channel or "default").strip().lower()

    if ch in ("default", "main", "primary", "mirrorx"):
        token = os.getenv("MIRRORX_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("MIRRORX_TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
        return token, chat_id, "mirrorx"

    if ch in ("stock", "mirrorstock", "mirrorrastock", "mirrora_stock"):
        token = os.getenv("MIRRORSTOCK_TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("MIRRORSTOCK_TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")
        return token, chat_id, "mirrorstock"

    # fallback to legacy
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    return token, chat_id, ch


def send_telegram_message(message: str, channel: str = "default") -> bool:
    """Send a text message to Telegram using the selected channel credentials."""
    token, chat_id, resolved = _get_telegram_creds(channel)

    if not token or not chat_id:
        print(f"[WARN] Telegram credentials not configured for channel='{resolved}'.")
        return False

    try:
        url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        response = requests.post(url, data=payload, timeout=12)

        if response.status_code == 200:
            print(f"[TELEGRAM] Message sent → channel='{resolved}' chat_id={chat_id}")
            return True

        print(f"[TELEGRAM] Failed → channel='{resolved}' status={response.status_code} body={response.text}")
        return False

    except Exception as e:
        print(f"[ERROR] Telegram sendMessage failed → channel='{resolved}': {e}")
        return False


def send_telegram_photo(image_bytes: bytes, caption: str = "", channel: str = "default") -> bool:
    """Send a photo (PNG/JPG bytes) to Telegram using the selected channel credentials."""
    token, chat_id, resolved = _get_telegram_creds(channel)

    if not token or not chat_id:
        print(f"[WARN] Telegram credentials not configured for channel='{resolved}'.")
        return False

    if not image_bytes:
        print(f"[WARN] Empty image bytes; not sending photo → channel='{resolved}'.")
        return False

    try:
        url = f"{TELEGRAM_API_BASE}/bot{token}/sendPhoto"
        files = {"photo": ("chart.png", image_bytes)}
        data = {
            "chat_id": chat_id,
            "caption": (caption or "")[:900],
            "parse_mode": "HTML",
        }
        response = requests.post(url, data=data, files=files, timeout=15)

        if response.status_code == 200:
            print(f"[TELEGRAM] Photo sent → channel='{resolved}' chat_id={chat_id}")
            return True

        print(f"[TELEGRAM] Photo failed → channel='{resolved}' status={response.status_code} body={response.text}")
        return False

    except Exception as e:
        print(f"[ERROR] Telegram sendPhoto failed → channel='{resolved}': {e}")
        return False


def test_telegram(channel: str = "default") -> bool:
    """Quick sanity test you can call from anywhere."""
    return send_telegram_message("✅ Telegram test: alerts are sending.", channel=channel)
