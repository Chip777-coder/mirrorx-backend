# src/app.py
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import os
import json

# ---- Core Config ----
from src.config import settings
from src.routes.crypto import crypto_bp
from src.routes.intel import intel_bp
from src.routes.twitterRapid import twitter_bp
from src.routes.fusion import fusion_bp  # ✅ Fusion blueprint

# ---- Load RPCs ----
RPC_FILE = os.path.join(os.path.dirname(__file__), "rpcs", "rpc_list.json")


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

# ---- Initialize Flask ----
app = Flask(__name__)
CORS(app)

# ---- Root Routes ----
@app.route("/")
def home():
    return "🚀 MirroraX backend is live!"


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})


@app.route("/rpc-list")
def rpc_list():
    return jsonify(RPC_URLS)


# ==================================================================
# ✅ BLUEPRINT REGISTRATION
# ==================================================================

# Fusion: keep only /api
app.register_blueprint(fusion_bp, url_prefix="/api")

# Crypto
app.register_blueprint(crypto_bp, url_prefix="/crypto")
app.register_blueprint(crypto_bp, url_prefix="/api/crypto", name="crypto_api")

# Intelligence
app.register_blueprint(intel_bp, url_prefix="/intel")
app.register_blueprint(intel_bp, url_prefix="/api/intel", name="intel_api")

# TwitterRapid
app.register_blueprint(twitter_bp, url_prefix="/twitterRapid")
app.register_blueprint(twitter_bp, url_prefix="/api/twitterRapid", name="twitterRapid_api")

# ---- Status and HealthCard ----
from src.routes.status import status_bp
app.register_blueprint(status_bp, url_prefix="/api")

from src.routes.health_card import health_bp
app.register_blueprint(health_bp)

# ---- Signals and History ----
from src.routes.signals import signals_bp
app.register_blueprint(signals_bp, url_prefix="/api")

from src.routes.signal_history import signal_history_bp
app.register_blueprint(signal_history_bp, url_prefix="/api")

from src.routes.signals_history import signals_history_bp
app.register_blueprint(signals_history_bp)

# ---- Trend Engine ----
from src.routes.signals_trends import signals_trends_bp
app.register_blueprint(signals_trends_bp, url_prefix="/api")

# ---- DexScreener Proxy ----
from src.routes.dex_proxy import dex_proxy_bp
app.register_blueprint(dex_proxy_bp, url_prefix="/api", name="dex_proxy_api")

# ---- Alerts API ----
from src.routes.alerts_api import alerts_api_bp
app.register_blueprint(alerts_api_bp, url_prefix="/api", name="alerts_api")

# ---- Parlays (FIXED & SAFE) ----
try:
    from src.routes.parlays import parlays_bp
    app.register_blueprint(parlays_bp)
    app.register_blueprint(parlays_bp, url_prefix="/api", name="parlays_api")
except Exception as e:
    print(f"[WARN] Parlays not loaded: {e}")

# ---- Conditional Blueprints ----
try:
    from src.routes.rpc_status import rpc_status_bp
    app.register_blueprint(rpc_status_bp)
except Exception as e:
    print(f"[WARN] RPC Status route not loaded: {e}")

if os.getenv("ENABLE_ALERT_INGEST", "0") == "1":
    try:
        from src.routes.alerts import alerts_bp
        app.register_blueprint(alerts_bp)
    except Exception as e:
        print(f"[WARN] Alerts failed to import: {e}")

if os.getenv("ENABLE_AGENTS", "0") == "1":
    try:
        from src.routes.agents import agents_bp
        app.register_blueprint(agents_bp)
    except Exception as e:
        print(f"[WARN] Agents failed to import: {e}")

if os.getenv("ENABLE_SMOKE", "0") == "1":
    try:
        from src.routes.smoke import smoke_bp
        app.register_blueprint(smoke_bp)
    except Exception as e:
        print(f"[WARN] Smoke failed to import: {e}")

from src.routes.alerts_test import alerts_test_bp
app.register_blueprint(alerts_test_bp)
@app.route("/test/telegram")
def test_bot():
    from analytics.mirrax.parlay_builder import generate_multiple_parlays
    from bots.telegram_bot import send_parlay_to_telegram

    parlay = generate_multiple_parlays()[0]
    send_parlay_to_telegram(parlay)
    return "Sent"
# ---- ENV Diagnostic ----
@app.route("/test-env")
def test_env():
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
        "quicknode_http": bool(settings.QUICKNODE_HTTP),
        "quicknode_wss": bool(settings.QUICKNODE_WSS),
    }

# ---- OpenAPI ----
@app.route("/openapi.json")
def serve_openapi():
    base_dir = os.path.dirname(os.path.dirname(__file__))
    file_path = os.path.join(base_dir, "openapi.json")
    if os.path.exists(file_path):
        return send_from_directory(base_dir, "openapi.json")
    return jsonify({"error": "openapi.json not found"}), 404

# ---- Fusion Dashboard ----
@app.route("/fusion-dashboard")
def serve_fusion_dashboard():
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), "analytics/ui"),
        "fusion_dashboard.html"
    )

# ---- Scheduler ----
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import threading
import requests

if os.getenv("ENABLE_BIRDEYE_WS", "0") == "1":
    try:
        from src.services.birdeye_ws import start_birdeye_ws_thread
        start_birdeye_ws_thread()
    except Exception as e:
        print(f"[WARN] Birdeye WS not started: {e}")

from src.services.alpha_detector import push_alpha_alerts

try:
    from src.services.alpha_fusion import push_fused_alpha_alerts
except Exception:
    push_fused_alpha_alerts = None

try:
    from src.services.mirrorstock_detector import push_mirrorstock_alerts
except Exception:
    push_mirrorstock_alerts = None


def trigger_trends_job():
    print(f"[SCHEDULER] Triggering MirrorX cycle at {datetime.utcnow().isoformat()}Z")
    push_alpha_alerts()
    if push_fused_alpha_alerts:
        push_fused_alpha_alerts()
    requests.get("https://mirrorx-backend.onrender.com/api/signals/trends", timeout=20)
    print("✅ MirrorX job cycle complete.\n")


def start_scheduler():
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(trigger_trends_job, "interval", hours=3, next_run_time=datetime.utcnow())

    if push_mirrorstock_alerts:
        scheduler.add_job(push_mirrorstock_alerts, "interval", hours=1, next_run_time=datetime.utcnow())
        print("✅ MirrorStock Scheduler initialized.")

    scheduler.start()
    print("✅ Scheduler initialized.")


if os.getenv("ENABLE_SCHEDULER", "0") == "1":
    threading.Thread(target=start_scheduler, daemon=True).start()

# ---- Run Server ----
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.PORT)
