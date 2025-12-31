# src/services/twitterRapid.py
"""
TwitterRapid data service for MirrorX Intelligence API.
Connects to the Twitter RapidAPI integration (or simulates data for fallback).
"""

import os
import requests

# Optional environment variable if you later store a real API key
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", None)
RAPIDAPI_HOST = "twitter154.p.rapidapi.com"

def get_twitterRapid_likes(pid: str = "mirrorx_demo_post", count: int = 5):
    """
    Fetches the latest likes for a given Twitter post ID from the RapidAPI endpoint.
    If no credentials or endpoint are configured, returns placeholder test data.
    """
    try:
        if RAPIDAPI_KEY:
            url = f"https://{RAPIDAPI_HOST}/tweet/likes"
            headers = {
                "x-rapidapi-key": RAPIDAPI_KEY,
                "x-rapidapi-host": RAPIDAPI_HOST
            }
            params = {"tweet_id": pid, "count": count}
            res = requests.get(url, headers=headers, params=params, timeout=10)
            res.raise_for_status()
            data = res.json()
            return {
                "postId": pid,
                "likesCount": len(data.get("results", [])),
                "users": data.get("results", [])
            }

        # fallback mode: safe mock data
        return {
            "postId": pid,
            "likesCount": count,
            "users": [
                {"username": "solana_alpha"},
                {"username": "bonk_whale"},
                {"username": "wifarmy"},
                {"username": "meme_hunter"},
                {"username": "mirrorx_data"}
            ]
        }

    except Exception as e:
        print("TwitterRapid fetch error:", e)
        return {"postId": pid, "likesCount": 0, "users": []}
