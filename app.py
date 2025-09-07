from flask import Flask, jsonify
import json
import os

# Import the Blueprint from routes
from routes.rpc_status import rpc_status_bp

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

# Register the /rpc-status route from the Blueprint
app.register_blueprint(rpc_status_bp)

if __name__ == "__main__":
    app.run(debug=True)
