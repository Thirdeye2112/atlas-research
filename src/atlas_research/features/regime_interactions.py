"""
regime_interactions.py — Regime-conditional interaction features for TRAIN_FEATURES_V3.

Computes per-row interaction features by multiplying a base feature against a
binary regime mask.  All inputs are already present in every parquet file (they
are V1 base features), so no schema changes or backfill are required.

Design
------
Each interaction = base_feature * regime_mask, where regime_mask is 0 or 1
derived from spy_above_sma200 or market_trend.

Regime masks used
-----------------
  above_200dma   spy_above_sma200          (1 when SPY > SMA200)
  below_200dma   1 - spy_above_sma200      (1 when SPY < SMA200)
  bull_regime    (market_trend == 1)       (1 in bull market)

Rationale (from REGIME_SENSITIVITY_REPORT.md)
----------------------------------------------
  omni_82_distance/above: IC = +0.026/+0.015 in bull/above_200dma,
                           negative in bear/below_200dma
  realized_vol_20/60:     IC = +0.053 in bear, +0.046 below_200dma
  return_1d/3d/5d:        IC more negative below_200dma — mean-reversion
                           stronger in downtrends
  rs_spy_20/60:           IC positive only in bull markets
  omni_82_slope:          IC = +0.002 above_200dma, -0.054 below_200dma
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Columns the parquet must supply to compute interactions.
# These are all V1 base features present in every parquet file.
BASE_COLS_NEEDED: frozenset[str] = frozenset({
    "spy_above_sma200",
    "market_trend",
    "omni_82_distance",
    "omni_82_above",
    "omni_82_slope",
    "realized_vol_20",
    "realized_vol_60",
    "return_1d",
    "return_3d",
    "return_5d",
    "rs_spy_20",
    "rs_spy_60",
})

# (output_name, base_col, regime_mask_key)
# regime_mask_key: "above_200dma" | "below_200dma" | "bull_regime"
INTERACTION_DEFS: list[tuple[str, str, str]] = [
    # OMNI works only when market is above 200DMA
    ("omni_82_distance_x_above_200dma", "omni_82_distance", "above_200dma"),
    ("omni_82_above_x_above_200dma",    "omni_82_above",    "above_200dma"),
    ("omni_82_slope_x_above_200dma",    "omni_82_slope",    "above_200dma"),
    # Volatility features work in downtrends
    ("realized_vol_20_x_below_200dma",  "realized_vol_20",  "below_200dma"),
    ("realized_vol_60_x_below_200dma",  "realized_vol_60",  "below_200dma"),
    # Mean-reversion signal stronger below 200DMA
    ("return_1d_x_below_200dma",        "return_1d",        "below_200dma"),
    ("return_3d_x_below_200dma",        "return_3d",        "below_200dma"),
    ("return_5d_x_below_200dma",        "return_5d",        "below_200dma"),
    # Relative strength useful only in bull markets
    ("rs_spy_20_x_bull",                "rs_spy_20",        "bull_regime"),
    ("rs_spy_60_x_bull",                "rs_spy_60",        "bull_regime"),
]

# All output column names produced by add_interactions()
INTERACTION_NAMES: frozenset[str] = frozenset(name for name, _, _ in INTERACTION_DEFS)


def _regime_mask(df: pd.DataFrame, key: str) -> pd.Series:
    if key == "above_200dma":
        col = df.get("spy_above_sma200")
        if col is None:
            return pd.Series(np.nan, index=df.index)
        return col.fillna(0.0).astype(float)

    if key == "below_200dma":
        col = df.get("spy_above_sma200")
        if col is None:
            return pd.Series(np.nan, index=df.index)
        return (1.0 - col.fillna(0.0)).astype(float)

    if key == "bull_regime":
        col = df.get("market_trend")
        if col is None:
            return pd.Series(np.nan, index=df.index)
        return (col == 1).astype(float)

    raise ValueError(f"Unknown regime_mask_key: {key!r}")


def add_interactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add all V3 interaction columns to df in-place (returns same object).

    Safe to call on any DataFrame that may or may not have all base columns.
    Missing base columns produce NaN interaction columns — LightGBM handles NaN
    natively, so this is no different from a missing V1 feature on old files.

    Idempotent: if columns already exist they are overwritten.
    """
    for output_name, base_col, regime_key in INTERACTION_DEFS:
        base = df.get(base_col)
        if base is None:
            df[output_name] = np.nan
            continue
        mask = _regime_mask(df, regime_key)
        df[output_name] = base.astype(float) * mask
    return df
