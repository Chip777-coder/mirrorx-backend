# src/app.py
from flask import Flask, jsonify
from flask_cors import CORS
import os
import json

# ----- Load RPCs (keeps your old /rpc-list behavior) -----
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

# ----- App -----
app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    # Keep this simple and 200 so Render's first GET doesn't 404
    return "MirrorX backend is live ✅"

@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})

@app.route("/rpc-list")
def rpc_list():
    return jsonify(RPC_URLS)

# ----- Blueprints -----
# Always present
from routes.rpc_status import rpc_status_bp
app.register_blueprint(rpc_status_bp, url_prefix="")

# Optional blueprints (don’t crash if files are missing)
if os.getenv("ENABLE_ALERT_INGEST", "0") == "1":
    try:
        from routes.alerts import alerts_bp
        app.register_blueprint(alerts_bp, url_prefix="")
    except Exception as e:
        print(f"[WARN] ENABLE_ALERT_INGEST=1 but routes/alerts.py not found or failed to import: {e}")

if os.getenv("ENABLE_AGENTS", "0") == "1":
    try:
        from routes.agents import agents_bp
        app.register_blueprint(agents_bp, url_prefix="")
    except Exception as e:
        print(f"[WARN] ENABLE_AGENTS=1 but routes/agents.py not found or failed to import: {e}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
# BEFORE
# from routes.rpc_status import rpc_status_bp
# from routes.alerts import alerts_bp
# from routes.agents import agents_bp
# from routes.smoke import smoke_bp   # if you added /smoke

# AFTER (use one style; I recommend relative)
from .routes.rpc_status import rpc_status_bp
from .routes.alerts import alerts_bp
from .routes.agents import agents_bp
from .routes.smoke import smoke_bp  # if present
