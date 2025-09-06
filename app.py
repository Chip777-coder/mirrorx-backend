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
        filepath = os.path.join('rpcs', 'rpc_list.json')  # ✅ correct subfolder path
        with open(filepath, 'r') as f:
            data = json.load(f)
        return jsonify({'rpcs': data})
    except FileNotFoundError as e:
        return jsonify({'error': 'RPC list fetch failed', 'details': str(e)}), 500

if __name__ == "__main__":
    app.run()
