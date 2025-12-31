import os, requests

def get_cmc_listings():
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
    headers = {"X-CMC_PRO_API_KEY": os.getenv("CMC_API_KEY")}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        return res.json().get("data", [])
    except Exception as e:
        print("CMC fetch error:", e)
        return []
# src/services/coinmarketcap.py
import os, requests

def get_cmc_listings():
    """
    Fetch top listings from CoinMarketCap using the API key
    stored in COINMARKETCAP_API_KEY.
    """
    url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
    headers = {"X-CMC_PRO_API_KEY": os.getenv("COINMARKETCAP_API_KEY")}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        return res.json().get("data", [])
    except Exception as e:
        print("CMC fetch error:", e)
        return []
