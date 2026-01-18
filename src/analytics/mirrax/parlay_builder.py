# parlay_builder.py
from datetime import datetime
from services.sports_api.nba import get_nba_games
from analytics.mirrax.fade_logic import analyze_public_fade
from analytics.mirrax.edge_logic import calculate_confidence

def build_parlay(max_legs=3):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    games = get_nba_games(today)
    parlay = []

    for idx, game in enumerate(games):
        confidence = calculate_confidence(game)
        fade_data = analyze_public_fade(game)

        if confidence >= 87:
            leg = {
                "leg": idx + 1,
                "pick": f"{game['teams']['home']['name']} ML",
                "confidence": confidence,
                "rationale": fade_data['reason'],
                "fade_flag": fade_data['should_fade'],
                "edge_flag": confidence >= 87
            }
            parlay.append(leg)

        if len(parlay) >= max_legs:
            break

    return parlay
