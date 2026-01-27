# src/services/chart_render.py
"""
Chart Render
------------
Renders a simple price + volume chart PNG from Polygon aggs data.

Input:
  - aggs_desc: newest-first list of OHLCV dicts (Polygon "results")

Output:
  - PNG bytes
"""

from __future__ import annotations

import io
from typing import Any, Dict, List


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def render_price_volume_chart_png_bytes(
    ticker: str,
    aggs_desc: List[Dict[str, Any]],
    minutes: int = 5,
) -> bytes:
    """
    Minimal chart:
      - Top: closes line
      - Bottom: volume bars
    """
    if not aggs_desc or len(aggs_desc) < 10:
        return b""

    try:
        import matplotlib  # type: ignore
        matplotlib.use("Agg")  # headless
        import matplotlib.pyplot as plt  # type: ignore
    except Exception:
        return b""

    # Convert newest-first into oldest-first for plotting
    bars = list(reversed(aggs_desc))

    closes = [_safe_float(b.get("c"), 0.0) for b in bars]
    vols = [_safe_float(b.get("v"), 0.0) for b in bars]

    fig = plt.figure(figsize=(10, 5))

    ax1 = fig.add_subplot(2, 1, 1)
    ax1.plot(closes)
    ax1.set_title(f"{ticker} • {minutes}m (recent)")
    ax1.grid(True, alpha=0.2)

    ax2 = fig.add_subplot(2, 1, 2)
    ax2.bar(range(len(vols)), vols)
    ax2.grid(True, alpha=0.2)

    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=130)
    plt.close(fig)
    return buf.getvalue()
