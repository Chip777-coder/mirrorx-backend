# src/services/alpha_detector.py
"""
MirrorX Alpha Detector
---------------------------------------
Scans live DEXScreener data, identifies standout tokens
with high velocity (price, volume, or liquidity spikes),
and pushes actionable alerts to Telegram.

Integrated with scheduler for 3-hour autonomous runs.
"""

import os
import requests
from datetime import datetime
from src.services.telegram_alerts import send_telegram_message

DEX_API = "https://api.dexscreener.com/latest/dex/tokens/"
DEFAULT_TOKENS = ["SOL", "JUP", "BONK", "WIF", "PYTH", "MPLX", "JTO"]

def fetch_token_data(symbol: str):
    """Fetch live pair data from DexScreener for a token."""
    try:
        res = requests.get(f"{DEX_API}{symbol}", timeout=10)
        res.raise_for_status()
        data = res.json().get("pairs", [])
        return data or []
    except Exception as e:
        print(f"[AlphaDetector] Error fetching {symbol}: {e}")
        return []

def analyze_pairs(pairs):
    """Evaluate pairs and find alpha candidates."""
    alpha_candidates = []
    for p in pairs:
        try:
            base_token = p.get("baseToken", {}).get("symbol")
            quote_token = p.get("quoteToken", {}).get("symbol")
            price_usd = float(p.get("priceUsd", 0))
            volume_24h = float(p.get("volume", {}).get("h24", 0))
            price_change = p.get("priceChange", {})
            change_1h = float(price_change.get("h1", 0))
            change_24h = float(price_change.get("h24", 0))
            liquidity_usd = float(p.get("liquidity", {}).get("usd", 0))

            # Core Alpha Filters
            if (
                liquidity_usd > 20000 and
                (change_1h > 35 or change_24h > 80 or volume_24h > 750000)
            ):
                alpha_candidates.append({
                    "symbol": base_token,
                    "quote": quote_token,
                    "price": price_usd,
                    "change_1h": change_1h,
                    "change_24h": change_24h,
                    "volume": volume_24h,
                    "liquidity": liquidity_usd,
                    "dex": p.get("dexId"),
                    "url": p.get("url")
                })
        except Exception as e:
            print(f"[AlphaDetector] Analysis error: {e}")
    return alpha_candidates

def detect_alpha_tokens(symbols=None):
    """Run alpha detection for multiple tokens."""
    if symbols is None:
        symbols = DEFAULT_TOKENS
    detected = []
    for sym in symbols:
        pairs = fetch_token_data(sym)
        detected += analyze_pairs(pairs)
    return sorted(detected, key=lambda x: x["change_1h"] + x["change_24h"], reverse=True)

def format_alert(token):
    """Craft a compelling, contextual alert message."""
    performance = ""
    if token["change_1h"] >= 100:
        performance = f"🚀 {token['symbol']} holders are already up {int(token['change_1h'])}x in the last hour!"
    elif token["change_1h"] >= 40:
        performance = f"🔥 Strong rally forming — {token['change_1h']}% in 1h!"
    elif token["change_24h"] >= 100:
        performance = f"⚡ {token['symbol']} showing parabolic 24h growth: +{token['change_24h']}%"
    else:
        performance = f"⏳ Building momentum: {token['change_1h']}% (1h)"

    message = (
        f"<b>📊 MirrorX Alpha Alert</b>\n"
        f"Token: <b>{token['symbol']}</b> / {token['quote']}\n"
        f"Price: ${token['price']:.4f}\n"
        f"1h Change: {token['change_1h']}%\n"
        f"24h Change: {token['change_24h']}%\n"
        f"24h Volume: ${token['volume']:,.0f}\n"
        f"Liquidity: ${token['liquidity']:,.0f}\n"
        f"DEX: {token['dex']}\n\n"
        f"{performance}\n"
        f"<a href='{token['url']}'>View on DexScreener</a>\n\n"
        f"💡 MirrorX surfaces early market anomalies before retail momentum. "
        f"Signals like these have historically preceded 100x+ runs."
    )
    return message

def push_alpha_alerts():
    """Detect and push live alpha alerts to Telegram."""
    print("[SCHEDULER] Running Alpha Detector...")
    detected = detect_alpha_tokens()

    if not detected:
        print("[AlphaDetector] No standout alpha signals.")
        return

    # Limit to strongest 3–5 tokens
    top_tokens = detected[:5]
    for token in top_tokens:
        msg = format_alert(token)
        send_telegram_message(msg)
        print(f"[AlphaDetector] Sent alert for {token['symbol']}")

if __name__ == "__main__":
    # Local debug test
    push_alpha_alerts()
