# src/routes/health_card.py
from flask import Blueprint, jsonify
import time, requests, psutil, os

health_bp = Blueprint("health_bp", __name__)

start_time = time.time()

def check_api_status(name, url, headers=None):
    try:
        start = time.time()
        res = requests.get(url, headers=headers, timeout=6)
        latency = round((time.time() - start) * 1000, 2)
        status = "OK" if res.status_code == 200 else "FAIL"
        return {"name": name, "status": status, "latency_ms": latency}
    except Exception:
        return {"name": name, "status": "DOWN", "latency_ms": None}

@health_bp.route("/api/health-card", methods=["GET"])
def health_card():
    uptime = round(time.time() - start_time, 2)
    mem = psutil.virtual_memory()

    # Quick checks of your key integrations
    checks = [
        check_api_status("CoinMarketCap", "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"),
        check_api_status("DexScreener", "https://api.dexscreener.com/token-profiles/latest/v1"),
        check_api_status("CryptoCompare", "https://min-api.cryptocompare.com/data/pricemulti?fsyms=BTC,ETH&tsyms=USD"),
    ]

    return jsonify({
        "uptime_sec": uptime,
        "memory": {
            "used_mb": round(mem.used / (1024**2), 2),
            "available_mb": round(mem.available / (1024**2), 2),
            "percent": mem.percent,
        },
        "system_status": checks,
        "environment": {
            "port": os.getenv("PORT", "10000"),
            "telegram_enabled": bool(os.getenv("TELEGRAM_TOKEN")),
            "redis_enabled": bool(os.getenv("REDIS_URL")),
        },
        "status": "healthy" if all(c["status"] == "OK" for c in checks) else "degraded"
    })
