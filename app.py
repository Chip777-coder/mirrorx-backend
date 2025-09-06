from flask import Flask, jsonify
import json
import os
import requests
import time

app = Flask(__name__)

@app.route("/")
def home():
    return "MirrorX Backend is Live"

@app.route('/rpc-list', methods=['GET'])
def rpc_list():
    try:
        with open('rpc_list.json', 'r') as f:
            data = json.load(f)
        return jsonify({'rpcs': data})
    except FileNotFoundError as e:
        return jsonify({'error': 'RPC list fetch failed', 'details': str(e)}), 500

@app.route('/test-rpcs', methods=['GET'])
def test_rpcs():
    try:
        with open('rpc_list.json', 'r') as f:
            rpc_urls = json.load(f)
    except FileNotFoundError as e:
        return jsonify({'error': 'RPC list fetch failed', 'details': str(e)}), 500

    results = []
    for url in rpc_urls:
        start = time.time()
        try:
            # Use a simple JSON-RPC method like getHealth
            response = requests.post(url, json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getHealth"
            }, timeout=3)
            latency = round((time.time() - start) * 1000, 2)
            results.append({
                'rpc': url,
                'status': 'ok' if response.status_code == 200 else 'fail',
                'response': response.json(),
                'latency_ms': latency
            })
        except Exception as e:
            latency = round((time.time() - start) * 1000, 2)
            results.append({
                'rpc': url,
                'status': 'error',
                'error': str(e),
                'latency_ms': latency
            })

    return jsonify({'results': results})

if __name__ == "__main__":
    app.run()