from flask import Flask, jsonify
import requests
import json
import os

app = Flask(__name__)

# 🛠 Use portable path to ensure it always works, even on Render or GitHub
try:
    rpc_list_path = os.path.join(os.path.dirname(__file__), "rpcs", "rpc_list.json")
    with open(rpc_list_path, "r") as f:
        rpc_list = json.load(f)["rpcs"]  # 💡 make sure we access the actual list under "rpcs"
except Exception as e:
    rpc_list = []
    print("Failed to load rpc_list.json:", e)

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
            response = requests.post(url, json=payload, timeout=5)
            data = response.json()
            results.append({
                "rpc_url": url,
                "method": "getSlot",
                "result": data.get("result"),
                "status": "Success"
            })
        except Exception as e:
            results.append({
                "rpc_url": url,
                "method": "getSlot",
                "status": "Failed",
                "error": str(e)
            })
    return jsonify(results)
