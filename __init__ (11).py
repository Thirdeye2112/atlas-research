"""
Volatility features.

PURITY CONTRACT — stateless pure function. See trend.py for full contract.

INPUT CONTRACT
--------------
All inputs are numpy float64 arrays, ascending date order.

Phase-1 features produced:
    atr_14           Average True Range, 14-period
    realized_vol_20  Annualised σ of 20-day log returns
    realized_vol_60  Annualised σ of 60-day log returns
"""

from __future__ import annotations

import numpy as np


def compute(
    close: np.ndarray,
    high:  np.ndarray,
    low:   np.ndarray,
) -> dict[str, float | None]:
    """
    Compute volatility features for the final bar.

    Args:
        close: numpy float64 array of adjusted close prices, ascending.
        high:  daily high prices, same length.
        low:   daily low prices, same length.

    Returns:
        Dict of feature_name → float | None.
    """
    return {
        "atr_14":          _atr(close, high, low, period=14),
        "realized_vol_20": _realized_vol(close, days=20),
        "realized_vol_60": _realized_vol(close, days=60),
    }


# ---------------------------------------------------------------------------
# Helpers — pure numpy
# ---------------------------------------------------------------------------

def _atr(
    close: np.ndarray,
    high:  np.ndarray,
    low:   np.ndarray,
    period: int = 14,
) -> float | None:
    n = len(close)
    if n < period + 1:
        return None
    prev_close = close[-(period + 1) : -1]   # length = period
    h = high[-period:]
    l = low[-period:]
    c = prev_close

    tr = np.maximum(
        h - l,
        np.maximum(np.abs(h - c), np.abs(l - c))
    )
    atr = float(tr.mean())
    return atr if not np.isnan(atr) else None


def _realized_vol(close: np.ndarray, days: int) -> float | None:
    if len(close) < days + 1:
        return None
    window = close[-(days + 1):]
    log_rets = np.log(window[1:] / window[:-1])
    std = float(np.std(log_rets, ddof=1))
    vol = std * np.sqrt(252)
    return vol if not np.isnan(vol) else None
