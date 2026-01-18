from datetime import datetime
from services.sports_api.nba import get_nba_games
from services.sports_api.nfl import get_nfl_games
from services.sports_api.mlb import get_mlb_games
from services.sports_api.soccer import get_soccer_games
from analytics.mirrax.fade_logic import analyze_public_fade
from analytics.mirrax.edge_logic import calculate_confidence
from analytics.mirrax.history_analyzer import get_matchup_trend

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
            "rationale": f"{trend} | {fade_data['reason']}",
            "fade_flag": fade_data['should_fade'],
            "edge_flag": confidence >= 87
        }
        parlay.append(leg)

    return parlay

def generate_multiple_parlays():
    today = datetime.utcnow().strftime("%Y-%m-%d")

    all_games = (
        get_nba_games(today)
        + get_nfl_games(today)
        + get_mlb_games(today)
        + get_soccer_games(today)
    )

    parlays = []
    total_leg_pool = len(all_games)

    for i in range(10):
        start = (i * 10) % total_leg_pool
        batch = all_games[start:start+15]
        parlay = build_10_leg_parlay(batch)
        parlays.append(parlay)

    return parlays
