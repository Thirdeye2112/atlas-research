"""
Atlas Intraday Similarity Feature Vector v1
============================================
Converts a candle + daily-context row into a normalized 16-dim vector
suitable for KNN similarity search.

All values are clipped to [0, 1].  Neutral/missing values are mapped to 0.5
so that missing data does not artificially attract or repel matches.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# -----------------------------------------------------------------------
# Feature names (must match order of build_feature_vector output)
# -----------------------------------------------------------------------
FEATURE_NAMES: list[str] = [
    # Candle shape (5)
    "f_body",          # body_pct/100
    "f_upper_wick",    # upper_wick / candle_range
    "f_lower_wick",    # lower_wick / candle_range
    "f_direction",     # 1.0=green, 0.0=red
    "f_range",         # atr_pct clipped [0,3] -> [0,1]
    # Volume (2)
    "f_rel_vol",       # vol_ratio clipped [0,4] -> [0,1]
    "f_vol_zscore",    # vol_zscore clipped [-4,4] -> [0,1]
    # Trend (3)
    "f_vwap_dist",     # dist_vwap_pct clipped [-3,3] -> [0,1]
    "f_or_pos",        # 0.0=below OR, 0.5=in OR, 1.0=above OR
    "f_ema9_slope",    # ema9_slope/atr14 clipped [-2,2] -> [0,1]
    # Momentum (2)
    "f_rsi",           # rsi14/100
    "f_macd",          # macd_hist/atr14 clipped [-2,2] -> [0,1]
    # Time (1)
    "f_time",          # tod_min/390 (minutes since 9:30)
    # Daily context (3)
    "f_conviction",    # VERY_LOW=0.1, LOW=0.25, MOD=0.5, HIGH=0.75, VH=1.0
    "f_regime",        # bear=0.0, neutral=0.5, bull=1.0
    "f_vix",           # extreme=0.0, high=0.25, moderate=0.5, low=1.0
]

N_FEATURES: int = len(FEATURE_NAMES)

# Weights for weighted Euclidean distance in KNN
DEFAULT_WEIGHTS: np.ndarray = np.array([
    1.0, 1.0, 1.0, 1.0, 0.5,   # candle shape
    1.5, 1.5,                   # volume
    1.0, 1.0, 0.75,             # trend
    0.75, 0.5,                  # momentum
    2.0,                        # time-of-day (intraday behavior varies by session)
    2.0, 2.0, 1.5,              # daily context
], dtype=np.float64)

assert len(DEFAULT_WEIGHTS) == N_FEATURES, "Weight count must match FEATURE_NAMES"


# -----------------------------------------------------------------------
# Conviction/regime/VIX ordinal maps
# -----------------------------------------------------------------------
_CONVICTION_MAP = {
    "VERY_HIGH": 1.00,
    "HIGH":      0.75,
    "MODERATE":  0.50,
    "LOW":       0.25,
    "VERY_LOW":  0.10,
}
_REGIME_MAP = {
    "bull":    1.0,
    "bullish": 1.0,
    "neutral": 0.5,
    "bearish": 0.0,
    "bear":    0.0,
}
_VIX_MAP = {
    "low":     1.00,
    "LOW":     1.00,
    "moderate":0.50,
    "MODERATE":0.50,
    "high":    0.25,
    "HIGH":    0.25,
    "extreme": 0.00,
    "EXTREME": 0.00,
}


def _safe(v, default: float = 0.5) -> float:
    """Return v as float, or default if None/NaN."""
    if v is None:
        return default
    try:
        f = float(v)
        return default if (f != f) else f  # NaN check
    except (TypeError, ValueError):
        return default


def _clip01(v: float) -> float:
    return max(0.0, min(1.0, v))


def build_feature_vector(row: "pd.Series | dict") -> np.ndarray:
    """
    Build a 16-dim normalized feature vector from a candle row.

    row must contain (from compute_features output + daily context join):
        body_pct, upper_wick_ratio, lower_wick_ratio, is_green,
        atr_pct, vol_ratio, vol_zscore, dist_vwap_pct,
        above_or_high, below_or_low, ema9_slope, atr14,
        rsi14, macd_hist, tod_min,
        daily_conviction, daily_regime, daily_vix
    Missing fields are handled with safe defaults.
    """
    def g(key, default=0.5):
        v = row[key] if hasattr(row, "__getitem__") else getattr(row, key, None)
        return _safe(v, default)

    # Candle shape
    body_pct  = g("body_pct", 50.0) / 100.0          # 0-100 -> 0-1
    upper_w   = _clip01(g("upper_wick_ratio", 0.0))
    lower_w   = _clip01(g("lower_wick_ratio", 0.0))
    direction = 1.0 if g("is_green", 0.5) > 0.5 else 0.0
    atr_pct   = _clip01(g("atr_pct", 0.3) / 3.0)

    # Volume
    rel_vol  = _clip01(g("vol_ratio", 1.0) / 4.0)
    vol_zsc  = _clip01((g("vol_zscore", 0.0) + 4.0) / 8.0)

    # Trend
    vwap_d   = _clip01((g("dist_vwap_pct", 0.0) + 3.0) / 6.0)

    above_or  = g("above_or_high", 0) > 0.5
    below_or  = g("below_or_low",  0) > 0.5
    or_pos    = 1.0 if above_or else (0.0 if below_or else 0.5)

    atr14    = max(g("atr14", 0.1), 1e-8)
    slope    = g("ema9_slope", 0.0)
    ema9_sl  = _clip01((slope / atr14 + 2.0) / 4.0)

    # Momentum
    rsi_f    = _clip01(g("rsi14", 50.0) / 100.0)
    macd_h   = g("macd_hist", 0.0)
    macd_f   = _clip01((macd_h / atr14 + 2.0) / 4.0)

    # Time (minutes since 9:30 AM = tod_min - 570, total session = 390 min)
    tod_raw  = g("tod_min", 570 + 195)  # default midday
    time_f   = _clip01((tod_raw - 570) / 390.0)

    # Daily context
    conv_str = row.get("daily_conviction") if hasattr(row, "get") else getattr(row, "daily_conviction", None)
    conv_f   = _CONVICTION_MAP.get(str(conv_str).upper() if conv_str else "", 0.5)

    reg_str  = row.get("daily_regime") if hasattr(row, "get") else getattr(row, "daily_regime", None)
    reg_f    = _REGIME_MAP.get(str(reg_str).lower() if reg_str else "", 0.5)

    vix_str  = row.get("daily_vix") if hasattr(row, "get") else getattr(row, "daily_vix", None)
    vix_f    = _VIX_MAP.get(str(vix_str) if vix_str else "", 0.5)

    return np.array([
        _clip01(body_pct),
        upper_w,
        lower_w,
        direction,
        atr_pct,
        rel_vol,
        vol_zsc,
        vwap_d,
        or_pos,
        ema9_sl,
        rsi_f,
        macd_f,
        time_f,
        conv_f,
        reg_f,
        vix_f,
    ], dtype=np.float64)


def build_vectors_batch(df: pd.DataFrame) -> np.ndarray:
    """
    Vectorized batch version for building feature vectors from a DataFrame.
    Expects compute_features() output + daily context columns merged in.
    Returns (N, 16) float64 array.
    """
    n = len(df)
    out = np.zeros((n, N_FEATURES), dtype=np.float64)

    def col(name, default=0.5):
        if name not in df.columns:
            return np.full(n, default, dtype=np.float64)
        v = pd.to_numeric(df[name], errors="coerce").fillna(default).values.astype(np.float64)
        return v

    def clip01(arr):
        return np.clip(arr, 0.0, 1.0)

    # Candle shape
    out[:, 0] = clip01(col("body_pct", 50.0) / 100.0)
    out[:, 1] = clip01(col("upper_wick_ratio", 0.0))
    out[:, 2] = clip01(col("lower_wick_ratio", 0.0))
    is_green = col("is_green_bin", 0.5)
    if "is_green" in df.columns:
        is_green = df["is_green"].astype(float).fillna(0.5).values
    out[:, 3] = np.where(is_green > 0.5, 1.0, 0.0)
    out[:, 4] = clip01(col("atr_pct", 0.3) / 3.0)

    # Volume
    out[:, 5] = clip01(col("vol_ratio", 1.0) / 4.0)
    out[:, 6] = clip01((col("vol_zscore", 0.0) + 4.0) / 8.0)

    # Trend
    out[:, 7] = clip01((col("dist_vwap_pct", 0.0) + 3.0) / 6.0)

    above_or = col("above_or_high", 0.0)
    below_or = col("below_or_low", 0.0)
    or_pos   = np.where(above_or > 0.5, 1.0, np.where(below_or > 0.5, 0.0, 0.5))
    out[:, 8] = or_pos

    atr14    = np.maximum(col("atr14", 0.1), 1e-8)
    slope    = col("ema9_slope", 0.0)
    out[:, 9] = clip01((slope / atr14 + 2.0) / 4.0)

    # Momentum
    out[:, 10] = clip01(col("rsi14", 50.0) / 100.0)
    macd_h     = col("macd_hist", 0.0)
    out[:, 11] = clip01((macd_h / atr14 + 2.0) / 4.0)

    # Time
    tod = col("tod_min", 570.0 + 195.0)
    out[:, 12] = clip01((tod - 570.0) / 390.0)

    # Daily context
    def map_series(col_name, mapping, default=0.5):
        if col_name not in df.columns:
            return np.full(n, default, dtype=np.float64)
        return df[col_name].map(mapping).fillna(default).values.astype(np.float64)

    out[:, 13] = map_series("daily_conviction", _CONVICTION_MAP)
    out[:, 14] = map_series("daily_regime",     _REGIME_MAP)
    out[:, 15] = map_series("daily_vix",        _VIX_MAP)

    return out
