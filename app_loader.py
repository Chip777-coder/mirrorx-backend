
# app_loader.py
import sys
from importlib import import_module

try:
    # Try normal import (Render's typical /src/src structure)
    app_module = import_module("src.app")
except ModuleNotFoundError:
    # Fallback if already running inside /src
    app_module = import_module("app")

app = app_module.app
