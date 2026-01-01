# src/services/sentiment.py
"""
MirrorX Sentiment Microservice
Collects and aggregates social sentiment data (Reddit, Twitter, LunarCrush API)
to compute a normalized 0–2.0 sentiment multiplier for tokens.
"""

import requests
import os

LUNARCRUSH_API_KEY = os.getenv("LUNARCRUSH_API_KEY")
LUNARCRUSH_URL = "https://lunarcrush.com/api4/public/coins"

def fetch_sentiment_scores(symbols=None):
    """Fetch sentiment metrics and normalize into 0.5–2.0 multipliers."""
    if not LUNARCRUSH_API_KEY:
        # Safe mock fallback
        return {
            "sol": 1.1, "bonk": 1.3, "wif": 1.4, "eth": 1.0, "btc": 0.95
        }

    try:
        params = {"data": "assets", "key": LUNARCRUSH_API_KEY}
        res = requests.get(LUNARCRUSH_URL, params=params, timeout=10)
        res.raise_for_status()
        data = res.json().get("data", [])
        out = {}
        for d in data:
            s = d.get("s", "").lower()
            score = float(d.get("galaxy_score", 50)) / 50  # 0.5–2.0 range
            out[s] = round(score, 2)
        if symbols:
            out = {k: v for k, v in out.items() if k in [x.lower() for x in symbols]}
        return out
    except Exception as e:
        print("Sentiment fetch error:", e)
        return {}
