from flask import Flask, jsonify
import json
import requests
import time
import os

app = Flask(__name__)

@app.route("/rpc-test", methods=["GET"])
def rpc_test():
    try:
        with open(os.path.join("rpcs", "rpc_list.json"), "r") as f:
            rpc_data = json.load(f)
            rpc_urls = rpc_data.get("rpcs", [])
    except Exception as e:
        return jsonify({"error": "Failed to load rpc_list.json", "details": str(e)}), 500

    results = []
    for url in rpc_urls:
        start = time.time()
        try:
            response = requests.post(url, json={"jsonrpc":"2.0","id":1,"method":"getHealth"})
            duration = int((time.time() - start) * 1000)
            results.append({
                "url": url,
                "status": response.status_code,
                "response_time_ms": duration,
                "ok": response.ok,
                "error": None if response.ok else response.text
            })
        except Exception as e:
            duration = int((time.time() - start) * 1000)
            results.append({
                "url": url,
                "status": "failed",
                "response_time_ms": duration,
                "ok": False,
                "error": str(e)
            })

    return jsonify({"results": results})

if __name__ == "__main__":
    app.run(debug=True)
