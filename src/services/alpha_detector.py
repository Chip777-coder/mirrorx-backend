# src/services/alpha_detector.py
"""
MirrorX Alpha Detector (Rocket Mode + Moonshot Exception)
---------------------------------------------------------
Old behavior: scan fixed symbols like SOL/BONK/WIF...
New behavior: dynamically discover candidates (boosts/profiles) and scan by token address.

Goal:
- Catch early-stage rockets (10k%+ movers) without drowning in junk.

How:
1) Discovery (Dex Radar): boosts/profiles/takeovers => candidate token addresses
2) Fetch best pair per token address
3) Apply gates:
   - Normal "quality" gate (liquidity + volume + movement)
   - Moonshot exception gate (lower liquidity allowed ONLY if move is extreme + volume non-trivial)
4) Store snapshots (movers_store) for acceleration context
5) Alert to Telegram + persist to alerts_store (optional)

Educational tooling only. Not trade advice.
"""

from __future__ import annotations

import os
import requests
from datetime import datetime, timezone

from src.services.telegram_alerts import send_telegram_message
from src.services.dex_radar import get_top_candidates
from src.services.movers_store import record_snapshot, compute_acceleration

# Optional alert store (safe if file doesn't exist)
try:
    from src.services.alerts_store import add_alert  # type: ignore
except Exception:
    def add_alert(_source: str, _payload: dict):  # fallback no-op
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
# (lets us catch early ignition)
# ----------------------------
MOONSHOT_ENABLE = os.getenv("ALPHA_MOONSHOT_ENABLE", "1") == "1"
MOONSHOT_MIN_LIQ_USD = float(os.getenv("ALPHA_MOONSHOT_MIN_LIQ_USD", "8000"))
MOONSHOT_MIN_VOL_1H = float(os.getenv("ALPHA_MOONSHOT_MIN_VOL_1H", "25000"))
MOONSHOT_CH_M5 = float(os.getenv("ALPHA_MOONSHOT_CH_M5", "80"))     # 5m change threshold
MOONSHOT_CH_1H = float(os.getenv("ALPHA_MOONSHOT_CH_1H", "250"))    # 1h change threshold

# Movement floor (applies to both paths)
MIN_MOVE_ANY = float(os.getenv("ALPHA_MIN_MOVE_ANY", "25"))         # must be moving at least this much in m5/h1/h24

# Discovery scan size
RADAR_LIMIT = int(os.getenv("ALPHA_RADAR_LIMIT", "60"))

# Telegram: max alerts per run
MAX_ALERTS = int(os.getenv("ALPHA_MAX_ALERTS", "5"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def fetch_pairs_by_address(token_address: str) -> list[dict]:
    """Fetch live pair data from DexScreener for a Solana token mint/address."""
    try:
        r = requests.get(f"{DEX_TOKEN_PAIRS}{token_address}", timeout=12)
        r.raise_for_status()
        return r.json().get("pairs", []) or []
    except Exception:
        return []


def fetch_pairs_by_search(query: str) -> list[dict]:
    """Fallback: search by symbol/pair query."""
    try:
        r = requests.get(DEX_SEARCH, params={"q": query}, timeout=12)
        r.raise_for_status()
        return r.json().get("pairs", []) or []
    except Exception:
        return []


def _best_pair_by_liquidity(pairs: list[dict]) -> dict:
    if not pairs:
        return {}
    return sorted(
        pairs,
        key=lambda p: _safe_float((p.get("liquidity") or {}).get("usd"), 0.0),
        reverse=True
    )[0]


def _passes_normal_gate(liq_usd: float, vol_1h: float, vol_24h: float) -> bool:
    return (liq_usd >= MIN_LIQ_USD) and (vol_1h >= MIN_VOL_1H or vol_24h >= MIN_VOL_24H)


def _passes_moonshot_gate(liq_usd: float, vol_1h: float, ch_m5: float, ch_1h: float) -> bool:
    """
    Moonshot exception:
    - allow lower liquidity, BUT require:
      - some real volume
      - extreme short-term move
    This catches early ignition before liquidity scales.
    """
    if not MOONSHOT_ENABLE:
        return False
    if liq_usd < MOONSHOT_MIN_LIQ_USD:
        return False
    if vol_1h < MOONSHOT_MIN_VOL_1H:
        return False
    if (ch_m5 >= MOONSHOT_CH_M5) or (ch_1h >= MOONSHOT_CH_1H):
        return True
    return False


def analyze_pair(pair: dict) -> dict | None:
    """
    Convert a Dex pair into a normalized candidate if it passes gates.
    """
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

    # Must be moving (avoid dead tokens)
    if max(ch_m5, ch_1h, ch_24h) < MIN_MOVE_ANY:
        return None

    # Gate logic:
    # 1) Normal quality gate OR 2) Moonshot exception gate
    normal_ok = _passes_normal_gate(liq_usd, vol_1h, vol_24h)
    moonshot_ok = _passes_moonshot_gate(liq_usd, vol_1h, ch_m5, ch_1h)

    if not (normal_ok or moonshot_ok):
        return None

    gate_used = "normal" if normal_ok else "moonshot"

    out = {
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
    return out


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

    message = (
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
    return message


def detect_alpha_tokens() -> list[dict]:
    """
    1) Discover candidates from Dex Radar (boosts/profiles)
    2) Fetch best pair per token address
    3) Apply gates + rank
    """
    candidates = get_top_candidates(limit=RADAR_LIMIT) or []
    if not candidates:
        return []

    found: list[dict] = []

    for c in candidates:
        addr = c.get("address")
        if not addr:
            continue

        pairs = fetch_pairs_by_address(addr)
        best = _best_pair_by_liquidity(pairs)
        if not best:
            continue

        token = analyze_pair(best)
        if not token:
            continue

        # Store snapshot for acceleration tracking
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

    # Rank: emphasize short-term acceleration + liquidity + volume
    def score(t: dict) -> float:
        gate = t.get("gate", "normal")
        gate_boost = 15.0 if gate == "moonshot" else 0.0  # small boost so moonshots bubble up
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
    """Detect and push live rocket alerts to Telegram."""
    print("[SCHEDULER] Running Rocket Alpha Detector...")
    detected = detect_alpha_tokens()

    if not detected:
        print("[AlphaDetector] No standout rocket signals.")
        return

    top = detected[:MAX_ALERTS]

    for token in top:
        msg = format_alert(token)

        # store in alerts store (if enabled)
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
