"""
setup_formation_v2_outcomes.py
=================================
Forward-outcome measurement -- the ONLY code in this measurement allowed to
look past the decision index T. Identical definition to v1's
setup_formation_outcomes.py, kept as a separate module so the two runs are
directly comparable (same forward_return / forward_direction / hit_target
semantics, same K values, same ATR_HIT_MULT/FORWARD_RETURN_FLAT_EPS).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from setup_formation_v2_common import K_VALUES, ATR_HIT_MULT, FORWARD_RETURN_FLAT_EPS


def compute_forward_outcomes(feat_df: pd.DataFrame) -> dict:
    close = feat_df["close"].to_numpy(dtype=float)
    high = feat_df["high"].to_numpy(dtype=float)
    low = feat_df["low"].to_numpy(dtype=float)
    n = len(close)

    out = {}
    high_s = pd.Series(high)
    low_s = pd.Series(low)
    close_s = pd.Series(close)

    for k in K_VALUES:
        fwd_close = close_s.shift(-k).to_numpy()
        with np.errstate(divide="ignore", invalid="ignore"):
            fwd_return = np.where(close > 0, (fwd_close - close) / close * 100.0, np.nan)

        fwd_direction = np.full(n, None, dtype=object)
        valid = ~np.isnan(fwd_return)
        fwd_direction[valid & (fwd_return > FORWARD_RETURN_FLAT_EPS)] = "up"
        fwd_direction[valid & (fwd_return < -FORWARD_RETURN_FLAT_EPS)] = "down"
        fwd_direction[valid & (np.abs(fwd_return) <= FORWARD_RETURN_FLAT_EPS)] = "flat"

        roll_max = high_s.rolling(k).max().to_numpy()
        fwd_high = np.full(n, np.nan)
        if n - k > 0:
            fwd_high[: n - k] = roll_max[k:]

        roll_min = low_s.rolling(k).min().to_numpy()
        fwd_low = np.full(n, np.nan)
        if n - k > 0:
            fwd_low[: n - k] = roll_min[k:]

        out[k] = {
            "forward_return": fwd_return,
            "forward_direction": fwd_direction,
            "fwd_high": fwd_high,
            "fwd_low": fwd_low,
        }

    return out


def hit_target_for(direction: np.ndarray, close: np.ndarray, atr14: np.ndarray,
                    fwd_high: np.ndarray, fwd_low: np.ndarray) -> np.ndarray:
    n = len(direction)
    out = np.full(n, None, dtype=object)

    target_up = close + ATR_HIT_MULT * atr14
    target_down = close - ATR_HIT_MULT * atr14

    is_long = direction == "long"
    is_short = direction == "short"

    hit_long = fwd_high >= target_up
    hit_short = fwd_low <= target_down

    valid_long = is_long & ~np.isnan(fwd_high) & ~np.isnan(atr14)
    valid_short = is_short & ~np.isnan(fwd_low) & ~np.isnan(atr14)

    out[valid_long] = hit_long[valid_long]
    out[valid_short] = hit_short[valid_short]
    return out
