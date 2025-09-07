# MirrorX Backend (minimal drop-in)

This package contains a clean, minimal Flask backend that serves:
- `/` health text
- `/rpc-list` -> returns the array of RPC URLs
- `/rpc-status` -> calls `getSlot` on each RPC in parallel and returns results
- `/healthz` -> JSON health check

## Structure
```
app.py
rpcs/rpc_list.json
routes/                (package marker only)
logs/score_log.csv     (empty starter)
fallback/working_endpoints.json
Procfile
gunicorn.conf.py
requirements.txt
```

## Deploy (Render)
1. Push these files to your repo root.
2. Make sure your Render service uses **Build Command** (if any) to `pip install -r requirements.txt` or the default Python buildpack picks it up.
3. **Start Command:** `gunicorn app:app`
4. Expose port via the Render `$PORT` (the code respects it; defaults to 10000).

## Configure RPCs
Edit `rpcs/rpc_list.json`. Both of these are public/demo and worked during tests:
```json
{
  "rpcs": [
    "https://api.mainnet-beta.solana.com",
    "https://solana-mainnet.g.alchemy.com/v2/demo"
  ]
}
```
If your previous file had many entries, paste them in—this backend will still work; bad ones will just show `"status": "Failed"` in `/rpc-status`.

## Notes
- Concurrency is controlled by `RPC_MAX_WORKERS` env var (default 10).
- Keep the list small for faster `/rpc-status` responses; you can keep a longer list in the repo and a short "active" list for production.
