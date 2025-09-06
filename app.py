from flask import Flask, jsonify
import requests
import json
import os

# Import only the function to register the route (not redefine it)
from routes.rpc_status import real_rpc_status

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

# DO NOT redefine real_rpc_status here.
# It's already defined in routes/rpc_status.py and registered via app.route

# ✅ Removed:
# - Duplicate `/rpc-status` route
# - Line: `response = requests.post(url, json=payload, timeout=2)`
