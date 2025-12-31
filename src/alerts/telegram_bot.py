from telegram import Bot
from src.services.coinmarketcap import get_cmc_listings
bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
def send_top_alerts():
    data = get_cmc_listings()[:5]
    msg = "\n".join([f"{t['symbol']}: {round(t['quote']['USD']['price'],6)}" for t in data])
    bot.send_message(chat_id=os.getenv("CHAT_ID"), text=f"🔥 Top Movers:\n{msg}")
