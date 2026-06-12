"""
Momentum features.

PURITY CONTRACT — stateless pure function. See trend.py for full contract.

INPUT CONTRACT
--------------
All inputs are numpy float64 arrays, ascending date order.

Phase-1 features produced:
    return_1d     log return over 1 trading day
    return_3d
    return_5d
    return_10d
    return_20d
    return_60d
    rsi_14        Wilder RSI, 14-period (0–100)
    macd_histogram  MACD(12,26,9) histogram value
    roc_20        Rate of Change over 20 days (simple return)
"""

from __future__ import annotations

import numpy as np


def compute(close: np.ndarray) -> dict[str, float | None]:
    """
    Compute momentum features for the final bar in `close`.

    Args:
        close: numpy float64 array of adjusted close prices, ascending date order.

    Returns:
        Dict of feature_name → float | None.
    """
    result: dict[str, float | None] = {}

    for days, key in [
        (1,  "return_1d"),
        (3,  "return_3d"),
        (5,  "return_5d"),
        (10, "return_10d"),
        (20, "return_20d"),
        (60, "return_60d"),
    ]:
        result[key] = _log_return(close, days)

    result["rsi_14"]         = _rsi(close, period=14)
    result["macd_histogram"] = _macd_histogram(close, fast=12, slow=26, signal=9)
    result["roc_20"]         = _roc(close, period=20)

    # rsi_momentum_5d: RSI today minus RSI as of 5 bars ago
    if len(close) >= 20:
        rsi_5d_ago = _rsi(close[:-5], period=14)
        rsi_now = result["rsi_14"]
        result["rsi_momentum_5d"] = (
            rsi_now - rsi_5d_ago
            if rsi_now is not None and rsi_5d_ago is not None else None
        )
    else:
        result["rsi_momentum_5d"] = None

    return result


# ---------------------------------------------------------------------------
# Helpers — pure numpy, no Pandas
# ---------------------------------------------------------------------------

def _log_return(close: np.ndarray, days: int) -> float | None:
    n = len(close)
    if n <= days:
        return None
    prev = float(close[-(days + 1)])
    curr = float(close[-1])
    if prev <= 0:
        return None
    return float(np.log(curr / prev))


def _rsi(close: np.ndarray, period: int = 14) -> float | None:
    if len(close) < period + 1:
        return None
    delta = np.diff(close[-(period + 1):])   # length = period
    gains  = np.where(delta > 0, delta, 0.0)
    losses = np.where(delta < 0, -delta, 0.0)
    avg_gain = float(gains.mean())
    avg_loss = float(losses.mean())
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - 100.0 / (1.0 + rs))


def _ema(arr: np.ndarray, span: int) -> np.ndarray:
    """Exponential moving average via numpy (no Pandas)."""
    alpha = 2.0 / (span + 1)
    out = np.empty(len(arr), dtype=np.float64)
    out[0] = arr[0]
    for i in range(1, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def _macd_histogram(close: np.ndarray, fast: int, slow: int, signal: int) -> float | None:
    if len(close) < slow + signal:
        return None
    ema_fast  = _ema(close, fast)
    ema_slow  = _ema(close, slow)
    macd_line = ema_fast - ema_slow
    macd_sig  = _ema(macd_line, signal)
    hist      = float(macd_line[-1] - macd_sig[-1])
    return hist if not np.isnan(hist) else None


def _roc(close: np.ndarray, period: int) -> float | None:
    if len(close) <= period:
        return None
    prev = float(close[-(period + 1)])
    curr = float(close[-1])
    if prev == 0:
        return None
    return float((curr - prev) / prev)
