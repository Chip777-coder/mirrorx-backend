from flask import Flask, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv

from routes.rpc_status import rpc_status_bp
from routes.alerts import alerts_bp
from routes.agents import agents_bp

load_dotenv()

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "MirrorX backend is live ✅"

@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})

app.register_blueprint(rpc_status_bp, url_prefix="")
if os.getenv("ENABLE_ALERT_INGEST", "1") == "1":
    app.register_blueprint(alerts_bp, url_prefix="")
if os.getenv("ENABLE_AGENTS", "1") == "1":
    app.register_blueprint(agents_bp, url_prefix="")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
from flask import Flask, jsonify
# ... your existing imports ...

app = Flask(__name__)

# --- existing routes here ("/", "/rpc-list", "/rpc-status", "/healthz") ---

# Register blueprints AFTER app is created
from routes.rpc_status import rpc_status_bp
app.register_blueprint(rpc_status_bp)

from routes.alerts import alerts_bp
app.register_blueprint(alerts_bp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
