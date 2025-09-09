# src/routes/rpc_status.py
from flask import Blueprint, jsonify, request
import os, json, requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..config import QUICKNODE_HTTP, USE_ONLY_QUICKNODE, RPC_TIMEOUT_SECS, RPC_MAX_WORKERS

rpc_status_bp = Blueprint("rpc_status_bp", __name__)

# Load fallback RPCs, but we'll prefer QuickNode.
RPC_FILE = os.path.join(os.path.dirname(__file__), "..", "rpcs", "rpc_list.json")
def load_rpc_urls():
    try:
        with open(RPC_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, dict) and "rpcs" in data:
                return data["rpcs"]
            if isinstance(data, list):
                return data
    except Exception as e:
        print(f"[rpc_status] failed loading rpc_list.json: {e}")
    return []

FALLBACK_RPCS = load_rpc_urls()

def unique(seq):
    seen = set()
    out = []
    for s in seq:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out

def probe(url, timeout=RPC_TIMEOUT_SECS):
    # We’ll use getSlot for a fast, cheap liveness check.
    payload = {"jsonrpc":"2.0","id":1,"method":"getSlot","params":[]}
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        # handle non-json noise cleanly
        try:
            data = resp.json()
        except Exception:
            return {"rpc_url": url, "status":"Failed", "error":"Non-JSON response"}
        if "result" in data:
            return {"rpc_url": url, "status":"Success", "result": data["result"]}
        return {"rpc_url": url, "status":"Failed", "error": data.get("error","No result")}
    except requests.exceptions.RequestException as e:
        return {"rpc_url": url, "status":"Failed", "error": str(e)}

@rpc_status_bp.route("/rpc-status")
def rpc_status():
    """
    Behavior:
      - If USE_ONLY_QUICKNODE=1 and QUICKNODE_HTTP is set → only check that.
      - Else → QuickNode first, then a trimmed list of public RPCs.
    Query params:
      - limit: max number of RPCs to check (default 12)
      - batch: if '1', trim to distinct providers (avoid spamming same host with many fallback=N variants)
    """
    limit = max(1, int(request.args.get("limit", "12")))
    batch_mode = request.args.get("batch", "1") == "1"

    urls = []
    if QUICKNODE_HTTP and QUICKNODE_HTTP.startswith("http"):
        urls.append(QUICKNODE_HTTP)

    if not (USE_ONLY_QUICKNODE and urls):
        # include fallbacks but filter out ones that usually error without keys
        noisy_hosts = (
            "helius-rpc.com",
            "rpcpool.com",
            "shyft.to",
            "hellomoon.io",
            "chainstack.com",
            "mintgarden.io",
        )
        filtered = [u for u in FALLBACK_RPCS if all(h not in u for h in noisy_hosts)]
        urls.extend(filtered)

    # De-dup and optionally collapse to distinct providers (hostnames)
    urls = unique(urls)
    if batch_mode and len(urls) > 1:
        # keep at most one per host
        by_host = {}
        for u in urls:
            try:
                host = u.split("//",1)[1].split("/",1)[0]
            except Exception:
                host = u
            if host not in by_host:
                by_host[host] = u
        urls = list(by_host.values())

    # apply limit (QuickNode stays first)
    urls = urls[:limit]

    results = []
    with ThreadPoolExecutor(max_workers=RPC_MAX_WORKERS) as ex:
        futs = {ex.submit(probe, u): u for u in urls}
        for fut in as_completed(futs):
            results.append(fut.result())
    return jsonify(results)
