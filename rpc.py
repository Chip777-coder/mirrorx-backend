import os, json, time, requests
from requests.adapters import HTTPAdapter, Retry

RPC_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "rpcs", "rpc_list.json"))

def load_rpc_urls():
    try:
        with open(RPC_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, dict) and "rpcs" in data:
                return data["rpcs"]
            if isinstance(data, list):
                return data
    except Exception as e:
        print(f"[rpc] Error loading RPC list: {e}")
    return []

def get_session():
    s = requests.Session()
    retries = Retry(total=2, backoff_factor=0.2, status_forcelist=(429,500,502,503,504), allowed_methods=frozenset(["POST","GET"]))
    adapter = HTTPAdapter(max_retries=retries, pool_connections=100, pool_maxsize=100)
    s.mount("http://", adapter); s.mount("https://", adapter)
    return s

def check_rpc_once(session, url, timeout=6.0):
    payload = {"jsonrpc": "2.0", "id": 1, "method": "getSlot", "params": []}
    t0 = time.perf_counter()
    try:
        resp = session.post(url, json=payload, timeout=timeout)
    except requests.exceptions.RequestException as e:
        return {"rpc_url": url, "status": "Failed", "error": str(e)}
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    try:
        data = resp.json()
    except Exception:
        return {"rpc_url": url, "status": "Failed", "error": "Non-JSON response", "latency_ms": latency_ms}
    if "result" in data:
        return {"rpc_url": url, "status": "Success", "result": data["result"], "latency_ms": latency_ms}
    return {"rpc_url": url, "status": "Failed", "error": data.get("error", "No result returned"), "latency_ms": latency_ms}
