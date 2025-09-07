from flask import Blueprint, jsonify, current_app
import requests
import json
import os
import concurrent.futures

rpc_status_bp = Blueprint('rpc_status_bp', __name__)

# Load the RPC list from the parent directory
rpc_file_path = os.path.join(os.path.dirname(__file__), "..", "rpcs", "rpc_list.json")
try:
    with open(rpc_file_path, "r") as f:
        rpc_list = json.load(f).get("rpcs", [])
except Exception as e:
    print(f"Error loading RPC list: {e}")
    rpc_list = []

@rpc_status_bp.route("/rpc-status")
def real_rpc_status():
    def check_rpc(url):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSlot",
            "params": []
        }
        try:
            response = requests.post(url, json=payload, timeout=6)
            data = response.json()
            if "result" in data:
                return {
                    "rpc_url": url,
                    "result": data["result"],
                    "status": "Success"
                }
            else:
                return {
                    "rpc_url": url,
                    "status": "Failed",
                    "error": data.get("error", "Unknown")
                }
        except Exception as e:
            return {
                "rpc_url": url,
                "status": "Failed",
                "error": str(e)
            }

    with concurrent.futures.ThreadPoolExecutor() as executor:
        results = list(executor.map(check_rpc, rpc_list))

    return jsonify(results)
