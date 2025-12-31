import requests

def get_dexscreener():
    url = "https://api.dexscreener.com/latest/dex/pairs"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print("DexScreener fetch error:", e)
        return []
