from flask import Flask, jsonify
import requests
import json
import os

app = Flask(__name__)

# Load the RPC list safely from /rpcs/rpc_list.json
rpc_file_path = os.path.join(os.path.dirname(__file__), "rpcs", "rpc_list.json")
try:
    with open(rpc_file_path, "r") as f:
        rpc_list = json.load(f).get("rpcs", [])
except Exception as e:
    print(f"Error loading RPC list: {e}")
    rpc_list = []

@app.route("/")
def home():
    return "MirrorX backend is live ✅"

@app.route("/rpc-list")
def list_rpcs():
    return jsonify(rpc_list)

@app.route("/rpc-status")
def real_rpc_status():
    results = []
    for url in rpc_list:
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSlot",
                "params": []
            }
            response = requests.post(url, json=payload, timeout=6)
            data = response.json()

            if "result" in data:
                results.append({
                    "rpc_url": url,
                    "method": "getSlot",
                    "result": data.get("result"),
                    "status": "Success"
                })
            else:
                results.append({
                    "rpc_url": url,
                    "method": "getSlot",
                    "status": "Failed",
                    "error": data.get("error", "No result returned")
                })

        except requests.exceptions.RequestException as e:
            results.append({
                "rpc_url": url,
                "method": "getSlot",
                "status": "Failed",
                "error": str(e)
            })

    return jsonify(results)
            })

    return jsonify(results)
