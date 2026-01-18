# fade_logic.py
def analyze_public_fade(game):
    public_pct = game.get("statistics", {}).get("publicBetPct", 75)
    should_fade = public_pct >= 70
    reason = f"Heavy public backing ({public_pct}%)" if should_fade else "Neutral public sentiment"
    return {
        "should_fade": should_fade,
        "reason": reason
    }
