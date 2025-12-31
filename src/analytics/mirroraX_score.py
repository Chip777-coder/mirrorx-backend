def calculate_score(price_change, vol, liquidity, sentiment):
    w = {"price":0.3,"volume":0.3,"liquidity":0.2,"sentiment":0.2}
    norm = lambda v,limit: min(v/limit,1)
    return round(
        w["price"]*norm(abs(price_change),50) +
        w["volume"]*norm(vol,1e7) +
        w["liquidity"]*norm(liquidity,5e6) +
        w["sentiment"]*norm(sentiment,500), 2
    )*100
