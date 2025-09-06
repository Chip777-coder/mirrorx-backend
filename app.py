from flask import Flask, jsonify, request
import os
import json

app = Flask(__name__)

@app.route("/")
def home():
    return "MirrorX Backend is Live!"

@app.route("/status")
def status():
    return {"status": "ok", "message": "MirrorX backend running"}

@app.route("/rpc-list")
def rpc_list():
    try:
        with open("rpcs/rpc_list.json") as f:
            rpcs = json.load(f)
        return jsonify(rpcs)
    except Exception as e:
        return jsonify({"error": "RPC list fetch failed", "details": str(e)}), 500

@app.route("/fallback")
def fallback():
    return jsonify({"message": "Fallback route activated", "data": []})