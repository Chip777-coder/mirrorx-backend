# src/services/alpha_detector.py
"""
MirrorX Alpha Detector
---------------------------------------
Scans live DEXScreener data, identifies standout tokens
with high velocity (price, volume, or liquidity spikes),
and pushes actionable alerts to Telegram.

Integrated with scheduler for autonomous runs.
"""

import requests
from datetime import datetime
from src.services.telegram_alerts import send_telegram_message
from src.services.alerts_store import add_alert

DEX_API = "https://api.dexscreener.com/latest/dex/tokens/"
DEFAULT_TOKENS = ["SOL", "JUP", "BONK", "WIF", "PYTH", "MPLX", "JTO"]


def fetch_token_data(symbol: str):
    """Fetch live pair data from DexScreener for a token."""
    try:
        res = requests.get(f"{DEX_API}{symbol}", timeout=10)
        res.raise_for_status()
        return res.json().get("pairs", []) or []
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

            # Core Alpha Filters (educational / anomaly-based)
            if (
                liquidity_usd > 20_000
                and (change_1h > 35 or change_24h > 80 or volume_24h > 750_000)
            ):
                alpha_candidates.append(
                    {
                        "symbol": base_token,
                        "quote": quote_token,
                        "price": price_usd,
                        "change_1h": change_1h,
                        "change_24h": change_24h,
                        "volume": volume_24h,
                        "liquidity": liquidity_usd,
                        "dex": p.get("dexId"),
                        "url": p.get("url"),
                    }
                )
        except Exception as e:
            print(f"[AlphaDetector] Analysis error: {e}")

    return alpha_candidates


def detect_alpha_tokens(symbols=None):
    """Run alpha detection for multiple tokens."""
    symbols = symbols or DEFAULT_TOKENS
    detected = []

    for sym in symbols:
        pairs = fetch_token_data(sym)
        detected.extend(analyze_pairs(pairs))

    return sorted(
        detected,
        key=lambda x: x["change_1h"] + x["change_24h"],
        reverse=True,
    )


def generate_alpha_summary(token):
    """Create a human-readable educational narrative."""
    sym = token["symbol"]
    change_1h = token.get("change_1h", 0)
    change_24h = token.get("change_24h", 0)
    volume = token.get("volume", 0)
    dex = token.get("dex", "Unknown DEX")
    liquidity = token.get("liquidity", 0)

    if change_1h >= 150:
        return (
            f"{sym} is surging aggressively (+{change_1h}% in 1h) with "
            f"${volume/1_000_000:.1f}M volume on {dex}. "
            f"Liquidity at ${liquidity:,.0f} suggests early momentum."
        )
    elif change_24h >= 80:
        return (
            f"{sym} gained {change_24h}% over 24h on {dex}, driven by "
            f"${volume/1_000_000:.1f}M volume and growing liquidity."
        )
    else:
        return (
            f"{sym} is showing early momentum (+{change_1h}% 1h) with "
            f"${volume/1_000_000:.1f}M traded on {dex}."
        )


def format_alert(token):
    """Craft a contextual Telegram alert."""
    narrative = generate_alpha_summary(token)

    message = (
        f"<b>📊 MirrorX Alpha Alert</b>\n"
        f"Token: <b>{token['symbol']}</b> / {token['quote']}\n"
        f"Price: ${token['price']:.6f}\n"
        f"1h Change: {token['change_1h']}%\n"
        f"24h Change: {token['change_24h']}%\n"
        f"24h Volume: ${token['volume']:,.0f}\n"
        f"Liquidity: ${token['liquidity']:,.0f}\n"
        f"DEX: {token['dex']}\n\n"
        f"{narrative}\n\n"
        f"<a href='{token['url']}'>View on DexScreener</a>\n\n"
        f"⚠️ Educational signal only — not financial advice."
    )

    return message


def push_alpha_alerts():
    """Detect and push live alpha alerts."""
    print("[SCHEDULER] Running Alpha Detector...")

    detected = detect_alpha_tokens()
    if not detected:
        print("[AlphaDetector] No standout alpha signals.")
        return

    for token in detected[:5]:
        msg = format_alert(token)

        # Store alert for API / GPT access
        add_alert(
            "alpha_detector",
            {
                "symbol": token.get("symbol"),
                "url": token.get("url"),
                "message": msg,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
        )

        # Telegram push
        send_telegram_message(msg)
        print(f"[AlphaDetector] Sent alert for {token['symbol']}")


if __name__ == "__main__":
    push_alpha_alerts()
