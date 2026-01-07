# src/services/alpha_fusion.py
"""
MirrorX Hybrid Alpha Fusion Engine (Rocket-compatible)
------------------------------------------------------
Combines:
- DexScreener live pair metrics (via Rocket alpha_detector logic)
- MirrorX Fusion feed (market-intel)

Goal:
Find tokens that are BOTH:
- technically moving (volume/liquidity + price expansion) on DEX
- and have "fusion" context available (momentum/sentiment/summary fields)

Educational tooling only. Not trade advice.
"""

from __future__ import annotations
import os
import requests

from src.services.telegram_alerts import send_telegram_message

# ✅ Import from the *new* Rocket alpha detector module
from src.services.alpha_detector import (
    fetch_pairs_by_search,
    _best_pair_by_liquidity,
    analyze_pair,
    format_alert,
)

FUSION_API = os.getenv("FUSION_API_URL", "https://mirrorx-backend.onrender.com/api/fusion/market-intel")


def fetch_fusion_intel() -> list[dict]:
    """Fetch live fusion intelligence feed."""
    try:
        res = requests.get(FUSION_API, timeout=12)
        res.raise_for_status()
        data = res.json()
        if isinstance(data, dict):
            return data.get("data", []) or []
        if isinstance(data, list):
            return data
    except Exception as e:
        print(f"[AlphaFusion] Error fetching fusion intel: {e}")
    return []


def _fusion_map_by_symbol(fusion_data: list[dict]) -> dict[str, dict]:
    """
    Your fusion endpoint returns a list of items with at least "symbol".
    We map by SYMBOL so the fusion layer can enrich DEX candidates.
    """
    out: dict[str, dict] = {}
    for t in fusion_data or []:
        sym = (t.get("symbol") or "").upper()
        if sym:
            out[sym] = t
    return out


def detect_fused_alpha(symbols: list[str] | None = None) -> list[dict]:
    """
    For each symbol:
      1) Dex search
      2) Pick best pair by liquidity
      3) Apply Rocket/Moonshot analyze_pair gates
      4) If symbol exists in Fusion feed, enrich + rank
    """
    print("[AlphaFusion] Running hybrid detector...")

    fusion_data = fetch_fusion_intel()
    if not fusion_data:
        print("[AlphaFusion] Fusion feed unavailable; returning empty (or use Dex-only detector elsewhere).")
        return []

    f_map = _fusion_map_by_symbol(fusion_data)

    # Default universe (tune)
    symbols = symbols or ["SOL", "BONK", "WIF", "JUP", "PYTH", "JTO", "MPLX", "WEN"]

    all_tokens: list[dict] = []

    for sym in symbols:
        # Dex search for symbol/pairs
        pairs = fetch_pairs_by_search(sym)
        if not pairs:
            continue

        best = _best_pair_by_liquidity(pairs)
        if not best:
            continue

        token = analyze_pair(best)
        if not token:
            continue

        s = (token.get("symbol") or "").upper()
        fusion = f_map.get(s)
        if not fusion:
            continue

        # Enrich token with whatever fusion fields exist
        # (Your fusion feed keys may vary; this is defensive.)
        token["fusion"] = {
            "summary": fusion.get("summary") or fusion.get("narrative") or "",
            "momentum": fusion.get("momentum", 0),
            "sentiment": fusion.get("sentiment", 0),
            "ccChange24h": fusion.get("ccChange24h", 0),
            "cmcVolume": fusion.get("cmcVolume", 0),
        }

        # Combined score (educational): short-term move + fusion sentiment/momentum
        token["fusion_score"] = (
            float(token.get("change_m5", 0) or 0) * 0.8 +
            float(token.get("change_1h", 0) or 0) * 0.6 +
            float(token.get("volume_1h", 0) or 0) / 300_000.0 +
            float(token.get("liquidity", 0) or 0) / 200_000.0 +
            float(token["fusion"].get("momentum", 0) or 0) +
            float(token["fusion"].get("sentiment", 0) or 0)
        )

        all_tokens.append(token)

    if not all_tokens:
        print("[AlphaFusion] No fused alpha signals detected.")
        return []

    ranked = sorted(all_tokens, key=lambda x: float(x.get("fusion_score", 0) or 0), reverse=True)
    return ranked[:5]


def push_fused_alpha_alerts():
    """Push hybrid alpha alerts to Telegram."""
    tokens = detect_fused_alpha()
    if not tokens:
        print("[AlphaFusion] No standout fusion signals.")
        return

    for token in tokens:
        msg = format_alert(token)

        # If we have fusion context, append it
        fusion = token.get("fusion") or {}
        if fusion.get("summary"):
            msg += f"\n\n🧠 <b>Fusion Insight</b>: {fusion.get('summary')}\n"

        send_telegram_message(msg)
        print(f"[AlphaFusion] Sent fused alert for {token.get('symbol')} ({token.get('address')})")


if __name__ == "__main__":
    push_fused_alpha_alerts()
