# src/realtime/fusion_stream.py
from flask_socketio import SocketIO, emit
import threading, time, requests, os, json

socketio = SocketIO(cors_allowed_origins="*")

API_URL = os.getenv("FUSION_API_URL", "https://mirrorx-backend.onrender.com/api/fusion/market-intel")

def fetch_live_fusion():
    """Fetch live MirroraX fusion market data (top 5)."""
    try:
        r = requests.get(API_URL, timeout=10)
        if r.status_code == 200:
            data = r.json().get("data", [])
            # Pick top 5 by cmcVolume
            top = sorted(data, key=lambda x: x.get("cmcVolume", 0), reverse=True)[:5]
            return top
    except Exception as e:
        print(f"[WARN] Fusion API fetch failed: {e}")
    return []

def start_fusion_stream():
    """Emit live data periodically, fallback to heartbeat if API fails."""
    def run():
        while True:
            try:
                payload = fetch_live_fusion()
                if not payload:
                    emit_data = {"status": "idle", "message": "No live data available."}
                    socketio.emit("fusion_update", emit_data)
                else:
                    socketio.emit("fusion_update", payload)
                # keep calls modest (1/minute)
                time.sleep(60)
            except Exception as e:
                print(f"[WARN] Fusion stream loop error: {e}")
                time.sleep(120)
    thread = threading.Thread(target=run, daemon=True)
    thread.start()

@socketio.on("connect")
def handle_connect():
    emit("fusion_status", {"status": "connected", "message": "🔗 Live MirroraX feed active."})
    print("[SocketIO] Client connected")

@socketio.on("disconnect")
def handle_disconnect():
    print("[SocketIO] Client disconnected")
