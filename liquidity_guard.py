from typing import Dict, Any

def run(min_pool_usd: float = 100000.0, max_tax_pct: float = 10.0, min_holders: int = 100, **kwargs) -> Dict[str, Any]:
    return {
        "min_pool_usd": min_pool_usd,
        "max_tax_pct": max_tax_pct,
        "min_holders": min_holders,
        "flagged": []
    }
