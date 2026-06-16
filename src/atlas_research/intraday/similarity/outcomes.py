"""
Atlas Intraday Similarity Outcome Aggregation v1
==================================================
Aggregates multi-horizon outcomes from a set of matched historical candles.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def aggregate_outcomes(matched_df: pd.DataFrame, horizon: int = 6) -> dict:
    """
    Aggregate outcomes from matched historical candles.

    Parameters
    ----------
    matched_df : DataFrame
        Rows from intraday_candle_memory; may include 'distance' column.
    horizon : int
        Primary horizon in bars (default 6 = 30 min).

    Returns
    -------
    dict with keys:
        matched_total, valid_count, mean_return, median_return,
        hit_rate, pct_up_1pct, pct_down_1pct, std_return,
        mfe_12_mean, mae_12_mean, pct_hit_plus_1atr, pct_hit_minus_1atr,
        horizon_summary (all 5 horizons + eod)
    """
    col = f"future_return_{horizon}"
    valid = matched_df[matched_df[col].notna()] if col in matched_df.columns else matched_df.iloc[0:0]

    if len(valid) < 3:
        return {
            "matched_total": len(matched_df),
            "valid_count":   0,
            "mean_return":   None,
            "median_return": None,
            "hit_rate":      None,
        }

    returns = valid[col].astype(float).values

    def _stat(col_name, fn=np.nanmean):
        if col_name not in valid.columns:
            return None
        arr = valid[col_name].astype(float).values
        arr = arr[~np.isnan(arr)]
        return float(fn(arr)) if len(arr) > 0 else None

    def _pct_bool(col_name):
        if col_name not in valid.columns:
            return None
        arr = valid[col_name].astype(float).values
        valid_mask = ~np.isnan(arr)
        return float(arr[valid_mask].mean()) if valid_mask.sum() > 0 else None

    # Horizon summary
    horizon_summary: dict[str, dict] = {}
    for h in [1, 3, 6, 12, 24, "eod"]:
        c = f"future_return_{h}"
        if c not in valid.columns:
            continue
        arr = valid[c].astype(float).values
        arr = arr[~np.isnan(arr)]
        if len(arr) == 0:
            continue
        horizon_summary[str(h)] = {
            "n":          int(len(arr)),
            "mean":       float(arr.mean()),
            "hit_rate":   float((arr > 0).mean()),
            "pct_up_1":   float((arr > 1.0).mean()),
            "pct_dn_1":   float((arr < -1.0).mean()),
        }

    return {
        "matched_total":      int(len(matched_df)),
        "valid_count":        int(len(valid)),
        "mean_return":        float(returns.mean()),
        "median_return":      float(np.median(returns)),
        "hit_rate":           float((returns > 0).mean()),
        "pct_up_1pct":        float((returns > 1.0).mean()),
        "pct_down_1pct":      float((returns < -1.0).mean()),
        "std_return":         float(returns.std()),
        "mfe_12_mean":        _stat("mfe_12"),
        "mae_12_mean":        _stat("mae_12"),
        "pct_hit_plus_1atr":  _pct_bool("hit_plus_1_0_atr"),
        "pct_hit_minus_1atr": _pct_bool("hit_minus_1_0_atr"),
        "horizon_summary":    horizon_summary,
    }


def pick_best_k(backtest_results: list[dict]) -> dict:
    """
    From a list of {k, hitrate, mean_return} dicts, return the one
    with the best combined score = hitrate * abs(mean_return).
    """
    if not backtest_results:
        return {}
    scored = sorted(
        backtest_results,
        key=lambda d: d.get("hit_rate", 0.5) * abs(d.get("mean_return", 0.0)),
        reverse=True,
    )
    return scored[0]
