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
        "rs_spy_20":  None,
        "rs_spy_60":  None,
        "rs_spy_120": None,
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
