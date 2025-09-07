from typing import List, Dict, Any

def run(addresses: List[str] = None, min_usd: float = 5000.0, lookback_min: int = 60, **kwargs) -> Dict[str, Any]:
    addresses = addresses or []
    return {
        "addresses": addresses,
        "lookback_min": lookback_min,
        "matches": [],
        "threshold_usd": min_usd,
    }
