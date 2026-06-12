"""
Volume features.

PURITY CONTRACT — stateless pure function. See trend.py for full contract.

INPUT CONTRACT
--------------
All inputs are numpy float64 arrays, ascending date order.

Phase-1 features produced:
    volume_ratio_20   today volume / 20-day average volume (excl. today)
    dollar_volume_20  20-day average of (close * volume)
"""

from __future__ import annotations

import numpy as np


def compute(
    close:  np.ndarray,
    volume: np.ndarray,
) -> dict[str, float | None]:
    """
    Compute volume features for the final bar.

    Args:
        close:  numpy float64 adjusted close prices, ascending.
        volume: numpy float64 share volumes, same length.

    Returns:
        Dict of feature_name → float | None.
    """
    result: dict[str, float | None] = {
        "volume_ratio_20":  None,
        "dollar_volume_20": None,
        "volume_trend_5d":  None,
    }

    n = len(close)
    if n < 21 or len(volume) < 21:
        return result

    # Relative volume: today vs 20-day average (excluding today)
    vol_avg_20 = float(volume[-21:-1].mean())
    today_vol  = float(volume[-1])
    if vol_avg_20 > 0:
        result["volume_ratio_20"] = today_vol / vol_avg_20

    # Dollar volume: 20-day average of (close * volume)
    dv = close[-20:] * volume[-20:]
    dv_mean = float(dv.mean())
    result["dollar_volume_20"] = dv_mean if not np.isnan(dv_mean) else None

    # volume_trend_5d: recent 5-bar avg vol vs prior 5-bar avg vol
    # Values > 1 mean increasing volume (participation accelerating)
    if len(volume) >= 10:
        vol_recent = float(volume[-5:].mean())
        vol_prior  = float(volume[-10:-5].mean())
        if vol_prior > 0:
            result["volume_trend_5d"] = vol_recent / vol_prior

    return result
