# MirrorX RPC-Ready Flask Backend (Ultimate)

This is a production-grade Flask backend that:
- Cycles through 15+ Solana RPCs with automatic fallback
- Measures latency and uptime to pick the best performing RPC
- Provides endpoints for real-time RPC status and fallback logic

## Endpoints
- `/rpc-status`: Check the health and latency of all available RPCs
- `/get-best-rpc`: Get the best (alive + fastest) RPC URL

## Running Locally
```bash
pip install -r requirements.txt
python app.py
```

## Deployment Ready
Use with Render, Replit, or connect to your GPT/Telegram/Discord frontends.