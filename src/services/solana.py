# src/services/solana.py
"""
Solana ecosystem data service.
Returns trending tokens or metrics for /api/crypto/solana and intel endpoints.
"""

import requests

BASE_URL = "https://api.coingecko.com/api/v3"   # or any Solana data source

def get_solana_trending():
    """Fetch top Solana ecosystem tokens from CoinGecko."""
    try:
        r = requests.get(f"{BASE_URL}/coins/markets", params={
            "vs_currency": "usd",
            "category": "solana-ecosystem",
            "order": "volume_desc",
            "per_page": 25,
            "page": 1
        }, timeout=10)
        r.raise_for_status()
        data = r.json()
        # Normalize minimal structure
        return [
            {
                "symbol": d.get("symbol", "").upper(),
                "name": d.get("name"),
                "price": d.get("current_price"),
                "volume_24h": d.get("total_volume"),
                "change_24h": d.get("price_change_percentage_24h"),
                "market_cap": d.get("market_cap")
            }
            for d in data
            if "sol" in d.get("categories", []) or "solana" in d.get("name", "").lower()
        ]
    except Exception as e:
        print("Solana fetch error:", e)
        return []
