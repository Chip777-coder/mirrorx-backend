
# app_loader.py
import sys, os
from importlib import import_module

# Ensure both possible paths are importable
base_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(base_dir, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

try:
    # Try when app is in /src/app.py
    app_module = import_module("src.app")
except ModuleNotFoundError:
    # Fallback when app.py is at root
    app_module = import_module("app")

app = app_module.app
