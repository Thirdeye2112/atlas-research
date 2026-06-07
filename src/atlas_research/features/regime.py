"""
Regime features — Phase 1.5.

PURITY CONTRACT — stateless pure function. See trend.py for full contract.

INPUT CONTRACT
--------------
All inputs are numpy float64 arrays, ascending date order.
SPY data only — no VIX, no breadth in Phase 1 (those come in Phase 2).

Phase-1 features produced (written per-ticker so every row in the ML
matrix has the market context for that date):
    spy_above_sma50    1.0 if SPY close > SMA50 else 0.0
    spy_above_sma200   1.0 if SPY close > SMA200 else 0.0
    spy_return_20d     SPY 20-day log return
    market_trend       +1.0 bull / 0.0 neutral / -1.0 bear
                       (bull = both SMAs above; bear = both below; else neutral)

Deferred to Phase 2:
    vix_level, vix_regime          — requires VIX data feed
    breadth_pct_above_sma200       — requires full universe computation
    adx_trend_strength             — SPY ADX
"""

from __future__ import annotations

import numpy as np


def compute(spy_close: np.ndarray) -> dict[str, float | None]:
    """
    Compute regime features from SPY adjusted close.

    Args:
        spy_close: SPY adjusted close array, ascending date order.
                   Needs at least 200 bars for full feature set.

    Returns:
        Dict of feature_name → float | None.
    """
    result: dict[str, float | None] = {
        "spy_above_sma50":  None,
        "spy_above_sma200": None,
        "spy_return_20d":   None,
        "market_trend":     None,
    }

    n = len(spy_close)
    if n < 2:
        return result

    current = float(spy_close[-1])
    above_50, above_200 = None, None

    if n >= 50:
        sma50 = float(spy_close[-50:].mean())
        above_50 = 1.0 if current > sma50 else 0.0
        result["spy_above_sma50"] = above_50

    if n >= 200:
        sma200 = float(spy_close[-200:].mean())
        above_200 = 1.0 if current > sma200 else 0.0
        result["spy_above_sma200"] = above_200

    if n > 20:
        prev = float(spy_close[-21])
        if prev > 0:
            result["spy_return_20d"] = float(np.log(current / prev))

    if above_50 is not None and above_200 is not None:
        if above_50 == 1.0 and above_200 == 1.0:
            result["market_trend"] = 1.0
        elif above_50 == 0.0 and above_200 == 0.0:
            result["market_trend"] = -1.0
        else:
            result["market_trend"] = 0.0

    return result


# ---------------------------------------------------------------------------
# Phase 2 stubs (uncomment when VIX / breadth data is available)
# ---------------------------------------------------------------------------
# def compute_vix_regime(vix: np.ndarray) -> dict[str, float | None]: ...
# def compute_breadth(closes: dict[str, np.ndarray]) -> dict[str, float | None]: ...
