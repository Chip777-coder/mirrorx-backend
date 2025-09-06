from concurrent.futures import ThreadPoolExecutor, as_completed

@app.route("/rpc-status")
def real_rpc_status():
    def check_rpc(url):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSlot",
            "params": []
        }
        try:
            response = requests.post(url, json=payload, timeout=5)
            data = response.json()
            if "result" in data:
                return {
                    "rpc_url": url,
                    "method": "getSlot",
                    "result": data.get("result"),
                    "status": "Success"
                }
            else:
                return {
                    "rpc_url": url,
                    "method": "getSlot",
                    "status": "Failed",
                    "error": data.get("error", "No result returned")
                }
        except Exception as e:
            return {
                "rpc_url": url,
                "method": "getSlot",
                "status": "Failed",
                "error": str(e)
            }

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(check_rpc, url): url for url in rpc_list}
        for future in as_completed(future_to_url):
            results.append(future.result())

    return jsonify(results)
