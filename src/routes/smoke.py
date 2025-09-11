from flask import Blueprint, jsonify
import os, json, requests
from concurrent.futures import ThreadPoolExecutor, as_completed

smoke_bp = Blueprint("smoke_bp", __name__)

RPC_FILE = os.path.join(os.path.dirname(__file__), "..", "rpcs", "rpc_list.json")

def load_rpc_urls():
    try:
        with open(RPC_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, dict) and "rpcs" in data:
                return data["rpcs"]
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []

RPC_URLS = load_rpc_urls()

def probe_rpc(url, timeout=6):
    payload = {"jsonrpc":"2.0","id":1,"method":"getSlot","params":[]}
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        j = r.json()
        if "result" in j:
            return {"rpc_url": url, "status": "Success"}
        return {"rpc_url": url, "status": "Failed"}
    except Exception:
        return {"rpc_url": url, "status": "Failed"}

@smoke_bp.route("/smoke")
def smoke():
    max_workers = int(os.environ.get("RPC_MAX_WORKERS", "10"))
    results = []
    if RPC_URLS:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(probe_rpc, u): u for u in RPC_URLS}
            for fut in as_completed(futs):
                results.append(fut.result())
    ok = sum(1 for r in results if r["status"] == "Success")
    fail = sum(1 for r in results if r["status"] != "Success")
    sample = results[:3]

    return jsonify({
        "healthz": {"ok": True},
        "rpc_list_count": len(RPC_URLS),
        "rpc_status": {"ok": ok, "fail": fail, "sample": sample}
    })
