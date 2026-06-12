"""
Trend features.

PURITY CONTRACT — this module must remain stateless.
compute() is a pure function: features = f(data). No DB reads,
no model calls, no global state, no I/O of any kind.

INPUT CONTRACT
--------------
All inputs are numpy arrays (float64, 1-D, ascending date order).
Callers are responsible for the conversion from pandas/polars/arrow
before calling compute().  This keeps feature modules framework-agnostic
and ready for Polars migration without touching computation logic.

Phase-1 features produced:
    distance_sma20    (close - SMA20) / SMA20
    distance_sma50
    distance_sma200
    above_sma20       1.0 if close > SMA20 else 0.0
    above_sma50
    above_sma200
"""

from __future__ import annotations

import numpy as np


def compute(close: np.ndarray) -> dict[str, float | None]:
    """
    Compute trend features for the final bar in `close`.

    Args:
        close: numpy float64 array of adjusted close prices, ascending date order.

    Returns:
        Dict of feature_name → float | None.
        None signals insufficient history for that feature (not an error).
    """
    n = len(close)
    if n == 0:
        return _empty()

    current = float(close[-1])
    result: dict[str, float | None] = {}

    for period, dist_key, above_key in [
        (20,  "distance_sma20",  "above_sma20"),
        (50,  "distance_sma50",  "above_sma50"),
        (200, "distance_sma200", "above_sma200"),
    ]:
        if n >= period:
            sma = float(close[-period:].mean())
            result[dist_key]  = (current - sma) / sma if sma != 0 else None
            result[above_key] = 1.0 if current > sma else 0.0
        else:
            result[dist_key]  = None
            result[above_key] = None

    # distance_sma20_momentum: change in SMA20 distance over 5 bars
    # Captures whether price is extending or contracting vs its 20d mean
    if n >= 25:
        sma20_now = float(close[-20:].mean())
        sma20_5d_ago = float(close[-25:-5].mean())
        dist_now = (current - sma20_now) / sma20_now if sma20_now != 0 else None
        dist_5d  = (float(close[-6]) - sma20_5d_ago) / sma20_5d_ago if sma20_5d_ago != 0 else None
        result["distance_sma20_momentum"] = (
            dist_now - dist_5d if dist_now is not None and dist_5d is not None else None
        )
    else:
        result["distance_sma20_momentum"] = None

    return result


def _empty() -> dict[str, None]:
    return {k: None for k in [
        "distance_sma20", "distance_sma50", "distance_sma200",
        "above_sma20", "above_sma50", "above_sma200",
        "distance_sma20_momentum",
    ]}
