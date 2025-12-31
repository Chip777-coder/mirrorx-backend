# app_loader.py – FIXED ORDERED VERSION
import sys, os
from importlib import import_module

# Ensure src/ folder is in the path
base_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(base_dir, "src")

if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Import Flask app first
try:
    # Preferred structure: /src/app.py
    app_module = import_module("src.app")
except ModuleNotFoundError:
    # Fallback if app.py is at project root
    app_module = import_module("app")

app = app_module.app  # ✅ Flask instance now exists

# Now safely initialize socketio AFTER app exists
try:
    from src.realtime.fusion_stream import socketio
    socketio.init_app(app)
except Exception as e:
    print(f"⚠️ SocketIO init skipped or failed: {e}")
