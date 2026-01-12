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
# ------------------------------------------------------------------
# Dual-mounting for GPT compatibility: most blueprints available under
# both /api/... and the root path where relevant.
# ==================================================================

# Fusion: keep only /api (GPT doesn't call it directly)
app.register_blueprint(fusion_bp, url_prefix="/api")

# Crypto: serve under both /crypto/* and /api/crypto/*
app.register_blueprint(crypto_bp, url_prefix="/crypto")
app.register_blueprint(crypto_bp, url_prefix="/api/crypto", name="crypto_api")

# Intelligence: serve under both /intel/* and /api/intel/*
app.register_blueprint(intel_bp, url_prefix="/intel")
app.register_blueprint(intel_bp, url_prefix="/api/intel", name="intel_api")

# TwitterRapid: serve under both /twitterRapid/* and /api/twitterRapid/*
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

# ✅ Alpha Trend Engine
from src.routes.signals_trends import signals_trends_bp
app.register_blueprint(signals_trends_bp, url_prefix="/api")

# ✅ DexScreener Proxy (THIS is the one you wanted)
from src.routes.dex_proxy import dex_proxy_bp
app.register_blueprint(dex_proxy_bp, url_prefix="/api", name="dex_proxy_api")

# ✅ Alerts API (Telegram send endpoint, recent alerts, etc.)
from src.routes.alerts_api import alerts_api_bp
app.register_blueprint(alerts_api_bp, url_prefix="/api", name="alerts_api")

# ---- Conditional Blueprints ----
try:
    from src.routes.rpc_status import rpc_status_bp
    app.register_blueprint(rpc_status_bp, url_prefix="")
except Exception as e:
    print(f"[WARN] RPC Status route not loaded: {e}")

if os.getenv("ENABLE_ALERT_INGEST", "0") == "1":
    try:
        from src.routes.alerts import alerts_bp
        app.register_blueprint(alerts_bp, url_prefix="")
    except Exception as e:
        print(f"[WARN] Alerts failed to import: {e}")

if os.getenv("ENABLE_AGENTS", "0") == "1":
    try:
        from src.routes.agents import agents_bp
        app.register_blueprint(agents_bp, url_prefix="")
    except Exception as e:
        print(f"[WARN] Agents failed to import: {e}")

if os.getenv("ENABLE_SMOKE", "0") == "1":
    try:
        from src.routes.smoke import smoke_bp
        app.register_blueprint(smoke_bp, url_prefix="")
    except Exception as e:
        print(f"[WARN] Smoke failed to import: {e}")

from src.routes.alerts_test import alerts_test_bp
app.register_blueprint(alerts_test_bp)
# ✅ MirrorStock detector (safe import)
try:
    from src.services.mirrorstock_detector import push_mirrorstock_alerts
except Exception as e:
    push_mirrorstock_alerts = None
    print(f"[WARN] MirrorStock detector not loaded: {e}")
# ---- ENV Diagnostic ----
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

# ---- Serve OpenAPI Spec ----
@app.route("/openapi.json", methods=["GET"])
def serve_openapi():
    """Serve OpenAPI schema for GPT Actions"""
    base_dir = os.path.dirname(os.path.dirname(__file__))  # one level up from /src
    file_path = os.path.join(base_dir, "openapi.json")
    if os.path.exists(file_path):
        return send_from_directory(base_dir, "openapi.json")
    return jsonify({"error": "openapi.json not found"}), 404


# ---- Fusion Dashboard UI ----
@app.route("/fusion-dashboard", methods=["GET"])
def serve_fusion_dashboard():
    """Serve the real-time Fusion Intelligence dashboard"""
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), "analytics/ui"),
        "fusion_dashboard.html"
    )

# ---- Automated Trend Scheduler ----
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import threading
import requests

# ✅ Birdeye WS ignition (optional)
if os.getenv("ENABLE_BIRDEYE_WS", "0") == "1":
    try:
        from src.services.birdeye_ws import start_birdeye_ws_thread
        start_birdeye_ws_thread()
    except Exception as e:
        print(f"[WARN] Birdeye WS not started: {e}")
else:
    print("⚠️ Birdeye WS disabled (set ENABLE_BIRDEYE_WS=1 to enable).")
# ✅ Import Alpha Detectors
from src.services.alpha_detector import push_alpha_alerts

# Alpha fusion may fail if it still imports old alpha_detector functions
# Keep it optional so deploy doesn't die
try:
    from src.services.alpha_fusion import push_fused_alpha_alerts
except Exception as e:
    push_fused_alpha_alerts = None
    print(f"[WARN] Alpha Fusion not loaded: {e}")

# ✅ MirrorStock detector (safe import)
try:
    from src.services.mirrorstock_detector import push_mirrorstock_alerts
except Exception as e:
    push_mirrorstock_alerts = None
    print(f"[WARN] MirrorStock detector not loaded: {e}")


def trigger_trends_job():
    """MirrorX unified job runner (runs every 3 hours)."""
    try:
        print(f"[SCHEDULER] Triggering MirrorX cycle at {datetime.utcnow().isoformat()}Z")

        # 1️⃣ Run Dex-only Alpha Detector
        print("[SCHEDULER] → Running Alpha Detector (DEX layer)…")
        push_alpha_alerts()

        # 2️⃣ Run Dex + Fusion Alpha Detector (optional)
        if push_fused_alpha_alerts:
            print("[SCHEDULER] → Running Alpha Fusion (DEX + Fusion layer)…")
            push_fused_alpha_alerts()
        else:
            print("[SCHEDULER] → Alpha Fusion skipped (not loaded).")

        # 3️⃣ Trigger trend engine endpoint
        res = requests.get("https://mirrorx-backend.onrender.com/api/signals/trends", timeout=20)
        print(f"[SCHEDULER] Trend job response: {res.status_code}")

        print("✅ MirrorX job cycle complete.\n")
    except Exception as e:
        print(f"[SCHEDULER] MirrorX unified job failed: {e}")


def start_scheduler():
    """Start schedulers in a background thread."""
    scheduler = BackgroundScheduler(daemon=True)

    # MirrorX: every 3 hours
    scheduler.add_job(trigger_trends_job, "interval", hours=3, next_run_time=datetime.utcnow())

    # MirrorStock: every 1 hour (runs separately)
    if push_mirrorstock_alerts:
        scheduler.add_job(push_mirrorstock_alerts, "interval", hours=1, next_run_time=datetime.utcnow())
        print("✅ MirrorStock Scheduler initialized (runs every 1 hour).")
    else:
        print("⚠️ MirrorStock Scheduler not enabled (detector not loaded).")

    scheduler.start()
    print("✅ Scheduler initialized.")

# ✅ MirrorStock detector (safe import)
try:
    from src.services.mirrorstock_detector import push_mirrorstock_alerts
except Exception as e:
    push_mirrorstock_alerts = None
    print(f"[WARN] MirrorStock detector not loaded: {e}")
# Run the scheduler after app creation (only if enabled)
if os.getenv("ENABLE_SCHEDULER", "0") == "1":
    threading.Thread(target=start_scheduler, daemon=True).start()
else:
    print("⚠️ Scheduler disabled (set ENABLE_SCHEDULER=1 to enable).")

# ---- Run Server ----
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.PORT)
