# src/services/telegram_router.py
from __future__ import annotations

import os
import time
from typing import Optional

from src.services.telegram_alerts import send_telegram_message


# ============================================================
# Tiered Telegram Routing
# ============================================================
# You can set different Chat IDs per tier:
# - TELEGRAM_CHAT_ID_FREE
# - TELEGRAM_CHAT_ID_PREMIUM
# - TELEGRAM_CHAT_ID_ELITE
#
# If not set, it will fallback to your default TELEGRAM_CHAT_ID.
# ============================================================

FREE_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_FREE", "").strip()
PREMIUM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_PREMIUM", "").strip()
ELITE_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID_ELITE", "").strip()

# Optional paywall delay (premium gets earlier, free gets later)
FREE_DELAY_SECONDS = float(os.getenv("ALPHA_FREE_DELAY_SECONDS", "0"))
PREMIUM_DELAY_SECONDS = float(os.getenv("ALPHA_PREMIUM_DELAY_SECONDS", "0"))
ELITE_DELAY_SECONDS = float(os.getenv("ALPHA_ELITE_DELAY_SECONDS", "0"))


def _default_chat_id() -> str:
    return os.getenv("TELEGRAM_CHAT_ID", "").strip()


def send_to_tier(message: str, tier: str) -> None:
    """
    Sends message to the specified tier.
    Tier: "free" | "premium" | "elite"
    Falls back to default TELEGRAM_CHAT_ID if tier id isn't configured.
    """
    tier = (tier or "").lower().strip()

    if tier == "free":
        chat_id = FREE_CHAT_ID or _default_chat_id()
        delay = FREE_DELAY_SECONDS
    elif tier == "premium":
        chat_id = PREMIUM_CHAT_ID or _default_chat_id()
        delay = PREMIUM_DELAY_SECONDS
    elif tier == "elite":
        chat_id = ELITE_CHAT_ID or _default_chat_id()
        delay = ELITE_DELAY_SECONDS
    else:
        chat_id = _default_chat_id()
        delay = 0.0

    if delay > 0:
        time.sleep(delay)

    # ✅ If telegram_alerts.py supports chat_id, use it; otherwise it will ignore it safely.
    try:
        send_telegram_message(message, chat_id=chat_id)
    except TypeError:
        # backward compatible if your send_telegram_message(msg) only accepts 1 arg
        send_telegram_message(message)
