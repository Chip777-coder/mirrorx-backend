# src/services/alpha_fusion.py
"""
MirrorX Hybrid Alpha Fusion Engine
---------------------------------------
Combines live DexScreener metrics with MirrorX Fusion
market-intel feed to identify tokens showing both
technical and sentiment-based anomalies.
"""

import requests
from src.services.alpha_detector import analyze_pairs, fetch_token_data, format_alert
from src.services.telegram_alerts import send_telegram_message

DEX_API = "https://api.dexscreener.com/latest/dex/tokens/"
FUSION_API = "https://mirrorx-backend.onrender.com/api/fusion/market-intel"

def fetch_fusion_intel():
    """Fetch live fusion intelligence feed."""
    try:
        res = requests.get(FUSION_API, timeout=10)
        res.raise_for_status()
        data = res.json()
        return data.get("data", []) if isinstance(data, dict) else data
    except Exception as e:
        print(f"[AlphaFusion] Error fetching fusion intel: {e}")
        return []

def detect_fused_alpha(symbols=None):
    """Cross-analyze Dex data and Fusion intel."""
    print("[AlphaFusion] Running hybrid detector...")

    fusion_data = fetch_fusion_intel()
    if not fusion_data:
        print("[AlphaFusion] Fusion feed unavailable, falling back to Dex-only.")
        from src.services.alpha_detector import detect_alpha_tokens
        return detect_alpha_tokens()

    # Build fusion sentiment map
    sentiment_map = {t["symbol"].upper(): t for t in fusion_data if "symbol" in t}

    all_tokens = []
    symbols = symbols or ["SOL", "BONK", "WIF", "JUP", "PYTH", "JTO", "MPLX"]

    for sym in symbols:
        dex_pairs = fetch_token_data(sym)
        dex_candidates = analyze_pairs(dex_pairs)
        for token in dex_candidates:
            s = token["symbol"].upper()
            fusion = sentiment_map.get(s)
            if fusion:
                # Merge both layers of intelligence
                token["fusion_score"] = fusion.get("momentum", 0) + fusion.get("sentiment", 0)
                token["fusion_summary"] = fusion.get("summary", "")
                all_tokens.append(token)

    if not all_tokens:
        print("[AlphaFusion] No fused alpha signals detected.")
        return []

    # Rank by combined 1h change + fusion score
    ranked = sorted(all_tokens, key=lambda x: x["change_1h"] + x.get("fusion_score", 0), reverse=True)
    return ranked[:5]

def push_fused_alpha_alerts():
    """Push hybrid alpha alerts."""
    tokens = detect_fused_alpha()
    if not tokens:
        print("[AlphaFusion] No standout fusion signals.")
        return

    for token in tokens:
        msg = format_alert(token)
        if token.get("fusion_summary"):
            msg += f"\n🧠 Fusion Insight: {token['fusion_summary']}\n"
        send_telegram_message(msg)
        print(f"[AlphaFusion] Sent fused alert for {token['symbol']}")

if __name__ == "__main__":
    push_fused_alpha_alerts()
