from datetime import datetime, timedelta

_ALERT_CACHE = {}

def should_alert(key: str, accel: float, window_minutes=20, min_delta=15):
    now = datetime.utcnow()
    prev = _ALERT_CACHE.get(key)

    if prev:
        last_time, last_accel = prev
        if now - last_time < timedelta(minutes=window_minutes):
            if accel < last_accel + min_delta:
                return False

    _ALERT_CACHE[key] = (now, accel)
    return True
