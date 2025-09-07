from typing import Dict, Any

def run(pump_thr_pct: float = 25.0, dump_thr_pct: float = -20.0, window_min: int = 15, **kwargs) -> Dict[str, Any]:
    return {
        "window_min": window_min,
        "pump_thr_pct": pump_thr_pct,
        "dump_thr_pct": dump_thr_pct,
        "signals": []
    }
