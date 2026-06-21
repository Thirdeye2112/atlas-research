"""
ta/vwap.py — Session-anchored VWAP computation for 5-minute bars.

Definition
----------
VWAP at bar T = Σ(typical_price_i × volume_i, i=session_open..T)
                / Σ(volume_i, i=session_open..T)

typical_price = (high + low + close) / 3   (standard HLC3 definition)

The VWAP is a running cumulative anchored to the first bar of each trading
session (9:30 AM ET).  It resets cleanly each day.  Only bars from
session-open through T (inclusive) contribute — strictly no lookahead.

Timestamps
----------
intraday_bars.ts is UTC.  Session dates are derived by converting ts to
America/New_York, which handles DST transitions automatically (pandas
tz_convert delegates to zoneinfo/dateutil, which follow the IANA tz DB).
A "session date" is the ET calendar date of the bar.

Derived features
----------------
  dist_from_vwap  (close - vwap) / vwap   — signed, fractional (not %)
  above_vwap      close > vwap             — boolean

Entry point
-----------
    from atlas_research.ta.vwap import compute_vwap_features

    # df: single ticker, sorted by ts ASC, market-hours-only bars
    result = compute_vwap_features(df)
    # result columns: ticker, ts, vwap, dist_from_vwap, above_vwap, session_date
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_vwap_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute session-anchored VWAP and derived features for a single ticker.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain: ticker, ts (UTC, tz-aware), high, low, close, volume.
        Must be sorted ascending by ts.  Single ticker only.
        Caller should filter to regular market hours (9:30–16:00 ET) first.

    Returns
    -------
    pd.DataFrame with columns:
        ticker, ts, vwap, dist_from_vwap, above_vwap, session_date

    Look-ahead guarantee
    --------------------
    groupby("session_date").cumsum() is computed on rows already sorted
    ascending by ts, so VWAP at bar T only uses tp×vol for bars 0..T
    of its session.  It is algebraically independent of bars after T.
    """
    if df.empty:
        return pd.DataFrame(
            columns=["ticker", "ts", "vwap", "dist_from_vwap", "above_vwap", "session_date"]
        )

    df = df.copy().sort_values("ts").reset_index(drop=True)

    # ET session date — tz_convert handles DST automatically
    df["session_date"] = df["ts"].dt.tz_convert("America/New_York").dt.date

    # Typical price: HLC / 3
    df["_tp"] = (df["high"] + df["low"] + df["close"]) / 3

    # Zero/negative volume treated as 0 (no contribution to VWAP)
    vol_clean = df["volume"].clip(lower=0).fillna(0)
    df["_tp_vol"] = df["_tp"] * vol_clean
    df["_vol_clean"] = vol_clean

    # Running cumulative sums within each ET session
    df["_cum_tp_vol"] = df.groupby("session_date")["_tp_vol"].cumsum()
    df["_cum_vol"] = df.groupby("session_date")["_vol_clean"].cumsum().clip(lower=1e-9)

    df["vwap"] = df["_cum_tp_vol"] / df["_cum_vol"]

    # Derived features
    vwap_safe = df["vwap"].replace(0, np.nan)
    df["dist_from_vwap"] = (df["close"] - df["vwap"]) / vwap_safe
    df["above_vwap"] = (df["close"] > df["vwap"]).astype(bool)

    keep = ["ticker", "ts", "vwap", "dist_from_vwap", "above_vwap", "session_date"]
    return df[keep].copy()
