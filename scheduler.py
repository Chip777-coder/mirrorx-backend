from apscheduler.schedulers.background import BackgroundScheduler
import requests
import os

def fetch_intelligence():
    print("🔁 Fetching crypto + social intelligence data...")
    try:
        coingecko = requests.get(f"{os.getenv('COINGECKO_BASE_URL')}/coins/markets", params={"vs_currency": "usd", "category": "solana-ecosystem"})
        print(f"✅ Updated Solana token data: {len(coingecko.json())} entries")
    except Exception as e:
        print(f"❌ Scheduler failed: {e}")

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_intelligence, "interval", minutes=10)
    scheduler.start()
    print("🕒 Scheduler started... every 10 minutes")
