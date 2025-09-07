from flask import Blueprint, jsonify, request
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.rpc import load_rpc_urls, get_session, check_rpc_once
from config import RPC_TIMEOUT_SEC, RPC_MAX_WORKERS, RPC_TOP_N

rpc_status_bp = Blueprint("rpc_status_bp", __name__)
SESSION = get_session()

@rpc_status_bp.route("/rpc-list")
def rpc_list():
    return jsonify(load_rpc_urls())

@rpc_status_bp.route("/rpc-status")
def rpc_status():
    urls = load_rpc_urls()
    results = []
    with ThreadPoolExecutor(max_workers=RPC_MAX_WORKERS) as pool:
        futures = {pool.submit(check_rpc_once, SESSION, url, RPC_TIMEOUT_SEC): url for url in urls}
        for fut in as_completed(futures):
            results.append(fut.result())
    return jsonify(results)

@rpc_status_bp.route("/rpc-fast")
def rpc_fast():
    n = int(request.args.get("n", RPC_TOP_N))
    urls = load_rpc_urls()
    results = []
    with ThreadPoolExecutor(max_workers=RPC_MAX_WORKERS) as pool:
        futures = {pool.submit(check_rpc_once, SESSION, url, RPC_TIMEOUT_SEC): url for url in urls}
        for fut in as_completed(futures):
            results.append(fut.result())
    ok = [r for r in results if r.get("status") == "Success"]
    ok.sort(key=lambda x: (x.get("latency_ms", 9e9)))
    return jsonify(ok[:n])

@rpc_status_bp.route("/rpc-probe")
def rpc_probe():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "missing ?url="}), 400
    res = check_rpc_once(SESSION, url, RPC_TIMEOUT_SEC)
    return jsonify(res)
