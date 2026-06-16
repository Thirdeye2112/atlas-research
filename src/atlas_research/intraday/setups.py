"""
Atlas Intraday 5-Minute Setup Detector v1
==========================================
Detects technical-analysis setups from a feature-enriched DataFrame.
All conditions use only information available at the close of each candle.

Entry point:
    setups_df = detect_all_setups(features_df, ticker)
"""

from __future__ import annotations

import json
from typing import Callable

import numpy as np
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _bool(s: pd.Series) -> pd.Series:
    """Coerce to bool, filling NaN with False."""
    return s.fillna(False).astype(bool)


def _pack_inputs(row: pd.Series, keys: list[str]) -> str:
    """Serialize a dict of feature values to JSON string for storage."""
    d = {}
    for k in keys:
        v = row.get(k)
        if v is not None and v == v:
            try:
                d[k] = round(float(v), 4)
            except (TypeError, ValueError):
                d[k] = str(v)
    return json.dumps(d)


def _build_setup_rows(
    df: pd.DataFrame,
    mask: pd.Series,
    setup_type: str,
    direction: str,
    input_keys: list[str],
    ticker: str,
) -> pd.DataFrame:
    """
    Extract setup rows from df where mask is True.
    Returns a DataFrame with the standard setup columns.
    """
    mask = _bool(mask)
    hits = df[mask].copy()
    if hits.empty:
        return pd.DataFrame()

    # Deterministic setup_id
    hits["setup_id"] = (
        ticker + "_"
        + hits["ts"].astype(str).str.replace(r"[^0-9T]", "", regex=True).str[:15]
        + "_" + setup_type
    )
    hits["ticker"]     = ticker
    hits["setup_type"] = setup_type
    hits["direction"]  = direction
    hits["confidence_inputs"] = hits.apply(
        lambda r: _pack_inputs(r, input_keys), axis=1
    )

    keep = ["setup_id", "ticker", "ts", "setup_type", "direction",
            "confidence_inputs", "atr14", "close", "candle_num"]
    return hits[[c for c in keep if c in hits.columns]].copy()


# ─────────────────────────────────────────────────────────────────────────────
# Setup detectors  (each returns a boolean Series aligned with df.index)
# ─────────────────────────────────────────────────────────────────────────────

def _orb_bull(df: pd.DataFrame) -> pd.Series:
    """Opening range breakout -- long. First close above OR high after OR window."""
    return (
        _bool(df.get("orb_bull_signal")) &
        _bool(df.get("high_vol")) &
        _bool(df.get("is_green"))
    )


def _orb_bear(df: pd.DataFrame) -> pd.Series:
    """Opening range breakdown -- short."""
    return (
        _bool(df.get("orb_bear_signal")) &
        _bool(df.get("high_vol")) &
        _bool(df.get("is_red"))
    )


def _failed_breakout_bear(df: pd.DataFrame) -> pd.Series:
    """
    Failed ORB: price was above OR high in the prior candle, now back below.
    Short setup.
    """
    prev_above = df.get("above_or_high", pd.Series(False, index=df.index)).shift(1).fillna(False)
    return (
        _bool(prev_above) &
        ~_bool(df.get("above_or_high")) &
        ~_bool(df.get("in_or"))
    )


def _vwap_reclaim_bull(df: pd.DataFrame) -> pd.Series:
    """VWAP reclaim: price crosses above VWAP with volume confirmation."""
    return (
        _bool(df.get("vwap_cross_up")) &
        _bool(df.get("high_vol")) &
        ~_bool(df.get("in_or"))
    )


def _vwap_reject_bear(df: pd.DataFrame) -> pd.Series:
    """VWAP rejection: price crosses below VWAP with volume spike."""
    return (
        _bool(df.get("vwap_cross_down")) &
        _bool(df.get("high_vol")) &
        ~_bool(df.get("in_or"))
    )


def _rsi_reclaim_bull(df: pd.DataFrame) -> pd.Series:
    """RSI recovers from oversold (<30) back above 40, green candle."""
    return (
        _bool(df.get("rsi_reclaim_bull")) &
        _bool(df.get("is_green")) &
        _bool(df.get("above_vwap"))
    )


def _rsi_reclaim_bear(df: pd.DataFrame) -> pd.Series:
    """RSI retreats from overbought (>70) back below 60, red candle."""
    return (
        _bool(df.get("rsi_reclaim_bear")) &
        _bool(df.get("is_red")) &
        ~_bool(df.get("above_vwap"))
    )


def _momentum_cont_bull(df: pd.DataFrame) -> pd.Series:
    """Momentum continuation long: 2+ higher highs, above VWAP, EMA9 rising."""
    hh = df.get("hh_count", pd.Series(0, index=df.index)).fillna(0) >= 2
    return (
        hh &
        _bool(df.get("above_vwap")) &
        (df.get("ema9_slope", pd.Series(0, index=df.index)).fillna(0) > 0) &
        _bool(df.get("is_green"))
    )


def _momentum_cont_bear(df: pd.DataFrame) -> pd.Series:
    """Momentum continuation short: 2+ lower lows, below VWAP, EMA9 falling."""
    ll = df.get("ll_count", pd.Series(0, index=df.index)).fillna(0) >= 2
    return (
        ll &
        ~_bool(df.get("above_vwap")) &
        (df.get("ema9_slope", pd.Series(0, index=df.index)).fillna(0) < 0) &
        _bool(df.get("is_red"))
    )


def _exhaustion_rev_bull(df: pd.DataFrame) -> pd.Series:
    """
    Exhaustion reversal long: 3 consecutive red candles then hammer or bullish engulf.
    """
    consec_red_prev = df.get("consec_red", pd.Series(False, index=df.index)).shift(1).fillna(False)
    hammer_or_engulf = _bool(df.get("hammer")) | _bool(df.get("bullish_engulf"))
    return _bool(consec_red_prev) & hammer_or_engulf


def _exhaustion_rev_bear(df: pd.DataFrame) -> pd.Series:
    """Exhaustion reversal short: 3 consecutive green candles then shooting star or bearish engulf."""
    consec_green_prev = df.get("consec_green", pd.Series(False, index=df.index)).shift(1).fillna(False)
    star_or_engulf = _bool(df.get("shooting_star")) | _bool(df.get("bearish_engulf"))
    return _bool(consec_green_prev) & star_or_engulf


def _vol_squeeze_bull(df: pd.DataFrame) -> pd.Series:
    """Volatility squeeze release long: after compression, large green candle + volume."""
    compressed_prev = df.get("vol_compressed", pd.Series(False, index=df.index)).shift(1).fillna(False)
    large_candle = df.get("body_pct", pd.Series(0.0, index=df.index)).fillna(0) > 60
    return (
        _bool(compressed_prev) &
        large_candle &
        _bool(df.get("is_green")) &
        _bool(df.get("high_vol"))
    )


def _vol_squeeze_bear(df: pd.DataFrame) -> pd.Series:
    """Volatility squeeze release short: after compression, large red candle + volume."""
    compressed_prev = df.get("vol_compressed", pd.Series(False, index=df.index)).shift(1).fillna(False)
    large_candle = df.get("body_pct", pd.Series(0.0, index=df.index)).fillna(0) > 60
    return (
        _bool(compressed_prev) &
        large_candle &
        _bool(df.get("is_red")) &
        _bool(df.get("high_vol"))
    )


def _hvol_reversal_bull(df: pd.DataFrame) -> pd.Series:
    """High-volume reversal long: very high volume + hammer or bullish engulf."""
    return (
        _bool(df.get("very_hi_vol")) &
        (_bool(df.get("hammer")) | _bool(df.get("bullish_engulf")))
    )


def _hvol_reversal_bear(df: pd.DataFrame) -> pd.Series:
    """High-volume reversal short: very high volume + shooting star or bearish engulf."""
    return (
        _bool(df.get("very_hi_vol")) &
        (_bool(df.get("shooting_star")) | _bool(df.get("bearish_engulf")))
    )


def _ema_pullback_bull(df: pd.DataFrame) -> pd.Series:
    """
    Pullback to EMA9 in uptrend: EMA9 rising, price touches or dips below EMA9 then
    recovers (close above EMA9, low below EMA9 or close).
    """
    ema9 = df.get("ema9", pd.Series(np.nan, index=df.index))
    touched_ema = df["low"] <= ema9 * 1.001   # within 0.1% of EMA9
    return (
        _bool(df.get("ema9_above_ema20")) &
        (df.get("ema9_slope", pd.Series(0, index=df.index)).fillna(0) > 0) &
        touched_ema &
        _bool(df.get("price_above_ema9")) &
        _bool(df.get("is_green"))
    )


def _ema_pullback_bear(df: pd.DataFrame) -> pd.Series:
    """Pullback to EMA9 in downtrend: EMA9 falling, price rallies to EMA9 then rejects."""
    ema9 = df.get("ema9", pd.Series(np.nan, index=df.index))
    touched_ema = df["high"] >= ema9 * 0.999
    return (
        ~_bool(df.get("ema9_above_ema20")) &
        (df.get("ema9_slope", pd.Series(0, index=df.index)).fillna(0) < 0) &
        touched_ema &
        ~_bool(df.get("price_above_ema9")) &
        _bool(df.get("is_red"))
    )


def _first_red_rev_bull(df: pd.DataFrame) -> pd.Series:
    """
    First red candle after 3+ consecutive greens -- potential reversal long (dip buy).
    Looks for oversold pullback: red candle after green streak, still above VWAP.
    """
    consec_green_prev = df.get("consec_green", pd.Series(False, index=df.index)).shift(1).fillna(False)
    return (
        _bool(consec_green_prev) &
        _bool(df.get("is_red")) &
        _bool(df.get("above_vwap"))
    )


def _first_green_rev_bear(df: pd.DataFrame) -> pd.Series:
    """First green candle after 3+ consecutive reds -- potential dead cat bounce short."""
    consec_red_prev = df.get("consec_red", pd.Series(False, index=df.index)).shift(1).fillna(False)
    return (
        _bool(consec_red_prev) &
        _bool(df.get("is_green")) &
        ~_bool(df.get("above_vwap"))
    )


def _higher_low_cont_bull(df: pd.DataFrame) -> pd.Series:
    """Higher-low continuation long: new higher low while in uptrend."""
    return (
        _bool(df.get("higher_low")) &
        _bool(df.get("above_vwap")) &
        _bool(df.get("ema9_above_ema20")) &
        _bool(df.get("is_green"))
    )


def _lower_high_rej_bear(df: pd.DataFrame) -> pd.Series:
    """Lower-high rejection short: new lower high while in downtrend."""
    return (
        _bool(df.get("lower_high")) &
        ~_bool(df.get("above_vwap")) &
        ~_bool(df.get("ema9_above_ema20")) &
        _bool(df.get("is_red"))
    )


def _macd_bull_cross(df: pd.DataFrame) -> pd.Series:
    """MACD bullish cross above signal line."""
    return _bool(df.get("macd_bull_cross")) & _bool(df.get("above_vwap"))


def _macd_bear_cross(df: pd.DataFrame) -> pd.Series:
    """MACD bearish cross below signal line."""
    return _bool(df.get("macd_bear_cross")) & ~_bool(df.get("above_vwap"))


def _inside_bar_bull(df: pd.DataFrame) -> pd.Series:
    """
    Inside bar breakout long: candle N is inside bar, candle N+1 closes above N's high.
    Detected at candle N+1.
    """
    inside_prev = df.get("inside_bar", pd.Series(False, index=df.index)).shift(1).fillna(False)
    prev_high   = df["high"].shift(1)
    return (
        _bool(inside_prev) &
        (df["close"] > prev_high) &
        _bool(df.get("is_green"))
    )


def _inside_bar_bear(df: pd.DataFrame) -> pd.Series:
    """Inside bar breakdown short: candle N+1 closes below inside bar's low."""
    inside_prev = df.get("inside_bar", pd.Series(False, index=df.index)).shift(1).fillna(False)
    prev_low    = df["low"].shift(1)
    return (
        _bool(inside_prev) &
        (df["close"] < prev_low) &
        _bool(df.get("is_red"))
    )


def _bullish_engulf_setup(df: pd.DataFrame) -> pd.Series:
    """Bullish engulfing candle with volume confirmation."""
    return _bool(df.get("bullish_engulf")) & _bool(df.get("high_vol"))


def _bearish_engulf_setup(df: pd.DataFrame) -> pd.Series:
    """Bearish engulfing candle with volume confirmation."""
    return _bool(df.get("bearish_engulf")) & _bool(df.get("high_vol"))


# ─────────────────────────────────────────────────────────────────────────────
# Registry
# (name, detector_fn, direction)
# ─────────────────────────────────────────────────────────────────────────────

SETUP_REGISTRY: list[tuple[str, Callable, str, list[str]]] = [
    ("orb_bull",             _orb_bull,             "long",
     ["vol_ratio", "or_high", "or_range_pct", "atr14", "dist_vwap_pct"]),
    ("orb_bear",             _orb_bear,             "short",
     ["vol_ratio", "or_low", "or_range_pct", "atr14", "dist_vwap_pct"]),
    ("failed_breakout_bear", _failed_breakout_bear, "short",
     ["vol_ratio", "or_high", "dist_vwap_pct", "atr14"]),
    ("vwap_reclaim_bull",    _vwap_reclaim_bull,    "long",
     ["dist_vwap_pct", "vol_ratio", "rsi14", "ema9_slope"]),
    ("vwap_reject_bear",     _vwap_reject_bear,     "short",
     ["dist_vwap_pct", "vol_ratio", "rsi14", "ema9_slope"]),
    ("rsi_reclaim_bull",     _rsi_reclaim_bull,     "long",
     ["rsi14", "rsi_prev", "dist_vwap_pct", "vol_ratio"]),
    ("rsi_reclaim_bear",     _rsi_reclaim_bear,     "short",
     ["rsi14", "rsi_prev", "dist_vwap_pct", "vol_ratio"]),
    ("momentum_cont_bull",   _momentum_cont_bull,   "long",
     ["hh_count", "dist_vwap_pct", "ema9_slope", "vol_ratio"]),
    ("momentum_cont_bear",   _momentum_cont_bear,   "short",
     ["ll_count", "dist_vwap_pct", "ema9_slope", "vol_ratio"]),
    ("exhaustion_rev_bull",  _exhaustion_rev_bull,  "long",
     ["body_pct", "lower_wick", "vol_ratio", "rsi14"]),
    ("exhaustion_rev_bear",  _exhaustion_rev_bear,  "short",
     ["body_pct", "upper_wick", "vol_ratio", "rsi14"]),
    ("vol_squeeze_bull",     _vol_squeeze_bull,     "long",
     ["atr14", "atr14_ma", "vol_ratio", "body_pct", "dist_vwap_pct"]),
    ("vol_squeeze_bear",     _vol_squeeze_bear,     "short",
     ["atr14", "atr14_ma", "vol_ratio", "body_pct", "dist_vwap_pct"]),
    ("hvol_reversal_bull",   _hvol_reversal_bull,   "long",
     ["vol_ratio", "body_pct", "lower_wick", "rsi14"]),
    ("hvol_reversal_bear",   _hvol_reversal_bear,   "short",
     ["vol_ratio", "body_pct", "upper_wick", "rsi14"]),
    ("ema_pullback_bull",    _ema_pullback_bull,    "long",
     ["ema9", "ema9_slope", "dist_vwap_pct", "rsi14"]),
    ("ema_pullback_bear",    _ema_pullback_bear,    "short",
     ["ema9", "ema9_slope", "dist_vwap_pct", "rsi14"]),
    ("first_red_rev_bull",   _first_red_rev_bull,   "long",
     ["dist_vwap_pct", "rsi14", "vol_ratio"]),
    ("first_green_rev_bear", _first_green_rev_bear, "short",
     ["dist_vwap_pct", "rsi14", "vol_ratio"]),
    ("higher_low_cont_bull", _higher_low_cont_bull, "long",
     ["dist_vwap_pct", "ema9_slope", "rsi14", "vol_ratio"]),
    ("lower_high_rej_bear",  _lower_high_rej_bear,  "short",
     ["dist_vwap_pct", "ema9_slope", "rsi14", "vol_ratio"]),
    ("macd_cross_bull",      _macd_bull_cross,      "long",
     ["macd", "macd_signal_line", "macd_hist", "dist_vwap_pct"]),
    ("macd_cross_bear",      _macd_bear_cross,      "short",
     ["macd", "macd_signal_line", "macd_hist", "dist_vwap_pct"]),
    ("inside_bar_bull",      _inside_bar_bull,      "long",
     ["body_pct", "candle_rng", "atr14", "dist_vwap_pct"]),
    ("inside_bar_bear",      _inside_bar_bear,      "short",
     ["body_pct", "candle_rng", "atr14", "dist_vwap_pct"]),
    ("engulf_bull",          _bullish_engulf_setup, "long",
     ["body_pct", "vol_ratio", "rsi14", "dist_vwap_pct"]),
    ("engulf_bear",          _bearish_engulf_setup, "short",
     ["body_pct", "vol_ratio", "rsi14", "dist_vwap_pct"]),
]


# ─────────────────────────────────────────────────────────────────────────────
# Main entry
# ─────────────────────────────────────────────────────────────────────────────

def detect_all_setups(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """
    Run all setup detectors on a feature-enriched DataFrame for one ticker.
    Returns a DataFrame with one row per detected setup, standardised columns.
    """
    if df.empty:
        return pd.DataFrame()

    parts = []
    for setup_type, fn, direction, input_keys in SETUP_REGISTRY:
        try:
            mask = fn(df)
        except Exception:
            continue
        rows = _build_setup_rows(df, mask, setup_type, direction, input_keys, ticker)
        if not rows.empty:
            parts.append(rows)

    if not parts:
        return pd.DataFrame()

    out = pd.concat(parts, ignore_index=True)
    # Remove duplicate setup_id (can happen if same ts fires multiple detectors with same id)
    out = out.drop_duplicates(subset="setup_id")
    return out
