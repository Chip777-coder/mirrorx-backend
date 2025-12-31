# src/app.py
from flask import Flask, jsonify
from flask_cors import CORS
import os
import json
from src.config import settings  # import once, from the src package
from src.routes.crypto import crypto_bp
from src.routes.intel import intel_bp
from src.routes.twitterRapid import twitter_bp
# ----- Load RPCs (keeps your old /rpc-list behavior) -----
RPC_FILE = os.path.join(os.path.dirname(__file__), "rpcs", "rpc_list.json")
# app.py or src/app.py
from flask import Flask
from flask_cors import CORS

# Import your fusion blueprint
from src.routes.fusion import fusion_bp  # ✅ make sure this path matches your folder

app = Flask(__name__)
CORS(app)

# Register blueprints
app.register_blueprint(fusion_bp, url_prefix="/api")

@app.route("/")
def home():
    return "🚀 MirroraX backend is live!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
def load_rpc_urls():
    try:
        with open(RPC_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, dict) and "rpcs" in data:
                return data["rpcs"]
            if isinstance(data, list):
                return data
    except Exception as e:
        print(f"Error loading RPC list: {e}")
    return []

RPC_URLS = load_rpc_urls()

# ----- App -----
app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "MirrorX backend is live ✅"

@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})

@app.route("/rpc-list")
def rpc_list():
    return jsonify(RPC_URLS)

# ----- Blueprints -----
from .routes.rpc_status import rpc_status_bp
app.register_blueprint(rpc_status_bp, url_prefix="")

if os.getenv("ENABLE_ALERT_INGEST", "0") == "1":
    try:
        from .routes.alerts import alerts_bp
        app.register_blueprint(alerts_bp, url_prefix="")
    except Exception as e:
        print(f"[WARN] Alerts failed to import: {e}")

if os.getenv("ENABLE_AGENTS", "0") == "1":
    try:
        from .routes.agents import agents_bp
        app.register_blueprint(agents_bp, url_prefix="")
    except Exception as e:
        print(f"[WARN] Agents failed to import: {e}")

if os.getenv("ENABLE_SMOKE", "0") == "1":
    try:
        from .routes.smoke import smoke_bp
        app.register_blueprint(smoke_bp, url_prefix="")
    except Exception as e:
        print(f"[WARN] Smoke failed to import: {e}")
app.register_blueprint(crypto_bp, url_prefix="/crypto")
app.register_blueprint(intel_bp, url_prefix="/intel")
app.register_blueprint(twitter_bp, url_prefix="/twitterRapid")
# ----- Test ENV endpoint -----
@app.route("/test-env")
def test_env():
    """Check which API keys are set without exposing full values."""
    return {
        "coingecko": bool(settings.COINGECKO_API_BASE),
        "coinmarketcap": bool(settings.COINMARKETCAP_API_KEY),
        "defillama": bool(settings.DEFILLAMA_API_BASE),
        "dexscreener": bool(settings.DEXSCREENER_API_BASE),
        "lunarcrush": bool(settings.LUNARCRUSH_API_KEY),
        "cryptopanic": bool(settings.CRYPTOPANIC_API_KEY),
        "alchemy": bool(settings.ALCHEMY_API_KEY),
        "moralis": bool(settings.MORALIS_API_KEY),
        "solscan": bool(settings.SOLSCAN_API_KEY),
        "push": bool(settings.PUSH_API_KEY),
        "ankr": bool(settings.ANKR_API_KEY),
        "sentiment": bool(getattr(settings, "SENTIMENT_API_KEY", "")),
        "shyft": bool(getattr(settings, "SHYFT_API_KEY", "")),
        "quicknode_http": bool(settings.QUICKNODE_HTTP),
        "quicknode_wss": bool(settings.QUICKNODE_WSS),
    }

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.PORT)
from flask import send_from_directory
import os

@app.route("/openapi.json", methods=["GET"])
def serve_openapi():
    """Serve OpenAPI schema for GPT Actions"""
    return send_from_directory(os.getcwd(), "openapi.json")
