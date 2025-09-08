# MIRROR-BACKEND

Drop-in Flask backend for Render.

## Quick start (Render)
1. Create a new Web Service and point it at this repo.
2. Build Command: `pip install -r requirements.txt`
3. (Optional) Add env vars:
   - `ENABLE_ALERT_INGEST=1`
   - `ENABLE_AGENTS=1`
   - `RPC_MAX_WORKERS=10`
4. Health Check Path: `/healthz`
5. It will serve:
   - `/` → liveness text
   - `/healthz` → `{ "ok": true }`
   - `/rpc-list` → raw RPC list
   - `/rpc-status` → probe multiple Solana RPCs (parallel)
   - `/alerts/ping`, `/agents/ping` → stubs you can replace later

## Local
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PORT=10000
python -m src.app
```
