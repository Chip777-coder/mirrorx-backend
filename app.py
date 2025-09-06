from flask import Flask, jsonify
import requests
import json

app = Flask(__name__)

# Load RPC list
try:
    with open("rpcs/rpc_list.json", "r") as f:
        RPC_ENDPOINTS = json.load(f)
except Exception as e:
    print("Error loading rpc_list.json:", e)
    RPC_ENDPOINTS = []

@app.route("/")
def home():
    return "MirrorX backend is live ✅"

@app.route("/rpc-list")
def list_rpcs():
    return jsonify(RPC_ENDPOINTS)

@app.route('/rpc-status', methods=['GET'])
def rpc_status():
    status_list = []
    for rpc in RPC_ENDPOINTS:
        try:
            response = requests.post(
                rpc.split('?')[0],
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getHealth"
                },
                timeout=3
            )
            healthy = response.status_code == 200 and response.json().get('result') == 'ok'
            status_list.append({
                'rpc': rpc,
                'status': 'healthy' if healthy else 'unhealthy',
                'code': response.status_code
            })
        except Exception as e:
            status_list.append({
                'rpc': rpc,
                'status': 'error',
                'error': str(e)
            })
    return jsonify(status_list)

@app.route("/run-job")
def run_job():
    return jsonify({"job": "scoring", "status": "complete"})

@app.route("/score-history")
def score_history():
    try:
        with open("mock_data/score_history.csv", "r") as f:
            return jsonify(f.read().splitlines())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/live-score")
def live_score():
    try:
        with open("mock_data/live_score.csv", "r") as f:
            return jsonify(f.read().splitlines())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/scores")
def scores():
    try:
        with open("mock_data/scores.csv", "r") as f:
            return jsonify(f.read().splitlines())
    except Exception as e:
        return jsonify({"error": str(e)}), 500