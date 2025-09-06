
from flask import Flask, jsonify
import json
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "MirrorX Backend is Live"

@app.route("/rpc-list", methods=["GET"])
def rpc_list():
    try:
        json_path = os.path.join(os.path.dirname(__file__), 'rpcs', 'rpc_list.json')
        with open(json_path, 'r') as f:
            data = json.load(f)
        return jsonify({'rpcs': data})
    except Exception as e:
        return jsonify({'error': 'RPC list fetch failed', 'details': str(e)}), 500

if __name__ == "__main__":
    app.run()
