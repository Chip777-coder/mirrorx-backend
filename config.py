import os

PORT = int(os.getenv("PORT", "10000"))
RPC_TIMEOUT_SEC = float(os.getenv("RPC_TIMEOUT_SEC", "6"))
RPC_MAX_WORKERS = int(os.getenv("RPC_MAX_WORKERS", "16"))
RPC_TOP_N = int(os.getenv("RPC_TOP_N", "5"))

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
