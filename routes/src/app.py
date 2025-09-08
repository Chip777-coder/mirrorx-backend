from flask import Flask, jsonify
import os, json
from routes.rpc_status import rpc_status_bp

app = Flask(__name__)

# --- Load RPC list (from src/rpcs/rpc_list.json) ---
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

@app.route("/")
def home():
    return "MirrorX backend is live ✅"

@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})

@app.route("/rpc-list")
def rpc_list():
    return jsonify(RPC_URLS)

# register blueprint routes (/rpc-status)
app.register_blueprint(rpc_status_bp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
