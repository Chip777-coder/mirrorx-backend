
# app_loader.py (v3 - Final Fix)
import sys, os
from importlib import import_module

# Ensure both possible paths are importable
base_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(base_dir, "src")

# If 'src/routes' doesn’t exist but 'routes' does, link it
possible_routes = os.path.join(base_dir, "routes")
if not os.path.exists(os.path.join(src_path, "routes")) and os.path.exists(possible_routes):
    os.makedirs(src_path, exist_ok=True)
    os.symlink(possible_routes, os.path.join(src_path, "routes"))

if src_path not in sys.path:
    sys.path.insert(0, src_path)

try:
    # Preferred (when deployed inside /src/src/)
    app_module = import_module("src.app")
except ModuleNotFoundError:
    # Fallback (when app.py is in root)
    app_module = import_module("app")

app = app_module.app
