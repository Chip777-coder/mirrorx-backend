from flask import Blueprint, jsonify
import os, json, requests
from concurrent.futures import ThreadPoolExecutor, as_completed

rpc_status_bp = Blueprint("rpc_status_bp", __name__)

# --- Load RPC list ---
RPC_FILE = os.path.join(os.path.dirname(__file__), "..", "rpcs", "rpc_list.json")

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

@rpc_status_bp.route("/rpc-list")
def rpc_list():
    # return a raw JSON array for your frontend
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

@rpc_status_bp.route("/rpc-status")
def rpc_status():
    results = []
    max_workers = int(os.environ.get("RPC_MAX_WORKERS", "10"))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_rpc, u): u for u in RPC_URLS}
        for fut in as_completed(futures):
            results.append(fut.result())
    return jsonify(results)
