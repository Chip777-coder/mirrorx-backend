from flask import Flask, jsonify
import json, os, requests, time

app = Flask(__name__)

RPC_JSON_PATH = os.path.join("rpcs", "rpc_list.json")

@app.route("/")
def index():
    return jsonify(message="MirrorX Backend is Live. Use /rpc-list or /rpc-test")

@app.route("/rpc-list")
def get_rpc_list():
    try:
        with open(RPC_JSON_PATH, "r") as file:
            data = json.load(file)
        return jsonify(data)
    except Exception as e:
        return jsonify(error="RPC list fetch failed", details=str(e)), 500

@app.route("/rpc-test")
def test_rpcs():
    try:
        with open(RPC_JSON_PATH, "r") as file:
            rpc_data = json.load(file)
        rpcs = rpc_data.get("rpcs", [])
        results = []
        for rpc in rpcs:
            try:
                start = time.time()
                response = requests.post(rpc, json={"jsonrpc":"2.0","id":1,"method":"getHealth"})
                latency = round((time.time() - start)*1000, 2)
                results.append({"rpc": rpc, "status": response.json(), "latency_ms": latency})
            except Exception as rpc_error:
                results.append({"rpc": rpc, "status": "Failed", "error": str(rpc_error)})
        return jsonify(results=results)
    except Exception as e:
        return jsonify(error="RPC testing failed", details=str(e)), 500
