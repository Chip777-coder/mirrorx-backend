def compute_confidence(ch5, ch1, liq_delta, vol1h, source_weight):
    score = 0
    score += min(ch5, 100) * 0.25
    score += min(ch1, 300) * 0.2
    score += min(liq_delta / 10_000, 10) * 5
    score += min(vol1h / 250_000, 10) * 5
    score += source_weight
    return min(int(score), 100)
