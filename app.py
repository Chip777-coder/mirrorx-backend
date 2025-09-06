from flask import Flask, jsonify
import requests
import json

app = Flask(__name__)

# Load the real RPCs from the correct folder path
try:
    with open("rpcs/rpc_list.json", "r") as f:
        rpc_list = json.load(f)
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
