# src/services/dex_radar.py
"""
MirrorX Dex Radar (Solana Rocket Finder)
---------------------------------------
Builds a dynamic candidate list of fast-moving Solana tokens using:
  - token-boosts/top
  - token-boosts/latest
  - token-profiles/latest
  - community-takeovers/latest

Then enriches with /tokens/v1/solana/{addresses} where possible,
and returns a ranked list of candidates.

This is discovery (universe building).
"""

from __future__ import annotations

import os
import time
import random
import requests
from typing import Any

DEX_BASE = "https://api.dexscreener.com"

# If you prefer the backend proxy, set DEX_RADAR_USE_PROXY=1
USE_PROXY = os.getenv("DEX_RADAR_USE_PROXY", "0") == "1"
PROXY_BASE = os.getenv("DEX_PROXY_BASE", "https://mirrorx-backend.onrender.com")

CHAIN_ID = "solana"

# ---- Rate-limit safety knobs (env overridable) ----
DEX_HTTP_TIMEOUT = int(os.getenv("DEX_HTTP_TIMEOUT", "12"))
DEX_FEED_PAUSE_SECONDS = float(os.getenv("DEX_FEED_PAUSE_SECONDS", "0.35"))     # pause between discovery feeds
DEX_CHUNK_PAUSE_SECONDS = float(os.getenv("DEX_CHUNK_PAUSE_SECONDS", "0.18"))   # pause between tokens/v1 chunks
DEX_429_BACKOFF_SECONDS = float(os.getenv("DEX_429_BACKOFF_SECONDS", "2.25"))   # base backoff
DEX_429_MAX_RETRIES = int(os.getenv("DEX_429_MAX_RETRIES", "2"))

# Optional: cache radar results briefly to avoid re-pulling feeds too often
DEX_RADAR_CACHE_SECONDS = int(os.getenv("DEX_RADAR_CACHE_SECONDS", "120"))  # 2 minutes
_cached_at = 0.0
_cached_payload: list[dict] | None = None


def _dex_url(path: str) -> str:
    if USE_PROXY:
        # our proxy exposes /api/dex/... routes that map to DexScreener endpoints
        return f"{PROXY_BASE}{path}"
    return f"{DEX_BASE}{path}"


def _safe_float(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _sleep_jitter(base: float) -> None:
    # small random jitter to avoid synchronized bursts
    time.sleep(max(0.0, base + random.uniform(-0.05, 0.08)))


def _get_json(url: str, params: dict | None = None, timeout: int | None = None) -> Any:
    """
    HTTP GET with lightweight 429 backoff (DexScreener will 429 on bursts).
    Safe, minimal retries.
    """
    t = timeout or DEX_HTTP_TIMEOUT
    last_err: Exception | None = None

    for attempt in range(DEX_429_MAX_RETRIES + 1):
        try:
            r = requests.get(url, params=params or {}, timeout=t)
            if r.status_code == 429:
                # Backoff + jitter, then retry
                wait = DEX_429_BACKOFF_SECONDS * (attempt + 1)
                _sleep_jitter(wait)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            # brief pause on transient errors
            _sleep_jitter(0.25)

    if last_err:
        raise last_err
    return None


def _extract_candidates_from_boosts(items: list[dict]) -> list[dict]:
    out = []
    for it in items or []:
        chain = (it.get("chainId") or "").lower()
        if chain != CHAIN_ID:
            continue
        addr = it.get("tokenAddress") or it.get("address")
        if not addr:
            continue
        out.append({"chainId": CHAIN_ID, "address": addr, "source": "boosts", "raw": it})
    return out


def _extract_candidates_from_profiles(items: list[dict]) -> list[dict]:
    out = []
    for it in items or []:
        chain = (it.get("chainId") or "").lower()
        if chain != CHAIN_ID:
            continue
        addr = it.get("tokenAddress") or it.get("address")
        if not addr:
            continue
        out.append({"chainId": CHAIN_ID, "address": addr, "source": "profiles", "raw": it})
    return out


def _extract_candidates_from_takeovers(items: list[dict]) -> list[dict]:
    out = []
    for it in items or []:
        chain = (it.get("chainId") or "").lower()
        if chain != CHAIN_ID:
            continue
        addr = it.get("tokenAddress")
        if not addr:
            continue
        out.append({"chainId": CHAIN_ID, "address": addr, "source": "takeover", "raw": it})
    return out


def _dedupe_by_address(cands: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for c in cands:
        a = c.get("address")
        if not a or a in seen:
            continue
        seen.add(a)
        out.append(c)
    return out


def _enrich_tokens_v1(addresses: list[str]) -> dict[str, dict]:
    """
    Calls /tokens/v1/solana/{commaSeparated}
    Returns mapping: address -> token_data (best effort)
    """
    if not addresses:
        return {}

    chunk_size = int(os.getenv("DEX_TOKENS_V1_CHUNK", "25"))
    chunk_size = max(5, min(chunk_size, 30))

    out: dict[str, dict] = {}

    for i in range(0, len(addresses), chunk_size):
        chunk = addresses[i : i + chunk_size]
        joined = ",".join(chunk)

        if USE_PROXY:
            url = _dex_url(f"/api/dex/tokens/v1/{CHAIN_ID}/{joined}")
        else:
            url = _dex_url(f"/tokens/v1/{CHAIN_ID}/{joined}")

        try:
            data = _get_json(url, timeout=14)

            if isinstance(data, dict):
                tokens = data.get("tokens") if isinstance(data.get("tokens"), list) else None
                if tokens:
                    for t in tokens:
                        addr = t.get("address") or t.get("tokenAddress")
                        if addr:
                            out[addr] = t
                elif isinstance(data.get("pairs"), list):
                    for p in data.get("pairs", []):
                        base = p.get("baseToken") or {}
                        addr = base.get("address")
                        if addr and addr not in out:
                            out[addr] = {"pair": p}
            elif isinstance(data, list):
                for t in data:
                    addr = t.get("address") or t.get("tokenAddress")
                    if addr:
                        out[addr] = t
        except Exception:
            # swallow enrichment errors; discovery can still work
            pass

        _sleep_jitter(DEX_CHUNK_PAUSE_SECONDS)

    return out


def _rocket_score(enriched: dict) -> float:
    """
    Educational scoring. NOT trade advice.
    """
    liq = 0.0
    vol24 = 0.0
    vol1h = 0.0
    ch1h = 0.0
    ch5m = 0.0

    pair = enriched.get("pair") if isinstance(enriched.get("pair"), dict) else enriched
    if isinstance(pair, dict):
        liq = _safe_float((pair.get("liquidity") or {}).get("usd"), 0.0)
        vol24 = _safe_float((pair.get("volume") or {}).get("h24"), 0.0)
        vol1h = _safe_float((pair.get("volume") or {}).get("h1"), 0.0)
        pc = pair.get("priceChange") or {}
        ch1h = _safe_float(pc.get("h1"), 0.0)
        ch5m = _safe_float(pc.get("m5"), 0.0)

    score = 0.0
    score += min(liq / 100_000.0, 8.0) * 10.0
    score += min(vol24 / 2_000_000.0, 8.0) * 8.0
    score += min(vol1h / 500_000.0, 8.0) * 7.0
    score += max(ch1h, 0.0) * 0.35
    score += max(ch5m, 0.0) * 0.65

    if liq < 10_000 and (ch1h > 200 or ch5m > 80):
        score *= 0.35

    return float(score)


def get_top_candidates(limit: int = 60) -> list[dict]:
    """
    Returns ranked candidate tokens:
      { address, chainId, score, source, enriched? }

    Includes a short cache to avoid hammering DexScreener if multiple runs
    happen close together (e.g., worker restart).
    """
    global _cached_at, _cached_payload

    limit = max(1, int(limit))

    # cache
    now = time.time()
    if _cached_payload is not None and (now - _cached_at) < DEX_RADAR_CACHE_SECONDS:
        return _cached_payload[:limit]

    cands: list[dict] = []

    # 1) Pull discovery feeds (paced)
    try:
        boosts_top = _get_json(
            _dex_url("/token-boosts/top/v1") if not USE_PROXY else _dex_url("/api/dex/token-boosts/top")
        )
        if isinstance(boosts_top, list):
            cands += _extract_candidates_from_boosts(boosts_top)
    except Exception:
        pass
    _sleep_jitter(DEX_FEED_PAUSE_SECONDS)

    try:
        boosts_latest = _get_json(
            _dex_url("/token-boosts/latest/v1") if not USE_PROXY else _dex_url("/api/dex/token-boosts/latest")
        )
        if isinstance(boosts_latest, list):
            cands += _extract_candidates_from_boosts(boosts_latest)
    except Exception:
        pass
    _sleep_jitter(DEX_FEED_PAUSE_SECONDS)

    try:
        profiles = _get_json(
            _dex_url("/token-profiles/latest/v1") if not USE_PROXY else _dex_url("/api/dex/token-profiles/latest")
        )
        if isinstance(profiles, list):
            cands += _extract_candidates_from_profiles(profiles)
    except Exception:
        pass
    _sleep_jitter(DEX_FEED_PAUSE_SECONDS)

    try:
        takeovers = _get_json(
            _dex_url("/community-takeovers/latest/v1") if not USE_PROXY else _dex_url("/api/dex/community-takeovers/latest")
        )
        if isinstance(takeovers, list):
            cands += _extract_candidates_from_takeovers(takeovers)
    except Exception:
        pass

    cands = _dedupe_by_address(cands)
    if not cands:
        _cached_payload = []
        _cached_at = now
        return []

    # 2) Enrich via tokens/v1 (best effort)
    addrs = [c["address"] for c in cands if c.get("address")]
    enriched_map = _enrich_tokens_v1(addrs)

    # 3) Score + rank
    ranked: list[dict] = []
    for c in cands:
        addr = c["address"]
        enriched = enriched_map.get(addr, {})
        score = _rocket_score(enriched)
        ranked.append({
            "chainId": CHAIN_ID,
            "address": addr,
            "source": c.get("source"),
            "score": round(score, 3),
            "enriched": enriched,
        })

    ranked.sort(key=lambda x: x.get("score", 0), reverse=True)
    ranked = ranked[: max(1, limit)]

    _cached_payload = ranked
    _cached_at = now
    return ranked
SOURCE_WEIGHT = {
    "takeover": 15,
    "boosts": 10,
    "profiles": 5
}
# -----------------------------------------------------
# Future-safe helper (NOT wired into logic yet)
# -----------------------------------------------------
def detect_hidden_strength(pair: dict) -> bool:
    """
    Placeholder for future hidden-strength detection.
    Currently unused. Safe to keep.
    """
    try:
        pc = pair.get("priceChange") or {}
        vol = pair.get("volume") or {}
        liq = pair.get("liquidity") or {}

        ch5 = float(pc.get("m5", 0))
        vol1h = float(vol.get("h1", 0))
        liq_usd = float(liq.get("usd", 0))

        return (
            ch5 < 5 and
            vol1h > 100_000 and
            liq_usd > 20_000
        )
    except Exception:
        return False
# src/services/dex_radar.py
# (FILE HEADER UNCHANGED — OMITTED FOR BREVITY)

# 🔧 ADD THIS HELPER NEAR THE BOTTOM (SAFE)
def detect_hidden_strength(pair: dict) -> bool:
    try:
        pc = pair.get("priceChange") or {}
        vol = pair.get("volume") or {}
        liq = pair.get("liquidity") or {}

        ch5 = float(pc.get("m5", 0))
        vol1h = float(vol.get("h1", 0))
        liq_usd = float(liq.get("usd", 0))

        return (
            ch5 < 5 and
            vol1h > 100_000 and
            liq_usd > 20_000
        )
    except Exception:
        return False
