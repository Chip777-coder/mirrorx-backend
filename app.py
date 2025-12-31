# src/app.py
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import os, json
from src.config import settings
from src.routes.crypto import crypto_bp
from src.routes.intel import intel_bp
from src.routes.twitterRapid import twitter_bp
from src.routes.fusion import fusion_bp
from flask import Flask
from src.routes.fusion import fusion_bp

app = Flask(__name__)
app.register_blueprint(fusion_bp, url_prefix="/api")
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

app.register_blueprint(crypto_bp, url_prefix="/crypto")
app.register_blueprint(intel_bp, url_prefix="/intel")
app.register_blueprint(twitter_bp, url_prefix="/twitterRapid")

@app.route("/openapi.json", methods=["GET"])
def serve_openapi():
    return send_from_directory(os.getcwd(), "openapi.json")

@app.route("/test-env")
def test_env():
    return {k: bool(v) for k, v in settings.__dict__.items() if not k.startswith("__")}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=settings.PORT)
