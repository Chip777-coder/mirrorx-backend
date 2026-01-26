# src/services/wallet_intel.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests


# ============================================================
# Smart Wallet / Whale Intel (Helius RPC optional)
# ============================================================
# This does NOT execute trades.
# It provides whale context if HELIUS_API_KEY is set.
#
# Uses Solana JSON-RPC method: getTokenLargestAccounts
# ============================================================

HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "").strip()
HELIUS_RPC_URL = os.getenv(
    "HELIUS_RPC_URL",
    f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}" if HELIUS_API_KEY else ""
).strip()

RPC_TIMEOUT = int(os.getenv("HELIUS_TIMEOUT", "12"))


def _rpc_call(method: str, params: list) -> Optional[dict]:
    if not HELIUS_RPC_URL:
        return None

    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        r = requests.post(HELIUS_RPC_URL, json=payload, timeout=RPC_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def get_top_holders(mint: str, top_n: int = 10) -> Dict[str, Any]:
    """
    Returns whale distribution snapshot.
    If Helius key isn't set, returns empty intel (safe).
    """
    if not mint:
        return {"ok": False, "reason": "missing_mint", "holders": []}

    data = _rpc_call("getTokenLargestAccounts", [mint])
    if not data or "result" not in data:
        return {"ok": False, "reason": "helius_unavailable", "holders": []}

    value = (((data.get("result") or {}).get("value")) or [])
    holders = []

    for h in value[:top_n]:
        holders.append({
            "address": h.get("address"),
            "amount": h.get("amount"),
            "uiAmount": h.get("uiAmount"),
            "decimals": h.get("decimals"),
        })

    return {"ok": True, "holders": holders}


def whale_score_from_holders(holder_blob: Dict[str, Any]) -> int:
    """
    Heuristic whale score 0-100 based on concentration.
    """
    if not holder_blob.get("ok"):
        return 0

    holders = holder_blob.get("holders") or []
    if not holders:
        return 0

    # crude concentration heuristic:
    # if top holder is massive vs others -> higher risk / whale dominance
    ui_vals = []
    for h in holders:
        try:
            ui_vals.append(float(h.get("uiAmount") or 0))
        except Exception:
            ui_vals.append(0)

    total_top = sum(ui_vals)
    if total_top <= 0:
        return 0

    top1 = ui_vals[0] if ui_vals else 0
    dominance = top1 / total_top if total_top > 0 else 0

    # dominance higher = whale controls more = higher whale score
    score = int(min(100, max(0, dominance * 140)))
    return score
