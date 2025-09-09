# src/config.py
import os

QUICKNODE_HTTP = os.getenv("QUICKNODE_HTTP", "").rstrip("/") + "/"
QUICKNODE_WS   = os.getenv("QUICKNODE_WS", "").rstrip("/") + "/"

# If true, rpc-status uses ONLY QuickNode. If false, it will also include rpcs/rpc_list.json.
USE_ONLY_QUICKNODE = os.getenv("USE_ONLY_QUICKNODE", "1") == "1"

# Basic concurrency limits for /rpc-status
RPC_TIMEOUT_SECS = int(os.getenv("RPC_TIMEOUT_SECS", "6"))
RPC_MAX_WORKERS  = int(os.getenv("RPC_MAX_WORKERS", "10"))
