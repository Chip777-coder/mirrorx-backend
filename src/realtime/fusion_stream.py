# src/realtime/fusion_stream.py
from flask_socketio import SocketIO, emit
import threading, time, random, json

# Initialize SocketIO (no async mode conflicts)
socketio = SocketIO(cors_allowed_origins="*")

# --- Demo Data Streamer ---
def start_fusion_stream():
    """Background thread that emits simulated fusion updates every few seconds."""
    def run():
        while True:
            try:
                # Replace this block later with live fusion aggregation logic
                payload = {
                    "symbol": random.choice(["SOL", "BONK", "WIF", "JUP", "DOGWIFHAT"]),
                    "mirroraXScore": round(random.uniform(50, 99), 2),
                    "volume": round(random.uniform(1_000_000, 50_000_000), 2),
                    "socialVelocity": round(random.uniform(0.1, 5.0), 2),
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
                socketio.emit("fusion_update", payload, broadcast=True)
                time.sleep(5)
            except Exception as e:
                print(f"[WARN] Fusion stream error: {e}")
                time.sleep(10)
    thread = threading.Thread(target=run, daemon=True)
    thread.start()

# --- Socket Events ---
@socketio.on("connect")
def handle_connect():
    emit("fusion_status", {"status": "connected", "message": "🔗 Fusion stream active."})
    print("[SocketIO] Client connected")

@socketio.on("disconnect")
def handle_disconnect():
    print("[SocketIO] Client disconnected")
