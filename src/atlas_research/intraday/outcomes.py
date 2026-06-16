"""
Atlas Intraday 5-Minute Outcome Engine v1
==========================================
For each detected setup, computes forward outcomes at multiple horizons.
Uses ATR-based targets and stops. All look-ahead is intentional for labeling.

Entry point:
    outcomes_df = compute_outcomes(bars_df, setups_df, horizons, atr_targets, atr_stops)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

# Default horizons (bars = 5-minute candles)
DEFAULT_HORIZONS  = [1, 3, 6, 12, 24]   # 5, 15, 30, 60, 120 minutes

# ATR-based target and stop multiples
TARGET_MULTS = [0.5, 1.0, 1.5, 2.0]
STOP_MULTS   = [0.5, 1.0, 1.5]

# Primary horizon for the "canonical" target/stop labels
PRIMARY_HORIZON = 6      # 30 minutes
PRIMARY_TARGET  = 1.0    # +1 ATR
PRIMARY_STOP    = 1.0    # -1 ATR


def compute_outcomes(
    bars_df: pd.DataFrame,
    setups_df: pd.DataFrame,
    horizons: list[int] = DEFAULT_HORIZONS,
    primary_target_mult: float = PRIMARY_TARGET,
    primary_stop_mult: float   = PRIMARY_STOP,
) -> pd.DataFrame:
    """
    Compute forward outcomes for each row in setups_df.

    Args:
        bars_df:    Full OHLCV DataFrame for the ticker (sorted by ts asc).
                    Needs columns: ts, open, high, low, close, volume.
                    ATR column (atr14) optional -- recomputed if absent.
        setups_df:  Detected setups with setup_id, ts, direction, atr14 columns.
        horizons:   List of forward-bar counts to evaluate.
        primary_target_mult:  ATR multiple for primary target label.
        primary_stop_mult:    ATR multiple for primary stop label.

    Returns:
        DataFrame with one row per (setup_id, horizon_bars) containing outcome metrics.
    """
    if setups_df.empty or bars_df.empty:
        return pd.DataFrame()

    bars = bars_df.sort_values("ts").reset_index(drop=True)
    # Build a fast ts -> positional index map
    ts_to_idx: dict = {ts: i for i, ts in enumerate(bars["ts"])}

    rows = []
    for _, setup in setups_df.iterrows():
        sid       = setup["setup_id"]
        direction = setup.get("direction", "long")
        sign      = 1.0 if direction == "long" else -1.0
        entry_ts  = setup["ts"]
        entry_idx = ts_to_idx.get(entry_ts)
        if entry_idx is None:
            continue

        entry_price = bars.iloc[entry_idx]["close"]
        if entry_price <= 0 or np.isnan(entry_price):
            continue

        atr = setup.get("atr14") or 0.0
        if np.isnan(atr) or atr <= 0:
            # Fallback: estimate ATR from candle range
            lo = max(0, entry_idx - 14)
            atr = float((bars.iloc[lo:entry_idx + 1]["high"] - bars.iloc[lo:entry_idx + 1]["low"]).mean())
        if atr <= 0:
            atr = entry_price * 0.005  # 0.5% fallback

        t_target = entry_price + sign * primary_target_mult * atr
        t_stop   = entry_price - sign * primary_stop_mult   * atr

        for h in horizons:
            end_idx = min(entry_idx + h, len(bars) - 1)
            window  = bars.iloc[entry_idx + 1:end_idx + 1]

            if window.empty:
                rows.append(_empty_row(sid, h))
                continue

            final_close  = float(window.iloc[-1]["close"])
            future_ret   = sign * (final_close - entry_price) / entry_price * 100

            if direction == "long":
                mfe = float((window["high"].max()  - entry_price) / entry_price * 100)
                mae = float((entry_price - window["low"].min())   / entry_price * 100)
                target_bars = window[window["high"] >= t_target]
                stop_bars   = window[window["low"]  <= t_stop]
            else:
                mfe = float((entry_price - window["low"].min())   / entry_price * 100)
                mae = float((window["high"].max()  - entry_price) / entry_price * 100)
                target_bars = window[window["low"]  <= t_target]
                stop_bars   = window[window["high"] >= t_stop]

            hit_tgt = not target_bars.empty
            hit_stp = not stop_bars.empty

            # time_to_target/stop: bar offset from entry (1 = next candle)
            ttt = int(target_bars.index[0] - entry_idx) if hit_tgt else None
            tts = int(stop_bars.index[0]   - entry_idx) if hit_stp else None

            # If both hit: which came first?
            if hit_tgt and hit_stp and ttt is not None and tts is not None:
                if tts < ttt:
                    hit_tgt = False   # stop hit first
                    ttt     = None

            rows.append({
                "setup_id":      sid,
                "horizon_bars":  h,
                "future_return": round(future_ret, 4),
                "mfe":           round(mfe, 4),
                "mae":           round(mae, 4),
                "hit_target":    hit_tgt,
                "hit_stop":      hit_stp,
                "time_to_target": ttt,
                "time_to_stop":   tts,
            })

    return pd.DataFrame(rows)


def _empty_row(setup_id: str, horizon: int) -> dict:
    return {
        "setup_id":      setup_id,
        "horizon_bars":  horizon,
        "future_return": None,
        "mfe":           None,
        "mae":           None,
        "hit_target":    None,
        "hit_stop":      None,
        "time_to_target": None,
        "time_to_stop":   None,
    }
