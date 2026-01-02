# src/services/alpha_detector.py
import requests
from datetime import datetime
from src.services.telegram_alerts import send_telegram_message

DEX_API = "https://api.dexscreener.com/latest/dex/tokens/"

def detect_alpha_tokens(top_symbols=["SOL", "JUP", "BONK"]):
    """Detect high-momentum or high-return tokens."""
    detected = []
    for sym in top_symbols:
        try:
            res = requests.get(f"{DEX_API}{sym}", timeout=10)
            data = res.json().get("pairs", [])
            if not data:
                continue

            for pair in data[:3]:  # Limit to top pairs
                price_change = pair.get("priceChange", {})
                volume = float(pair.get("volume", {}).get("h24", 0))
                price = float(pair.get("priceUsd", 0))

                if price_change and price_change.get("h1", 0) > 40 or volume > 1_000_000:
                    detected.append({
                        "symbol": sym,
                        "pair": pair.get("pairAddress"),
                        "price": price,
                        "change": price_change.get("h1"),
                        "volume": volume
                    })
        except Exception as e:
            print("[AlphaDetector] Error:", e)

    return detected


def push_alpha_alerts():
    """Send only meaningful alpha-grade alerts."""
    detected = detect_alpha_tokens()
    if not detected:
        print("[AlphaDetector] No standout alpha signals.")
        return

    for token in detected:
        msg = (
            f"🔥 <b>MirrorX Alpha Signal</b>\n"
            f"Token: {token['symbol']}\n"
            f"📈 Price: ${token['price']:.4f}\n"
            f"💥 1h Change: {token['change']}%\n"
            f"💧 24h Volume: ${token['volume']:,.0f}\n\n"
            f"💡 If you caught this early, you'd already be up huge — "
            f"MirrorX Alpha spots early movers before they hit mainstream."
        )
        send_telegram_message(msg)
