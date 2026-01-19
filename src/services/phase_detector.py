def detect_phase(ch5, ch15, ch60):
    if ch5 > 30 and ch60 < 80:
        return "IGNITION"
    if ch60 >= 80 and ch60 < 250:
        return "EXPANSION"
    if ch60 >= 250:
        return "EUPHORIA"
    return "BUILDING"
