# app_loader.py
import sys, os
from importlib import import_module

# Ensure src/ is in path
base_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(base_dir, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Import Flask app first
try:
    app_module = import_module("src.app")
except ModuleNotFoundError:
    app_module = import_module("app")

app = app_module.app  # Flask instance

# Import and initialize SocketIO AFTER app exists
try:
    from src.realtime.fusion_stream import socketio, start_fusion_stream
    socketio.init_app(app)
    start_fusion_stream()
    print("✅ MirroraX Fusion Stream activated.")
except Exception as e:
    print(f"⚠️ SocketIO initialization skipped or failed: {e}")
