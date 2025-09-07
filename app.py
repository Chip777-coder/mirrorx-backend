from flask import Flask, jsonify
import requests
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)

# --- Load RPC list ---
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

@app.route("/rpc-list")
def rpc_list():
    # Return the raw list of URLs to stay compatible with your current frontend
    return jsonify(RPC_URLS)

def check_rpc(url, timeout=6):
    payload = {"jsonrpc": "2.0", "id": 1, "method": "getSlot", "params": []}
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        try:
            data = resp.json()
        except Exception:
            return {"rpc_url": url, "status": "Failed", "error": "Non-JSON response"}
        if "result" in data:
            return {"rpc_url": url, "status": "Success", "result": data["result"]}
        return {"rpc_url": url, "status": "Failed", "error": data.get("error", "No result returned")}
    except requests.exceptions.RequestException as e:
        return {"rpc_url": url, "status": "Failed", "error": str(e)}

@app.route("/rpc-status")
def rpc_status():
    results = []
    max_workers = int(os.environ.get("RPC_MAX_WORKERS", "10"))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_rpc, u): u for u in RPC_URLS}
        for fut in as_completed(futures):
            results.append(fut.result())
    return jsonify(results)

@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
