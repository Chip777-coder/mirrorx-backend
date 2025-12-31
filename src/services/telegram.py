# src/services/telegram.py
"""
Telegram data service for MirrorX Intelligence API.
Fetches or simulates message volume and sentiment for crypto Telegram groups.
"""

def get_telegram_data():
    """
    Returns summarized Telegram group data.
    Replace this with live API scraping later.
    """
    try:
        return [
            {
                "group": "Solana Signals",
                "mentions": 2100,
                "sentiment": "bullish",
                "top_tokens": ["SOL", "MYRO", "BONK"]
            },
            {
                "group": "Crypto Alpha Feed",
                "mentions": 1675,
                "sentiment": "bearish",
                "top_tokens": ["BTC", "ETH", "ADA"]
            }
        ]
    except Exception as e:
        print("Telegram fetch error:", e)
        return []
