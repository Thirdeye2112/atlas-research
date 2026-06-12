"""
Relative strength features.

PURITY CONTRACT — stateless pure function. See trend.py for full contract.

INPUT CONTRACT
--------------
All inputs are numpy float64 arrays, same length, ascending date order.
Caller is responsible for aligning ticker and benchmark arrays to the same
trading-day calendar before passing.

Phase-1 features produced:
    rs_spy_20    ticker log return (20d) minus SPY log return (20d)
    rs_spy_60
    rs_spy_120
"""

from __future__ import annotations

import numpy as np


def compute(
    close:     np.ndarray,
    spy_close: np.ndarray,
) -> dict[str, float | None]:
    """
    Compute relative strength vs SPY at 20, 60, and 120-day horizons.

    Args:
        close:     Ticker adjusted close, ascending date order.
        spy_close: SPY adjusted close, same length after alignment.

    Returns:
        Dict of feature_name → float | None.
    """
    result: dict[str, float | None] = {
        "rs_spy_20":          None,
        "rs_spy_60":          None,
        "rs_spy_120":         None,
        "rs_spy_20_momentum": None,
    }

    min_len = min(len(close), len(spy_close))
    if min_len < 2:
        return result

    # Use the trailing min_len elements from each array
    tk = close[-min_len:]
    sp = spy_close[-min_len:]

    for days, key in [(20, "rs_spy_20"), (60, "rs_spy_60"), (120, "rs_spy_120")]:
        if min_len > days:
            tk_ret = _log_ret(tk, days)
            sp_ret = _log_ret(sp, days)
            if tk_ret is not None and sp_ret is not None:
                result[key] = tk_ret - sp_ret

    # rs_spy_20_momentum: change in 20d RS over the past 5 bars
    # Positive = stock is accelerating vs SPY; negative = decelerating
    if min_len >= 27:
        tk_ret_5d = _log_ret_offset(tk, 20, 5)
        sp_ret_5d = _log_ret_offset(sp, 20, 5)
        rs_today = result["rs_spy_20"]
        if rs_today is not None and tk_ret_5d is not None and sp_ret_5d is not None:
            rs_5d_ago = tk_ret_5d - sp_ret_5d
            result["rs_spy_20_momentum"] = rs_today - rs_5d_ago

    return result


def _log_ret(arr: np.ndarray, days: int) -> float | None:
    n = len(arr)
    if n <= days:
        return None
    prev = float(arr[-(days + 1)])
    curr = float(arr[-1])
    if prev <= 0:
        return None
    return float(np.log(curr / prev))


def _log_ret_offset(arr: np.ndarray, days: int, back: int) -> float | None:
    """Log return of 'days' trading days, measured 'back' bars into the past.
    E.g., back=5, days=20 gives the 20d return as of 5 bars ago."""
    n = len(arr)
    if n < days + back + 1:
        return None
    curr = float(arr[-(1 + back)])
    prev = float(arr[-(1 + back + days)])
    if prev <= 0:
        return None
    return float(np.log(curr / prev))
