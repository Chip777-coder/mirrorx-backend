
from flask import Flask, jsonify
import json
import os

app = Flask(__name__)

@app.route("/")
def home():
    return "MirrorX Backend is Live"

@app.route('/rpc-list', methods=['GET'])
def rpc_list():
    try:
        with open('rpc_list.json', 'r') as f:  # ← no subfolder
            data = json.load(f)
        return jsonify({'rpcs': data})
    except FileNotFoundError as e:
        return jsonify({'error': 'RPC list fetch failed', 'details': str(e)}), 500
if __name__ == "__main__":
    app.run()
