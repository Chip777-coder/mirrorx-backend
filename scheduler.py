# scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
import os
import requests

# --- MirrorStock (stocks) alerts
# Make sure these files exist:
#   src/services/mirrorstock_detector.py
#   src/services/stock_radar.py
#   src/services/chart_render.py
from src.services.mirrorstock_detector import push_mirrorstock_alerts


def fetch_intelligence():
    print("🔁 Fetching crypto + social intelligence data...")
    try:
        base = (os.getenv("COINGECKO_BASE_URL") or "https://api.coingecko.com/api/v3").rstrip("/")
        r = requests.get(
            f"{base}/coins/markets",
            params={"vs_currency": "usd", "category": "solana-ecosystem"},
            timeout=12,
        )
        r.raise_for_status()
        data = r.json() if isinstance(r.json(), list) else []
        print(f"✅ Updated Solana token data: {len(data)} entries")
    except Exception as e:
        print(f"❌ fetch_intelligence failed: {e}")


def run_mirrorstock():
    """
    Runs the MirrorStock stock detector + sends Telegram alerts.
    Uses env vars:
      - POLYGON_API_KEY
      - MIRRORSTOCK_TELEGRAM_BOT_TOKEN
      - MIRRORSTOCK_TELEGRAM_CHAT_ID
    """
    try:
        print("📈 Running MirrorStock detector...")
        push_mirrorstock_alerts()
        print("✅ MirrorStock run complete.")
    except Exception as e:
        print(f"❌ MirrorStock scheduler run failed: {e}")


_scheduler = None  # module-level singleton


def start_scheduler():
    """
    Starts the background scheduler exactly once.
    Call this from your app startup (e.g., main.py).
    """
    global _scheduler
    if _scheduler is not None:
        print("🟡 Scheduler already running (skipping start).")
        return _scheduler

    scheduler = BackgroundScheduler()

    # --- Crypto intelligence every 10 min
    scheduler.add_job(fetch_intelligence, "interval", minutes=int(os.getenv("CRYPTO_JOB_MINUTES", "10")))

    # --- MirrorStock every 10 min (change with env if you want)
    scheduler.add_job(run_mirrorstock, "interval", minutes=int(os.getenv("MIRRORSTOCK_JOB_MINUTES", "10")))

    scheduler.start()
    _scheduler = scheduler

    print("🕒 Scheduler started.")
    print(f"   - fetch_intelligence every {os.getenv('CRYPTO_JOB_MINUTES', '10')} minutes")
    print(f"   - MirrorStock every {os.getenv('MIRRORSTOCK_JOB_MINUTES', '10')} minutes")

    return scheduler
