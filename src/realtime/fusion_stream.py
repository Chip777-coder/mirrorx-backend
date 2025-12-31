# src/realtime/fusion_stream.py
from flask_socketio import SocketIO, emit
import threading, time, requests, os
from functools import lru_cache
from src.alerts.fusion_broadcast import broadcast_fusion

socketio = SocketIO(cors_allowed_origins="*")

API_URL = os.getenv("FUSION_API_URL", "https://mirrorx-backend.onrender.com/api/fusion/market-intel")

def fetch_live_fusion():
    """Fetch live MirroraX fusion market data (top 5)."""
    try:
        r = requests.get(API_URL, timeout=10)
        if r.status_code == 200:
            data = r.json().get("data", [])
            top = sorted(data, key=lambda x: x.get("cmcVolume", 0), reverse=True)[:5]
            return top
    except Exception as e:
        print(f"[WARN] Fusion API fetch failed: {e}")
    return []

@lru_cache(maxsize=1)
def cached_fetch_live_fusion():
    """Cache fusion data for ~55 s to limit API calls."""
    return fetch_live_fusion()

def start_fusion_stream():
    """Emit cached or live data every 60 s and push alerts."""
    def run():
        while True:
            try:
                payload = cached_fetch_live_fusion()
                if not payload:
                    socketio.emit("fusion_update", {"status": "idle", "message": "No live data available."})
                else:
                    socketio.emit("fusion_update", payload)
                    broadcast_fusion(payload[:3])   # send top 3 to Telegram/Discord
                cached_fetch_live_fusion.cache_clear()
                time.sleep(60)
            except Exception as e:
                print(f"[WARN] Fusion stream loop error: {e}")
                time.sleep(120)
    threading.Thread(target=run, daemon=True).start()

@socketio.on("connect")
def handle_connect():
    emit("fusion_status", {"status": "connected", "message": "🔗 Live MirroraX feed active."})
    print("[SocketIO] Client connected")

@socketio.on("disconnect")
def handle_disconnect():
    print("[SocketIO] Client disconnected")
