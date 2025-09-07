import json, requests
from config import DISCORD_WEBHOOK_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_alert(payload: dict):
    title = payload.get("title") or "MirrorX Alert"
    message = payload.get("message") or json.dumps(payload, ensure_ascii=False)
    ok = True
    errs = []

    if DISCORD_WEBHOOK_URL:
        try:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": f"**{title}**\n{message}"}, timeout=8)
        except Exception as e:
            ok, errs = False, errs + [f"discord: {e}"]

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": f"{title}\n{message}"}, timeout=8)
        except Exception as e:
            ok, errs = False, errs + [f"telegram: {e}"]

    return ok, (", ".join(errs) if errs else None)
