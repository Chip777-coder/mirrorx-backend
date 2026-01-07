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

This is *discovery* (universe building) — the key missing piece for 10k%+ movers.
"""

from __future__ import annotations
import os
import time
import requests
from typing import Any

DEX_BASE = "https://api.dexscreener.com"

# If you prefer the backend proxy, set DEX_RADAR_USE_PROXY=1
USE_PROXY = os.getenv("DEX_RADAR_USE_PROXY", "0") == "1"
PROXY_BASE = os.getenv("DEX_PROXY_BASE", "https://mirrorx-backend.onrender.com")

CHAIN_ID = "solana"


def _get_json(url: str, params: dict | None = None, timeout: int = 12) -> Any:
    r = requests.get(url, params=params or {}, timeout=timeout)
    r.raise_for_status()
    return r.json()


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


def _extract_candidates_from_boosts(items: list[dict]) -> list[dict]:
    out = []
    for it in items or []:
        chain = (it.get("chainId") or "").lower()
        if chain != CHAIN_ID:
            continue
        addr = it.get("tokenAddress") or it.get("address")
        if not addr:
            continue
        out.append({
            "chainId": CHAIN_ID,
            "address": addr,
            "source": "boosts",
            "raw": it,
        })
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
        out.append({
            "chainId": CHAIN_ID,
            "address": addr,
            "source": "profiles",
            "raw": it,
        })
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
        out.append({
            "chainId": CHAIN_ID,
            "address": addr,
            "source": "takeover",
            "raw": it,
        })
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

    # DexScreener supports comma-separated addresses; keep request size reasonable
    chunk_size = 25
    out: dict[str, dict] = {}

    for i in range(0, len(addresses), chunk_size):
        chunk = addresses[i:i + chunk_size]
        joined = ",".join(chunk)

        if USE_PROXY:
            url = _dex_url(f"/api/dex/tokens/v1/{CHAIN_ID}/{joined}")
        else:
            url = _dex_url(f"/tokens/v1/{CHAIN_ID}/{joined}")

        try:
            data = _get_json(url, timeout=14)
            # response shape varies; handle defensively
            if isinstance(data, dict):
                # some variants: {"pairs":[...]} or {"tokens":[...]} or raw list
                tokens = data.get("tokens") if isinstance(data.get("tokens"), list) else None
                if tokens:
                    for t in tokens:
                        addr = t.get("address") or t.get("tokenAddress")
                        if addr:
                            out[addr] = t
                elif isinstance(data.get("pairs"), list):
                    # if only pairs returned, map baseToken address
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
            continue

        time.sleep(0.15)

    return out


def _rocket_score(enriched: dict) -> float:
    """
    Educational scoring. NOT trade advice.
    Tries to rank tokens likely to be "real movers" vs junk:
      - liquidity strength
      - volume
      - short timeframe change if available
      - penalize tiny liquidity + huge % (common rug bait)
    """
    liq = 0.0
    vol24 = 0.0
    vol1h = 0.0
    ch1h = 0.0
    ch5m = 0.0

    # Many responses come from pair objects
    pair = enriched.get("pair") if isinstance(enriched.get("pair"), dict) else enriched
    if isinstance(pair, dict):
        liq = _safe_float((pair.get("liquidity") or {}).get("usd"), 0.0)
        vol24 = _safe_float((pair.get("volume") or {}).get("h24"), 0.0)
        vol1h = _safe_float((pair.get("volume") or {}).get("h1"), 0.0)
        pc = pair.get("priceChange") or {}
        ch1h = _safe_float(pc.get("h1"), 0.0)
        ch5m = _safe_float(pc.get("m5"), 0.0)

    score = 0.0
    score += min(liq / 100_000.0, 8.0) * 10.0            # up to 80 pts
    score += min(vol24 / 2_000_000.0, 8.0) * 8.0         # up to 64 pts
    score += min(vol1h / 500_000.0, 8.0) * 7.0           # up to 56 pts
    score += max(ch1h, 0.0) * 0.35                        # percent-driven
    score += max(ch5m, 0.0) * 0.65

    # Penalize extremely low liquidity with giant % (common bait)
    if liq < 10_000 and (ch1h > 200 or ch5m > 80):
        score *= 0.35

    return float(score)


def get_top_candidates(limit: int = 60) -> list[dict]:
    """
    Returns ranked candidate tokens:
      { address, chainId, score, source, enriched? }
    """
    # 1) Pull discovery feeds
    cands: list[dict] = []

    try:
        boosts_top = _get_json(_dex_url("/token-boosts/top/v1") if not USE_PROXY else _dex_url("/api/dex/token-boosts/top"))
        if isinstance(boosts_top, list):
            cands += _extract_candidates_from_boosts(boosts_top)
    except Exception:
        pass

    try:
        boosts_latest = _get_json(_dex_url("/token-boosts/latest/v1") if not USE_PROXY else _dex_url("/api/dex/token-boosts/latest"))
        if isinstance(boosts_latest, list):
            cands += _extract_candidates_from_boosts(boosts_latest)
    except Exception:
        pass

    try:
        profiles = _get_json(_dex_url("/token-profiles/latest/v1") if not USE_PROXY else _dex_url("/api/dex/token-profiles/latest"))
        if isinstance(profiles, list):
            cands += _extract_candidates_from_profiles(profiles)
    except Exception:
        pass

    try:
        takeovers = _get_json(_dex_url("/community-takeovers/latest/v1") if not USE_PROXY else _dex_url("/api/dex/community-takeovers/latest"))
        if isinstance(takeovers, list):
            cands += _extract_candidates_from_takeovers(takeovers)
    except Exception:
        pass

    cands = _dedupe_by_address(cands)
    if not cands:
        return []

    # 2) Enrich via tokens/v1 (best effort)
    addrs = [c["address"] for c in cands if c.get("address")]
    enriched_map = _enrich_tokens_v1(addrs)

    # 3) Score + rank
    ranked = []
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
    return ranked[: max(1, int(limit))]
