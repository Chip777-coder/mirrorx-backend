# edge_logic.py
def calculate_confidence(game):
    streak = game.get("teams", {}).get("home", {}).get("form", {}).get("streak", 0)
    base = 85
    if streak >= 3:
        base += 5
    return base
