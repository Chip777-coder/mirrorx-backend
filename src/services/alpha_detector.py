# src/services/alpha_detector.py
"""
MirrorX Alpha Detector (Rocket Mode + Moonshot Exception)
---------------------------------------------------------
Dynamically discover candidates (boosts/profiles/takeovers) and scan by token address.

Key improvement in this version:
✅ Adds 429 backoff + pacing for DexScreener token-pairs fetches
   so 15-min runs stay consistent and don't "thin out" from rate limits.
"""

from __future__ import annotations

import os
import time
import random
import requests
from datetime import datetime, timezone

from src.services.telegram_alerts import send_telegram_message
from src.services.dex_radar import get_top_candidates
from src.services.movers_store import record_snapshot, compute_acceleration

# Optional alert store (safe if file doesn't exist)
try:
    from src.services.alerts_store import add_alert  # type: ignore
except Exception:
    def add_alert(_source: str, _payload: dict):
        return


DEX_BASE = "https://api.dexscreener.com"
DEX_TOKEN_PAIRS = f"{DEX_BASE}/latest/dex/tokens/"  # /latest/dex/tokens/{tokenAddress}
DEX_SEARCH = f"{DEX_BASE}/latest/dex/search"        # ?q=SYMBOL

# ----------------------------
# Normal safety gates (tune)
# ----------------------------
MIN_LIQ_USD = float(os.getenv("ALPHA_MIN_LIQ_USD", "30000"))
MIN_VOL_1H = float(os.getenv("ALPHA_MIN_VOL_1H", "150000"))
MIN_VOL_24H = float(os.getenv("ALPHA_MIN_VOL_24H", "750000"))

# ----------------------------
# Moonshot exception gates
# ----------------------------
MOONSHOT_ENABLE = os.getenv("ALPHA_MOONSHOT_ENABLE", "1") == "1"
MOONSHOT_MIN_LIQ_USD = float(os.getenv("ALPHA_MOONSHOT_MIN_LIQ_USD", "8000"))
MOONSHOT_MIN_VOL_1H = float(os.getenv("ALPHA_MOONSHOT_MIN_VOL_1H", "25000"))
MOONSHOT_MIN_VOL_24H = float(os.getenv("ALPHA_MOONSHOT_MIN_VOL_24H", "150000"))
MOONSHOT_CH_M5 = float(os.getenv("ALPHA_MOONSHOT_CH_M5", "80"))
MOONSHOT_CH_1H = float(os.getenv("ALPHA_MOONSHOT_CH_1H", "250"))

# Movement floor
MIN_MOVE_ANY = float(os.getenv("ALPHA_MIN_MOVE_ANY", "25"))

# Discovery scan size
RADAR_LIMIT = int(os.getenv("ALPHA_RADAR_LIMIT", "60"))

# Telegram: max alerts per run
MAX_ALERTS = int(os.getenv("ALPHA_MAX_ALERTS", "5"))

# ----------------------------
# DexScreener safety controls
# ----------------------------
DEX_HTTP_TIMEOUT = int(os.getenv("DEX_HTTP_TIMEOUT", "12"))
DEX_FETCH_PAUSE_SECONDS = float(os.getenv("ALPHA_DEX_FETCH_PAUSE_SECONDS", "0.08"))  # pause per token
DEX_429_BACKOFF_SECONDS = float(os.getenv("ALPHA_DEX_429_BACKOFF_SECONDS", "2.25"))
DEX_429_MAX_RETRIES = int(os.getenv("ALPHA_DEX_429_MAX_RETRIES", "2"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _sleep_jitter(base: float) -> None:
    time.sleep(max(0.0, base + random.uniform(-0.03, 0.06)))


def _get_json_with_backoff(url: str, params: dict | None = None, timeout: int | None = None) -> dict | None:
    t = timeout or DEX_HTTP_TIMEOUT
    last_err: Exception | None = None

    for attempt in range(DEX_429_MAX_RETRIES + 1):
        try:
            r = requests.get(url, params=params or {}, timeout=t)
            if r.status_code == 429:
                wait = DEX_429_BACKOFF_SECONDS * (attempt + 1)
                _sleep_jitter(wait)
                continue
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, dict) else None
        except Exception as e:
            last_err = e
            _sleep_jitter(0.2)

    # swallow, return None so pipeline continues
    return None


def fetch_pairs_by_address(token_address: str) -> list[dict]:
    """Fetch live pair data from DexScreener for a Solana token mint/address (with 429 backoff)."""
    data = _get_json_with_backoff(f"{DEX_TOKEN_PAIRS}{token_address}", timeout=DEX_HTTP_TIMEOUT)
    if not data:
        return []
    pairs = data.get("pairs", [])
    return pairs if isinstance(pairs, list) else []


def fetch_pairs_by_search(query: str) -> list[dict]:
    """Fallback: search by symbol/pair query (with 429 backoff)."""
    data = _get_json_with_backoff(DEX_SEARCH, params={"q": query}, timeout=DEX_HTTP_TIMEOUT)
    if not data:
        return []
    pairs = data.get("pairs", [])
    return pairs if isinstance(pairs, list) else []


def _best_pair_by_liquidity(pairs: list[dict]) -> dict:
    if not pairs:
        return {}
    return sorted(
        pairs,
        key=lambda p: _safe_float((p.get("liquidity") or {}).get("usd"), 0.0),
        reverse=True
    )[0]


def _best_pair_combo(pairs: list[dict]) -> dict:
    """Pick the pair most likely driving trending: momentum + participation."""
    if not pairs:
        return {}

    def s(p: dict) -> float:
        liq = _safe_float((p.get("liquidity") or {}).get("usd"), 0.0)
        vol = p.get("volume") or {}
        v1 = _safe_float(vol.get("h1"), 0.0)

        pc = p.get("priceChange") or {}
        ch5 = _safe_float(pc.get("m5"), 0.0)
        ch1 = _safe_float(pc.get("h1"), 0.0)

        score = (
            ch5 * 1.45 +
            ch1 * 0.85 +
            (liq / 20_000.0) +
            (v1 / 50_000.0)
        )

        if liq < 4_000 and (ch5 > 80 or ch1 > 200):
            score *= 0.25

        return score

    return sorted(pairs, key=s, reverse=True)[0]


def _passes_normal_gate(liq_usd: float, vol_1h: float, vol_24h: float) -> bool:
    return (liq_usd >= MIN_LIQ_USD) and (vol_1h >= MIN_VOL_1H or vol_24h >= MIN_VOL_24H)


def _passes_moonshot_gate(liq_usd: float, vol_1h: float, vol_24h: float, ch_m5: float, ch_1h: float) -> bool:
    if not MOONSHOT_ENABLE:
        return False
    if liq_usd < MOONSHOT_MIN_LIQ_USD:
        return False
    if not (vol_1h >= MOONSHOT_MIN_VOL_1H or vol_24h >= MOONSHOT_MIN_VOL_24H):
        return False
    return (ch_m5 >= MOONSHOT_CH_M5) or (ch_1h >= MOONSHOT_CH_1H)


def analyze_pair(pair: dict) -> dict | None:
    if not isinstance(pair, dict):
        return None

    base = pair.get("baseToken") or {}
    quote = pair.get("quoteToken") or {}

    symbol = (base.get("symbol") or "").upper()
    address = base.get("address") or ""
    price_usd = _safe_float(pair.get("priceUsd"), 0.0)

    vol = pair.get("volume") or {}
    vol_1h = _safe_float(vol.get("h1"), 0.0)
    vol_24h = _safe_float(vol.get("h24"), 0.0)

    pc = pair.get("priceChange") or {}
    ch_m5 = _safe_float(pc.get("m5"), 0.0)
    ch_1h = _safe_float(pc.get("h1"), 0.0)
    ch_24h = _safe_float(pc.get("h24"), 0.0)

    liq = pair.get("liquidity") or {}
    liq_usd = _safe_float(liq.get("usd"), 0.0)

    if max(ch_m5, ch_1h, ch_24h) < MIN_MOVE_ANY:
        return None

    normal_ok = _passes_normal_gate(liq_usd, vol_1h, vol_24h)
    moonshot_ok = _passes_moonshot_gate(liq_usd, vol_1h, vol_24h, ch_m5, ch_1h)

    if not (normal_ok or moonshot_ok):
        return None

    gate_used = "normal" if normal_ok else "moonshot"

    return {
        "address": address,
        "symbol": symbol,
        "quote": (quote.get("symbol") or "").upper(),
        "price": price_usd,
        "change_m5": ch_m5,
        "change_1h": ch_1h,
        "change_24h": ch_24h,
        "volume_1h": vol_1h,
        "volume_24h": vol_24h,
        "liquidity": liq_usd,
        "dex": pair.get("dexId"),
        "pairAddress": pair.get("pairAddress"),
        "url": pair.get("url"),
        "chainId": pair.get("chainId"),
        "gate": gate_used,
    }


def generate_alpha_summary(token: dict) -> str:
    sym = token.get("symbol", "UNKNOWN")
    ch1 = _safe_float(token.get("change_1h"), 0)
    ch24 = _safe_float(token.get("change_24h"), 0)
    ch5 = _safe_float(token.get("change_m5"), 0)
    vol1 = _safe_float(token.get("volume_1h"), 0)
    liq = _safe_float(token.get("liquidity"), 0)
    dex = token.get("dex", "DEX")
    gate = token.get("gate", "normal")

    if gate == "moonshot":
        return (
            f"{sym} triggered the <b>Moonshot</b> gate (+{ch5:.1f}% 5m / +{ch1:.1f}% 1h) "
            f"with ${liq:,.0f} liq and ~${vol1/1_000_000:.2f}M 1h volume on {dex}. "
            f"These can be explosive — and can also reverse violently."
        )

    if ch1 >= 150:
        return (
            f"{sym} is exploding (+{ch1:.1f}% 1h) with ~${vol1/1_000_000:.2f}M 1h volume on {dex}. "
            f"Liquidity is ${liq:,.0f} — strong rockets usually keep liquidity rising."
        )
    if ch24 >= 300:
        return (
            f"{sym} is in a high-volatility expansion (+{ch24:.1f}% 24h). "
            f"Liquidity ${liq:,.0f} with heavy participation on {dex}."
        )
    return (
        f"{sym} is accelerating (+{ch1:.1f}% 1h / +{ch5:.1f}% 5m) with ${liq:,.0f} liquidity and "
        f"~${vol1/1_000_000:.2f}M 1h volume on {dex}."
    )


def format_alert(token: dict) -> str:
    accel = compute_acceleration(token.get("address", ""))
    accel_hint = accel.get("accel_hint", "n/a")

    narrative = generate_alpha_summary(token)

    return (
        f"<b>📊 MirrorX Rocket Alert</b>\n"
        f"Token: <b>{token.get('symbol')}</b> / {token.get('quote')}\n"
        f"Gate: <b>{token.get('gate','normal')}</b>\n"
        f"Mint: <code>{token.get('address')}</code>\n"
        f"Price: ${_safe_float(token.get('price'), 0):.8f}\n"
        f"5m: {token.get('change_m5', 0):.1f}% | 1h: {token.get('change_1h', 0):.1f}% | 24h: {token.get('change_24h', 0):.1f}%\n"
        f"Vol 1h: ${_safe_float(token.get('volume_1h'), 0):,.0f} | Vol 24h: ${_safe_float(token.get('volume_24h'), 0):,.0f}\n"
        f"Liq: ${_safe_float(token.get('liquidity'), 0):,.0f} | DEX: {token.get('dex')}\n"
        f"Acceleration: <b>{accel_hint}</b>\n\n"
        f"{narrative}\n\n"
        f"<a href='{token.get('url')}'>View on DexScreener</a>\n\n"
        f"⚠️ Educational alert only. Use strict risk controls; fast movers can reverse hard."
    )


def detect_alpha_tokens() -> list[dict]:
    candidates = get_top_candidates(limit=RADAR_LIMIT) or []
    if not candidates:
        return []

    found: list[dict] = []

    for c in candidates:
        addr = c.get("address")
        if not addr:
            continue

        pairs = fetch_pairs_by_address(addr)
        best = _best_pair_combo(pairs)
        if not best:
            _sleep_jitter(DEX_FETCH_PAUSE_SECONDS)
            continue

        token = analyze_pair(best)
        if not token:
            _sleep_jitter(DEX_FETCH_PAUSE_SECONDS)
            continue

        record_snapshot("alpha_detector", {
            "address": token.get("address"),
            "symbol": token.get("symbol"),
            "priceUsd": token.get("price"),
            "liquidityUsd": token.get("liquidity"),
            "volumeH1": token.get("volume_1h"),
            "volumeH24": token.get("volume_24h"),
            "changeM5": token.get("change_m5"),
            "changeH1": token.get("change_1h"),
            "changeH24": token.get("change_24h"),
            "url": token.get("url"),
            "gate": token.get("gate"),
            "ts": _now_iso(),
        })

        found.append(token)
        _sleep_jitter(DEX_FETCH_PAUSE_SECONDS)

    def score(t: dict) -> float:
        gate = t.get("gate", "normal")
        gate_boost = 15.0 if gate == "moonshot" else 0.0
        return (
            gate_boost +
            _safe_float(t.get("change_m5"), 0) * 1.35 +
            _safe_float(t.get("change_1h"), 0) * 0.9 +
            _safe_float(t.get("volume_1h"), 0) / 250_000.0 +
            _safe_float(t.get("liquidity"), 0) / 150_000.0
        )

    found.sort(key=score, reverse=True)
    return found


def push_alpha_alerts():
    print("[SCHEDULER] Running Rocket Alpha Detector...")
    detected = detect_alpha_tokens()

    if not detected:
        print("[AlphaDetector] No standout rocket signals.")
        return

    top = detected[:MAX_ALERTS]

    for token in top:
        msg = format_alert(token)

        try:
            add_alert("alpha_detector", {
                "symbol": token.get("symbol"),
                "address": token.get("address"),
                "url": token.get("url"),
                "gate": token.get("gate"),
                "message": msg,
            })
        except Exception:
            pass

        send_telegram_message(msg)
        print(f"[AlphaDetector] Sent rocket alert for {token.get('symbol')} ({token.get('address')})")


if __name__ == "__main__":
    push_alpha_alerts()
