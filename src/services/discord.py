# src/services/discord.py
"""
Discord data service for MirrorX Intelligence API.
Fetches or simulates recent crypto-related Discord sentiment and activity.
"""

import requests

DISCORD_WEBHOOK_URL = None  # optional, only if you use a real webhook or API

def get_discord_data():
    """
    Returns summarized Discord sentiment data.
    Replace this stub with your live data pipeline later.
    """
    try:
        # Example: pull Discord message volume from an internal data source
        # r = requests.get("https://your-discord-api-endpoint/crypto-intel")
        # return r.json()

        # Temporary fallback (no crash)
        return [
            {
                "server": "Solana Traders",
                "mentions": 1284,
                "sentiment": "bullish",
                "top_tokens": ["SOL", "WIF", "BONK"]
            },
            {
                "server": "MemeCoin Lounge",
                "mentions": 932,
                "sentiment": "neutral",
                "top_tokens": ["DOGE", "PEPE", "SHIB"]
            }
        ]
    except Exception as e:
        print("Discord fetch error:", e)
        return []
