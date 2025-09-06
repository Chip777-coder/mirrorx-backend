from flask import Flask, jsonify
import requests
import random
import time

app = Flask(__name__)

# Preloaded list of diverse and globally distributed public Solana RPCs (examples, more can be added)
RPC_LIST = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-api.projectserum.com",
    "https://solana-mainnet.g.alchemy.com/v2/demo",
    "https://rpc.ankr.com/solana",
    "https://rpc.helius.xyz",
    "https://solana.public-rpc.com",
    "https://api.metaplex.solana.com",
    "https://rpc.shyft.to",
    "https://rpc.liftbridge.app",
    "https://rpc.triton.one",
    "https://solana-api.syndica.io/access-token/demo",
    "https://rpc-mainnet-fork.epochs.dev",
    "https://rpc1.mainnet.solana.allthatnode.com",
    "https://rpc2.mainnet.solana.allthatnode.com",
    "https://mainnet.rpcpool.com"
]

def is_rpc_alive(rpc_url):
    try:
        start = time.time()
        response = requests.post(rpc_url, json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getHealth"
        }, timeout=3)
        latency = round((time.time() - start) * 1000, 2)
        if response.status_code == 200 and response.json().get("result") == "ok":
            return True, latency
    except Exception:
        pass
    return False, None

def get_best_rpc():
    healthy_rpcs = []
    for rpc in RPC_LIST:
        healthy, latency = is_rpc_alive(rpc)
        if healthy:
            healthy_rpcs.append((rpc, latency))
    healthy_rpcs.sort(key=lambda x: x[1])  # sort by latency
    return healthy_rpcs[0][0] if healthy_rpcs else None

@app.route('/rpc-status')
def rpc_status():
    working_rpcs = []
    for rpc in RPC_LIST:
        alive, latency = is_rpc_alive(rpc)
        working_rpcs.append({
            "rpc": rpc,
            "alive": alive,
            "latency_ms": latency if latency else "N/A"
        })
    return jsonify({"rpc_status": working_rpcs})

@app.route('/get-best-rpc')
def best_rpc():
    best = get_best_rpc()
    if best:
        return jsonify({"best_rpc": best})
    return jsonify({"error": "No RPCs available"}), 503

if __name__ == '__main__':
    app.run(debug=True)
    @app.route("/")
def home():
    return "MirrorX Backend is Live!"@app.route("/status")
def status():
    return {"status": "ok", "message": "MirrorX backend running"}
