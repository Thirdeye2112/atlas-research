"""
Atlas Intraday 5-Minute Feature Engine v1
==========================================
Computes technical-analysis features from 5-minute bars.
All features are strictly backward-looking -- no lookahead.

Entry point:
    df = compute_features(bars_df)

Input: DataFrame with columns [ticker, ts (UTC TIMESTAMPTZ), open, high, low, close, volume]
       sorted ascending by ts, single ticker, regular market hours only.
Output: same DataFrame with feature columns appended.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

# Opening range = first OR_BARS * 5 minutes (default: 30 min)
OR_BARS = 6


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------

def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta  = series.diff()
    gains  = delta.clip(lower=0)
    losses = (-delta).clip(lower=0)
    avg_g  = gains.ewm(span=period, adjust=False).mean()
    avg_l  = losses.ewm(span=period, adjust=False).mean()
    rs     = avg_g / avg_l.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"]  - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all intraday features for a single ticker's 5-min bars.
    df must be sorted by ts (UTC) ascending, single ticker, market hours only.
    Returns df with feature columns appended.
    """
    df = df.copy().sort_values("ts").reset_index(drop=True)

    # Local Eastern time for market-hour logic
    local_ts   = df["ts"].dt.tz_convert("America/New_York")
    df["_date"]    = local_ts.dt.date
    df["_hour"]    = local_ts.dt.hour
    df["_minute"]  = local_ts.dt.minute
    df["_tod_min"] = df["_hour"] * 60 + df["_minute"]   # minutes since midnight

    df["candle_num"] = df.groupby("_date").cumcount()

    # ── Time-of-day bucket ───────────────────────────────────────────────────
    bins   = [570, 600, 630, 660, 840, 900, 960]
    labels = ["open_30m", "930_10", "10_1030", "1030_14", "14_15", "15_16"]
    df["time_bucket"] = pd.cut(df["_tod_min"], bins=bins, labels=labels, right=False)

    # ── Gap from prior close ─────────────────────────────────────────────────
    # Build prior-day close map from last candle of each session
    last_idx      = df.groupby("_date")["candle_num"].transform("max")
    is_last_candle = df["candle_num"] == last_idx
    prior_close_map: dict = {}
    for _, row in df[is_last_candle].iterrows():
        prior_close_map[row["_date"]] = row["close"]

    def _prior_close(d):
        for i in range(1, 8):
            key = d - timedelta(days=i)
            if key in prior_close_map:
                return prior_close_map[key]
        return np.nan

    df["prior_close"] = df["_date"].apply(_prior_close)
    is_first = df["candle_num"] == 0
    raw_gap  = (df["open"] - df["prior_close"]) / df["prior_close"].replace(0, np.nan) * 100
    df["gap_pct"] = np.where(is_first, raw_gap, np.nan)
    df["gap_pct"] = df.groupby("_date")["gap_pct"].transform("ffill")

    # ── VWAP (daily, cumulative from 9:30) ───────────────────────────────────
    df["_tp"]     = (df["high"] + df["low"] + df["close"]) / 3
    df["_tp_vol"] = df["_tp"] * df["volume"].clip(lower=0)
    df["_cum_tv"] = df.groupby("_date")["_tp_vol"].cumsum()
    df["_cum_v"]  = df.groupby("_date")["volume"].cumsum().clip(lower=1)
    df["vwap"]    = df["_cum_tv"] / df["_cum_v"]
    df["dist_vwap_pct"] = (df["close"] - df["vwap"]) / df["vwap"].replace(0, np.nan) * 100
    df["above_vwap"]    = df["close"] > df["vwap"]
    # NOTE: shift(1, fill_value=False) -- NOT .shift(1).fillna(False). A bare
    # .shift(1) on a bool-dtype Series upcasts to object dtype to hold the
    # leading NaN; Python's `~` on that object-dtype series of real bool
    # objects then does bitwise-int negation (~True=-2, ~False=-1, BOTH
    # truthy), silently collapsing any "& ~shifted_prev" expression built on
    # it. fill_value=False sidesteps the upcast entirely (no NaN is ever
    # introduced), so the column stays genuine bool dtype and `~` does
    # correct logical negation. See reports/research/COMPUTE_FEATURES_AUDIT.md.
    df["above_vwap_prev"] = df["above_vwap"].shift(1, fill_value=False)
    df["vwap_cross_up"]   = df["above_vwap"] & ~df["above_vwap_prev"]
    df["vwap_cross_down"] = ~df["above_vwap"] & df["above_vwap_prev"]

    # ── Opening range (first OR_BARS candles) ────────────────────────────────
    or_data = (
        df[df["candle_num"] < OR_BARS]
        .groupby("_date")
        .agg(or_high=("high", "max"), or_low=("low", "min"))
        .reset_index()
    )
    df = df.merge(or_data, on="_date", how="left")
    df["or_range_pct"]  = (df["or_high"] - df["or_low"]) / df["or_low"].replace(0, np.nan) * 100
    df["above_or_high"] = df["close"] > df["or_high"]
    df["below_or_low"]  = df["close"] < df["or_low"]
    df["in_or"]         = df["candle_num"] < OR_BARS
    # Breakout: first candle to close above OR_high after OR period
    # Same shift(1, fill_value=False) fix as above_vwap_prev -- see note there.
    df["_above_or_prev"]   = df["above_or_high"].shift(1, fill_value=False)
    df["orb_bull_signal"]  = df["above_or_high"] & ~df["_above_or_prev"] & ~df["in_or"]
    df["_below_or_prev"]   = df["below_or_low"].shift(1, fill_value=False)
    df["orb_bear_signal"]  = df["below_or_low"] & ~df["_below_or_prev"] & ~df["in_or"]

    # ── EMAs ─────────────────────────────────────────────────────────────────
    df["ema9"]  = df["close"].ewm(span=9,  adjust=False).mean()
    df["ema20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["ema50"] = df["close"].ewm(span=50, adjust=False).mean()
    df["ema9_slope"]       = df["ema9"]  - df["ema9"].shift(3)
    df["ema20_slope"]      = df["ema20"] - df["ema20"].shift(3)
    df["price_above_ema9"] = df["close"] > df["ema9"]
    df["ema9_above_ema20"] = df["ema9"]  > df["ema20"]

    # ── RSI ──────────────────────────────────────────────────────────────────
    df["rsi14"]          = _rsi(df["close"], 14)
    df["rsi_prev"]       = df["rsi14"].shift(1)
    df["rsi_2ago"]       = df["rsi14"].shift(2)
    df["rsi_oversold"]   = df["rsi14"] < 30
    df["rsi_overbought"] = df["rsi14"] > 70
    # Reclaim: RSI was < 35 in last 2 bars, now >= 40
    df["rsi_reclaim_bull"] = (
        (df["rsi14"] >= 40) &
        (df["rsi_prev"] < 35)
    )
    df["rsi_reclaim_bear"] = (
        (df["rsi14"] <= 60) &
        (df["rsi_prev"] > 65)
    )

    # ── MACD ─────────────────────────────────────────────────────────────────
    ema12 = df["close"].ewm(span=12, adjust=False).mean()
    ema26 = df["close"].ewm(span=26, adjust=False).mean()
    df["macd"]             = ema12 - ema26
    df["macd_signal_line"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"]        = df["macd"] - df["macd_signal_line"]
    df["macd_bull_cross"]  = (
        (df["macd"] > df["macd_signal_line"]) &
        (df["macd"].shift(1) <= df["macd_signal_line"].shift(1))
    )
    df["macd_bear_cross"]  = (
        (df["macd"] < df["macd_signal_line"]) &
        (df["macd"].shift(1) >= df["macd_signal_line"].shift(1))
    )

    # ── ATR ──────────────────────────────────────────────────────────────────
    df["atr14"]    = _atr(df, 14)
    df["atr_pct"]  = df["atr14"] / df["close"].replace(0, np.nan) * 100
    df["atr14_ma"] = df["atr14"].rolling(20).mean()
    df["vol_compressed"] = df["atr14"] < df["atr14_ma"] * 0.75

    # ── Volume ────────────────────────────────────────────────────────────────
    df["vol_ma20"]    = df["volume"].rolling(20).mean().clip(lower=1)
    df["vol_ratio"]   = df["volume"] / df["vol_ma20"]
    df["high_vol"]    = df["vol_ratio"] > 1.5
    df["very_hi_vol"] = df["vol_ratio"] > 2.5

    # ── Candle structure ──────────────────────────────────────────────────────
    df["body"]        = (df["close"] - df["open"]).abs()
    df["candle_rng"]  = (df["high"] - df["low"]).clip(lower=1e-8)
    df["upper_wick"]  = df["high"] - df[["open", "close"]].max(axis=1)
    df["lower_wick"]  = df[["open", "close"]].min(axis=1) - df["low"]
    df["body_pct"]    = df["body"] / df["candle_rng"] * 100
    df["is_green"]    = df["close"] > df["open"]
    df["is_red"]      = df["close"] < df["open"]

    safe_body = df["body"].clip(lower=1e-8)
    df["hammer"] = (
        (df["lower_wick"] > 2 * safe_body) &
        (df["upper_wick"] < safe_body) &
        (df["body"] > 0)
    )
    df["shooting_star"] = (
        (df["upper_wick"] > 2 * safe_body) &
        (df["lower_wick"] < safe_body) &
        (df["body"] > 0)
    )
    df["bullish_engulf"] = (
        df["is_green"] &
        df["is_red"].shift(1).fillna(False) &
        (df["open"] <= df["close"].shift(1)) &
        (df["close"] >= df["open"].shift(1))
    )
    df["bearish_engulf"] = (
        df["is_red"] &
        df["is_green"].shift(1).fillna(False) &
        (df["open"] >= df["close"].shift(1)) &
        (df["close"] <= df["open"].shift(1))
    )
    df["inside_bar"] = (
        (df["high"] <= df["high"].shift(1)) &
        (df["low"]  >= df["low"].shift(1))
    )

    # ── Trend structure ───────────────────────────────────────────────────────
    df["higher_high"]  = (df["high"] > df["high"].shift(1)) & (df["high"].shift(1) > df["high"].shift(2))
    df["lower_low"]    = (df["low"]  < df["low"].shift(1))  & (df["low"].shift(1)  < df["low"].shift(2))
    df["higher_low"]   = (df["low"]  > df["low"].shift(1))  & (df["low"].shift(1)  > df["low"].shift(2))
    df["lower_high"]   = (df["high"] < df["high"].shift(1)) & (df["high"].shift(1) < df["high"].shift(2))
    df["hh_count"]     = df["higher_high"].rolling(3).sum()   # consecutive HHs in window
    df["ll_count"]     = df["lower_low"].rolling(3).sum()
    df["consec_green"] = (df["is_green"] & df["is_green"].shift(1) & df["is_green"].shift(2)).fillna(False)
    df["consec_red"]   = (df["is_red"]   & df["is_red"].shift(1)   & df["is_red"].shift(2)).fillna(False)

    # Drop internal columns
    internal = [c for c in df.columns if c.startswith("_")]
    df = df.drop(columns=internal, errors="ignore")

    return df
