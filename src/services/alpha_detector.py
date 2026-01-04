# src/services/alpha_detector.py
"""
MirrorX Alpha Detector (Educational)
---------------------------------------
Scans live DexScreener pairs, identifies anomaly-style signals
(moves in price/volume/liquidity) and pushes educational alerts.

Adds:
1) Alert types (breakout / momentum / liquidity spike / volume anomaly / mean-reversion flag)
2) Risk context (educational invalidation guidance + risk notes)
3) Alert persistence (alerts_store) for /api/alerts/recent
4) DexScreener boosts + community takeovers integrated into scoring/tags
"""

from __future__ import annotations

import math
import requests
from datetime import datetime

from src.services.telegram_alerts import send_telegram_message
from src.services.alerts_store import add_alert
from src.services.dexscreener import (
    fetch_token_boosts_latest,
    fetch_token_boosts_top,
    fetch_community_takeovers_latest,
)

DEX_API = "https://api.dexscreener.com/latest/dex/tokens/"
DEFAULT_TOKENS = ["SOL", "JUP", "BONK", "WIF", "PYTH", "MPLX", "JTO"]


def fetch_token_data(symbol: str):
    """Fetch live pair data from DexScreener for a token symbol."""
    try:
        res = requests.get(f"{DEX_API}{symbol}", timeout=10)
        res.raise_for_status()
        return res.json().get("pairs", []) or []
    except Exception as e:
        print(f"[AlphaDetector] Error fetching {symbol}: {e}")
        return []


def _as_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _signal_type(change_1h: float, change_24h: float, volume_24h: float, liquidity_usd: float) -> str:
    """
    Educational classification (not a trading instruction).
    """
    # Volume anomaly first
    if volume_24h >= 3_000_000 and liquidity_usd >= 50_000:
        return "volume_anomaly"

    # Liquidity spike / attention
    if liquidity_usd >= 250_000 and (change_1h >= 20 or change_24h >= 50):
        return "liquidity_spike"

    # Breakout / momentum
    if change_1h >= 70 and liquidity_usd >= 25_000:
        return "breakout"
    if change_24h >= 120 and liquidity_usd >= 25_000:
        return "momentum"

    # Mean-reversion flag (we usually see this on pullbacks, but still educational)
    if change_1h <= -20 and change_24h >= 40 and liquidity_usd >= 25_000:
        return "mean_reversion_flag"

    return "momentum"


def _risk_context(price: float, signal_type: str) -> dict:
    """
    Educational risk framework (NOT a trade instruction).
    Provides a rough invalidation guide + notes.
    """
    if price <= 0:
        return {
            "invalidation_price": None,
            "risk_note": "Price unavailable for risk context.",
        }

    # Simple heuristic bands by signal type
    if signal_type in ("breakout", "momentum"):
        invalidation = price * (1 - 0.15)  # ~15% pullback invalidation guide
        note = "Educational: for momentum/breakouts, many traders invalidate on a ~10–20% reversal or loss of key level."
    elif signal_type in ("liquidity_spike",):
        invalidation = price * (1 - 0.12)
        note = "Educational: liquidity spikes can fade—watch spread, liquidity drop, and failed continuation."
    elif signal_type in ("volume_anomaly",):
        invalidation = price * (1 - 0.18)
        note = "Educational: volume anomalies can be news/rotation driven—watch for volume collapse after the spike."
    else:
        invalidation = price * (1 - 0.10)
        note = "Educational: mean-reversion setups often invalidate on continued weakness / lower lows."

    return {
        "invalidation_price": round(invalidation, 8),
        "risk_note": note,
    }


def _fetch_boost_and_takeover_sets() -> tuple[set[str], set[str]]:
    """
    Returns:
      boosted_token_addresses (set)
      takeover_token_addresses (set)
    """
    boosted = set()
    takeovers = set()

    # Boosts latest + top
    for item in (fetch_token_boosts_latest() or []):
        addr = (item.get("tokenAddress") or "").strip()
        if addr:
            boosted.add(addr)

    for item in (fetch_token_boosts_top() or []):
        addr = (item.get("tokenAddress") or "").strip()
        if addr:
            boosted.add(addr)

    # Community takeovers
    for item in (fetch_community_takeovers_latest() or []):
        addr = (item.get("tokenAddress") or "").strip()
        if addr:
            takeovers.add(addr)

    return boosted, takeovers


def analyze_pairs(pairs, boosted_addrs: set[str] | None = None, takeover_addrs: set[str] | None = None):
    """Evaluate Dex pairs and return candidate signals."""
    boosted_addrs = boosted_addrs or set()
    takeover_addrs = takeover_addrs or set()

    alpha_candidates = []

    for p in pairs:
        try:
            base = p.get("baseToken", {}) or {}
            quote = p.get("quoteToken", {}) or {}

            base_symbol = (base.get("symbol") or "").strip()
            quote_symbol = (quote.get("symbol") or "").strip()
            base_addr = (base.get("address") or "").strip()

            price_usd = _as_float(p.get("priceUsd", 0))
            volume_24h = _as_float((p.get("volume") or {}).get("h24", 0))

            pc = p.get("priceChange") or {}
            change_1h = _as_float(pc.get("h1", 0))
            change_24h = _as_float(pc.get("h24", 0))

            liquidity_usd = _as_float((p.get("liquidity") or {}).get("usd", 0))

            # Baseline filters (keeps spam down)
            if liquidity_usd < 20_000:
                continue

            # Detect “interesting enough” move
            if not (change_1h > 35 or change_24h > 80 or volume_24h > 750_000):
                continue

            stype = _signal_type(change_1h, change_24h, volume_24h, liquidity_usd)

            tags = []
            bonus = 0.0

            if base_addr and base_addr in boosted_addrs:
                tags.append("dex_boost")
                bonus += 25.0

            if base_addr and base_addr in takeover_addrs:
                tags.append("community_takeover")
                bonus += 20.0

            # Educational scoring (not “profit” scoring)
            # Uses change + log(volume) + log(liquidity) + bonuses
            score = (
                (change_1h * 0.7) +
                (change_24h * 0.3) +
                math.log(max(volume_24h, 1.0), 10) * 8.0 +
                math.log(max(liquidity_usd, 1.0), 10) * 6.0 +
                bonus
            )

            alpha_candidates.append({
                "symbol": base_symbol or "UNKNOWN",
                "quote": quote_symbol or "",
                "base_address": base_addr or None,
                "price": price_usd,
                "change_1h": change_1h,
                "change_24h": change_24h,
                "volume": volume_24h,
                "liquidity": liquidity_usd,
                "dex": p.get("dexId"),
                "url": p.get("url"),
                "signal_type": stype,
                "tags": tags,
                "score": round(score, 4),
            })

        except Exception as e:
            print(f"[AlphaDetector] Analysis error: {e}")

    return alpha_candidates


def detect_alpha_tokens(symbols=None):
    """Run alpha detection across token symbols."""
    symbols = symbols or DEFAULT_TOKENS

    boosted, takeovers = _fetch_boost_and_takeover_sets()

    detected = []
    for sym in symbols:
        pairs = fetch_token_data(sym)
        detected.extend(analyze_pairs(pairs, boosted_addrs=boosted, takeover_addrs=takeovers))

    # Rank by score
    return sorted(detected, key=lambda x: x.get("score", 0), reverse=True)


def _human_summary(token: dict) -> str:
    sym = token.get("symbol", "UNK")
    stype = token.get("signal_type", "momentum")
    vol_m = (token.get("volume", 0) or 0) / 1_000_000
    liq = token.get("liquidity", 0) or 0
    dex = token.get("dex", "DEX")

    return (
        f"{sym} flagged as <b>{stype}</b> on {dex}. "
        f"Volume ~{vol_m:.2f}M (24h), liquidity ~${liq:,.0f}."
    )


def format_alert(token: dict) -> str:
    """Telegram message (HTML) with type + risk context + tags."""
    sym = token.get("symbol", "UNK")
    quote = token.get("quote", "")
    price = _as_float(token.get("price", 0))
    ch1 = _as_float(token.get("change_1h", 0))
    ch24 = _as_float(token.get("change_24h", 0))
    vol = _as_float(token.get("volume", 0))
    liq = _as_float(token.get("liquidity", 0))
    dex = token.get("dex", "DEX")
    url = token.get("url", "")

    stype = token.get("signal_type", "momentum")
    tags = token.get("tags", []) or []
    score = token.get("score", 0)

    risk = _risk_context(price, stype)
    inv = risk.get("invalidation_price")

    tags_line = ""
    if tags:
        tags_line = " | Tags: " + ", ".join(tags)

    summary = _human_summary(token)

    msg = (
        f"<b>📊 MirrorX Alpha Alert</b>\n"
        f"Type: <b>{stype}</b>{tags_line}\n"
        f"Score: {score}\n"
        f"Pair: <b>{sym}</b> / {quote}\n"
        f"Price: ${price:.8f}\n"
        f"1h: {ch1}% | 24h: {ch24}%\n"
        f"24h Volume: ${vol:,.0f}\n"
        f"Liquidity: ${liq:,.0f}\n"
        f"DEX: {dex}\n\n"
        f"{summary}\n\n"
        f"<b>🧯 Risk context (educational)</b>\n"
        f"Intra-trend invalidation guide: {('~$' + str(inv)) if inv else 'N/A'}\n"
        f"{risk.get('risk_note','')}\n\n"
        f"<a href='{url}'>View on DexScreener</a>\n\n"
        f"⚠️ Educational signal only — not financial advice."
    )
    return msg


def push_alpha_alerts():
    """Detect + store + push alerts to Telegram."""
    print("[SCHEDULER] Running Alpha Detector...")

    detected = detect_alpha_tokens()
    if not detected:
        print("[AlphaDetector] No standout alpha signals.")
        return

    top_tokens = detected[:5]
    for token in top_tokens:
        msg = format_alert(token)

        # Store for /api/alerts/recent + GPT summaries
        add_alert(
            "alpha_detector",
            {
                "symbol": token.get("symbol"),
                "url": token.get("url"),
                "signal_type": token.get("signal_type"),
                "tags": token.get("tags", []),
                "score": token.get("score"),
                "message": msg,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
        )

        send_telegram_message(msg)
        print(f"[AlphaDetector] Sent alert for {token.get('symbol')}")


if __name__ == "__main__":
    push_alpha_alerts()
