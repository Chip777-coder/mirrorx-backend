from datetime import datetime

# ============================================================
# Safe / Guarded Sports API Imports (DO NOT HARD-CRASH APP)
# ============================================================

try:
    from src.services.sports_api.nba import get_nba_games
except Exception as e:
    get_nba_games = lambda *_args, **_kwargs: []
    print(f"[WARN] NBA API not available: {e}")

try:
    from src.services.sports_api.nfl import get_nfl_games
except Exception as e:
    get_nfl_games = lambda *_args, **_kwargs: []
    print(f"[WARN] NFL API not available: {e}")

try:
    from src.services.sports_api.mlb import get_mlb_games
except Exception as e:
    get_mlb_games = lambda *_args, **_kwargs: []
    print(f"[WARN] MLB API not available: {e}")

try:
    from src.services.sports_api.soccer import get_soccer_games
except Exception as e:
    get_soccer_games = lambda *_args, **_kwargs: []
    print(f"[WARN] Soccer API not available: {e}")

# ============================================================
# Internal MirroraX Analytics (these SHOULD exist)
# ============================================================

from analytics.mirrax.fade_logic import analyze_public_fade
from analytics.mirrax.edge_logic import calculate_confidence
from analytics.mirrax.history_analyzer import get_matchup_trend


# ============================================================
# Parlay Construction Logic
# ============================================================

def build_10_leg_parlay(games, max_legs=10):
    parlay = []

    for idx, game in enumerate(games):
        if len(parlay) >= max_legs:
            break

        confidence = calculate_confidence(game)
        fade_data = analyze_public_fade(game)

        home = game.get("teams", {}).get("home", {}).get("name", "Team A")
        away = game.get("teams", {}).get("away", {}).get("name", "Team B")

        trend = get_matchup_trend(home, away)

        leg = {
            "leg": idx + 1,
            "pick": f"{home} ML",
            "confidence": confidence,
            "rationale": f"{trend} | {fade_data.get('reason', 'n/a')}",
            "fade_flag": fade_data.get("should_fade", False),
            "edge_flag": confidence >= 87
        }

        parlay.append(leg)

    return parlay


# ============================================================
# Public Entry Point
# ============================================================

def generate_multiple_parlays():
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Collect all available games (each function safely returns [])
    all_games = (
        get_nba_games(today)
        + get_nfl_games(today)
        + get_mlb_games(today)
        + get_soccer_games(today)
    )

    if not all_games:
        print("[WARN] No sports data available for parlay generation.")
        return []

    parlays = []
    total_leg_pool = len(all_games)

    for i in range(10):
        start = (i * 10) % total_leg_pool
        batch = all_games[start:start + 15]
        parlay = build_10_leg_parlay(batch)
        parlays.append(parlay)

    return parlays
