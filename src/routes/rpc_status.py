# src/routes/rpc_status.py
from flask import Blueprint, jsonify
import requests, json, os, concurrent.futures

rpc_status_bp = Blueprint("rpc_status_bp", __name__)

# Build RPC list dynamically: prefer key-based RPCs if env is set, else keep your JSON
RPC_FILE = os.path.join(os.path.dirname(__file__), "..", "rpcs", "rpc_list.json")
def load_rpc_urls():
    urls = []
    # Keyed providers (optional)
    if os.getenv("HELIUS_RPC_URL"):   urls.append(os.getenv("HELIUS_RPC_URL"))
    if os.getenv("ALCHEMY_RPC_URL"):  urls.append(os.getenv("ALCHEMY_RPC_URL"))
    if os.getenv("RPCPOOL_RPC_URL"):  urls.append(os.getenv("RPCPOOL_RPC_URL"))
    # Always include public Solana endpoint
    urls.append("https://api.mainnet-beta.solana.com")
    # Add your legacy list (won’t duplicate)
    try:
        with open(RPC_FILE, "r") as f:
            data = json.load(f)
            extra = data["rpcs"] if isinstance(data, dict) else data
            for u in extra:
                base = u.split("?")[0]
                if base not in [x.split("?")[0] for x in urls]:
                    urls.append(u)
    except Exception:
        pass
    return urls

RPC_URLS = load_rpc_urls()

def rpc_batch(url, timeout=6):
    # 3 calls in one HTTP round trip
    batch = [
        {"jsonrpc":"2.0","id":"health","method":"getHealth","params":[]},
        {"jsonrpc":"2.0","id":"ver","method":"getVersion","params":[]},
        {"jsonrpc":"2.0","id":"slot","method":"getSlot","params":[]}
    ]
    try:
        r = requests.post(url, json=batch, timeout=timeout)
        out = r.json()  # list of responses
        res = {item.get("id"): item.get("result") for item in out if isinstance(out, list)}
        err = next((item.get("error") for item in out if isinstance(out, list) and "error" in item), None)
        summary = {
            "rpc_url": url,
            "status": "Success" if res else "Failed",
            "health": res.get("health"),
            "version": (res.get("ver") or {}).get("solana-core") if isinstance(res.get("ver"), dict) else res.get("ver"),
            "slot": res.get("slot"),
        }
        if err:
            summary["status"] = "Failed"
            summary["error"] = err
        return summary
    except Exception as e:
        return {"rpc_url": url, "status":"Failed", "error": str(e)}

@rpc_status_bp.route("/rpc-status", methods=["GET"])
def status_simple():
    # Keep your original single-call checker (getSlot) for compatibility
    def check(url):
        try:
            r = requests.post(url, json={"jsonrpc":"2.0","id":1,"method":"getSlot","params":[]}, timeout=6)
            j = r.json()
            if "result" in j: return {"rpc_url": url, "status":"Success", "slot": j["result"]}
            return {"rpc_url": url, "status":"Failed", "error": j.get("error","No result")}
        except Exception as e:
            return {"rpc_url": url, "status":"Failed", "error": str(e)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(os.getenv("RPC_MAX_WORKERS","10"))) as ex:
        return jsonify(list(ex.map(check, RPC_URLS)))

@rpc_status_bp.route("/rpc-status/batch", methods=["GET"])
def status_batch():
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(os.getenv("RPC_MAX_WORKERS","10"))) as ex:
        return jsonify(list(ex.map(rpc_batch, RPC_URLS)))
