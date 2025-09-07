from typing import Dict, Any

def run(min_usd: float = 20000.0, window_min: int = 30, chain: str = "sol", **kwargs) -> Dict[str, Any]:
    return {
        "chain": chain,
        "window_min": window_min,
        "min_usd": min_usd,
        "leaders": []
    }
