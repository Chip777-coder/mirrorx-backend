def breakout_probability(confidence, phase, liq_delta):
    base = confidence * 0.6
    if phase == "IGNITION":
        base += 10
    if liq_delta > 0:
        base += 5
    return min(int(base), 100)
