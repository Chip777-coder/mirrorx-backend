import os, requests

def get_crypto_compare():
    url = f"https://min-api.cryptocompare.com/data/top/totalvolfull?limit=50&tsym=USD&api_key={os.getenv('CC_API_KEY')}"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json().get("Data", [])
        mapping = {}
        for item in data:
            symbol = item.get("CoinInfo", {}).get("Name")
            if symbol:
                raw = item.get("RAW", {}).get("USD", {})
                mapping[symbol] = {"change24h": raw.get("CHANGE24HOUR", 0)}
        return mapping
    except Exception as e:
        print("CryptoCompare fetch error:", e)
        return {}
