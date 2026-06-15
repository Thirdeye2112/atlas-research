"""
atlas_research.backtest.conditions
=====================================
Canonical condition evaluators.

Every evaluator signature:
    fn(df: pd.DataFrame, params: dict) -> pd.Series[bool]

The returned Series is aligned to df.index (True = signal fired on that bar).
No DB access inside evaluators — calendar/sector data is loaded once into
module-level caches on first use.

Condition type names
--------------------
Price/return:
    consecutive_down  consecutive_up  gap_down  gap_up
    near_52w_low  near_52w_high  breakout_52w_high
    above_level  below_sma  above_sma

Volume:
    high_volume  volume_climax_down  volume_climax_up

Volatility:
    nr7

RSI:
    oversold_rsi  overbought_rsi

Candlestick (delegates to patterns.candlestick):
    candle   (params: {"pattern": "<name>"})

Calendar:
    end_of_month  turn_of_month  day_of_week
    fomc_proximity  opex_week  triple_witching_week

OMNI / Oscar proxy:
    omni_cross_up  omni_cross_down  omni_green_nd  omni_red_nd
    oscar_cross_up  oscar_cross_down  oscar_above_50
    ema_lows_cross_up  ema_lows_cross_down  ema_lows_support
    ema_lows_above_nd  ema_lows_green_slope
    hma_cross_up  hma_cross_down

Sector:
    sector_leading_nd  xly_vs_xlp  iwm_vs_spy

Aliases (probability engine names → canonical names):
    down_streak → consecutive_down   (param n → n_days)
    up_streak   → consecutive_up     (param n → n_days)
"""

from __future__ import annotations

import datetime
from typing import Callable

import numpy as np
import pandas as pd

from atlas_research.features import omni_proxy


# ── RSI (vectorised Wilder smoothing) ────────────────────────────────────────

def _rsi_series(closes: np.ndarray, period: int = 14) -> np.ndarray:
    n = len(closes)
    out = np.full(n, np.nan)
    if n <= period:
        return out
    deltas = np.diff(closes)
    gains  = np.maximum(deltas, 0.0)
    losses = np.maximum(-deltas, 0.0)
    avg_g  = float(np.mean(gains[:period]))
    avg_l  = float(np.mean(losses[:period]))
    for i in range(period, n - 1):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
        out[i + 1] = 100.0 if avg_l == 0 else 100.0 - 100.0 / (1.0 + avg_g / avg_l)
    return out


# ── OMNI helper: indices → boolean Series ────────────────────────────────────

def _idx_to_mask(indices: list[int], size: int, index) -> pd.Series:
    arr = np.zeros(size, dtype=bool)
    for i in indices:
        if 0 <= i < size:
            arr[i] = True
    return pd.Series(arr, index=index)


# ── Price / return conditions ─────────────────────────────────────────────────

def eval_consecutive_down(df: pd.DataFrame, params: dict) -> pd.Series:
    n = int(params.get("n_days", params.get("n", 3)))
    down = (df["close"] < df["close"].shift(1)).fillna(False).astype(int)
    return (down.rolling(n).sum() == n).fillna(False)


def eval_consecutive_up(df: pd.DataFrame, params: dict) -> pd.Series:
    n = int(params.get("n_days", params.get("n", 3)))
    up = (df["close"] > df["close"].shift(1)).fillna(False).astype(int)
    return (up.rolling(n).sum() == n).fillna(False)


def eval_gap_down(df: pd.DataFrame, params: dict) -> pd.Series:
    # accepts both "min_gap_pct" (conditional engine) and "threshold_pct" (probability engine)
    pct = float(params.get("min_gap_pct", params.get("threshold_pct", 2.0)))
    gap = (df["open"] / df["close"].shift(1) - 1) * 100
    return (gap < -pct).fillna(False)


def eval_gap_up(df: pd.DataFrame, params: dict) -> pd.Series:
    pct = float(params.get("min_gap_pct", params.get("threshold_pct", 2.0)))
    gap = (df["open"] / df["close"].shift(1) - 1) * 100
    return (gap > pct).fillna(False)


def eval_near_52w_low(df: pd.DataFrame, params: dict) -> pd.Series:
    within = float(params.get("within_pct", 5.0)) / 100.0
    lookback = min(252, len(df))
    low252 = df["low"].rolling(lookback).min()
    pct_above = (df["close"] - low252) / low252.replace(0, np.nan)
    return (pct_above <= within).fillna(False)


def eval_near_52w_high(df: pd.DataFrame, params: dict) -> pd.Series:
    within = float(params.get("within_pct", 5.0)) / 100.0
    lookback = min(252, len(df))
    high252 = df["high"].rolling(lookback).max()
    pct_below = (high252 - df["close"]) / high252.replace(0, np.nan)
    return (pct_below <= within).fillna(False)


def eval_breakout_52w_high(df: pd.DataFrame, params: dict) -> pd.Series:
    lookback = min(252, len(df))
    prior_high = df["high"].shift(1).rolling(lookback).max()
    return (df["close"] > prior_high).fillna(False)


def eval_above_level(df: pd.DataFrame, params: dict) -> pd.Series:
    threshold = float(params.get("threshold", 30.0))
    return (df["close"] > threshold).fillna(False)


def eval_below_sma(df: pd.DataFrame, params: dict) -> pd.Series:
    period = int(params.get("period", 200))
    sma = df["close"].rolling(period).mean()
    return (df["close"] < sma).fillna(False)


def eval_above_sma(df: pd.DataFrame, params: dict) -> pd.Series:
    period = int(params.get("period", 50))
    sma = df["close"].rolling(period).mean()
    return (df["close"] > sma).fillna(False)


# ── Volume conditions ─────────────────────────────────────────────────────────

def eval_high_volume(df: pd.DataFrame, params: dict) -> pd.Series:
    mult    = float(params.get("multiplier", 2.0))
    lookback = int(params.get("lookback", 20))
    avg_vol = df["volume"].rolling(lookback).mean()
    return (df["volume"] >= mult * avg_vol).fillna(False)


def eval_volume_climax_down(df: pd.DataFrame, params: dict) -> pd.Series:
    mult    = float(params.get("multiplier", 2.0))
    lookback = int(params.get("lookback", 20))
    avg_vol = df["volume"].rolling(lookback).mean()
    return (
        (df["volume"] >= mult * avg_vol) & (df["close"] < df["open"])
    ).fillna(False)


def eval_volume_climax_up(df: pd.DataFrame, params: dict) -> pd.Series:
    mult    = float(params.get("multiplier", 2.0))
    lookback = int(params.get("lookback", 20))
    avg_vol = df["volume"].rolling(lookback).mean()
    return (
        (df["volume"] >= mult * avg_vol) & (df["close"] > df["open"])
    ).fillna(False)


# ── Volatility conditions ─────────────────────────────────────────────────────

def eval_nr7(df: pd.DataFrame, params: dict) -> pd.Series:
    lookback = int(params.get("lookback", 7))
    rng = df["high"] - df["low"]
    min_prior = rng.shift(1).rolling(lookback - 1).min()
    return (rng < min_prior).fillna(False)


# ── RSI conditions ────────────────────────────────────────────────────────────

def eval_oversold_rsi(df: pd.DataFrame, params: dict) -> pd.Series:
    threshold = float(params.get("threshold", 30.0))
    period    = int(params.get("period", 14))
    rsi = _rsi_series(df["close"].to_numpy(dtype=np.float64), period)
    return pd.Series(rsi < threshold, index=df.index).fillna(False)


def eval_overbought_rsi(df: pd.DataFrame, params: dict) -> pd.Series:
    threshold = float(params.get("threshold", 70.0))
    period    = int(params.get("period", 14))
    rsi = _rsi_series(df["close"].to_numpy(dtype=np.float64), period)
    return pd.Series(rsi > threshold, index=df.index).fillna(False)


# ── Candlestick condition ─────────────────────────────────────────────────────

def eval_candle(df: pd.DataFrame, params: dict) -> pd.Series:
    from atlas_research.patterns.candlestick import detect_patterns

    _ALIAS = {
        "bullish_engulfing": "engulfing_bull",
        "bearish_engulfing": "engulfing_bear",
        "hammer":            "hammer",
        "shooting_star":     "shooting_star",
        "doji":              "doji",
    }
    pattern = params.get("pattern", "")
    internal = _ALIAS.get(pattern, pattern)

    if internal == "inside_day" or internal == "_inside_day":
        return (
            (df["high"] < df["high"].shift(1)) & (df["low"] > df["low"].shift(1))
        ).fillna(False)
    if internal == "outside_day" or internal == "_outside_day":
        return (
            (df["high"] > df["high"].shift(1)) & (df["low"] < df["low"].shift(1))
        ).fillna(False)

    signals = detect_patterns(df)
    if internal not in signals:
        raise ValueError(
            f"Unknown candle pattern {pattern!r}. "
            f"Available: {sorted(_ALIAS) + sorted(signals)}"
        )
    return signals[internal].fillna(False)


# ── Calendar conditions ───────────────────────────────────────────────────────

_calendar_cache: dict[str, set[str]] = {}


def _calendar_dates(event_type: str, proximity_days: int = 0) -> set[str]:
    from atlas_research.db.connection import get_raw_engine
    key = f"{event_type}:{proximity_days}"
    if key in _calendar_cache:
        return _calendar_cache[key]
    try:
        with get_raw_engine().connect() as conn:
            from sqlalchemy import text
            rows = conn.execute(
                text("SELECT date::text FROM market_calendar WHERE event_type = :et ORDER BY date"),
                {"et": event_type},
            ).fetchall()
    except Exception:
        _calendar_cache[key] = set()
        return set()
    if proximity_days == 0:
        result: set[str] = {r[0] for r in rows}
    else:
        result = set()
        for r in rows:
            d = datetime.date.fromisoformat(r[0])
            for off in range(-proximity_days, proximity_days + 1):
                result.add((d + datetime.timedelta(days=off)).isoformat())
    _calendar_cache[key] = result
    return result


def eval_end_of_month(df: pd.DataFrame, params: dict) -> pd.Series:
    n = int(params.get("n_days", 3))
    from collections import defaultdict
    if hasattr(df.index, "strftime"):
        dates = df.index.strftime("%Y-%m-%d").tolist()
    else:
        dates = [str(d)[:10] for d in df.index]
    month_groups: dict[str, list[int]] = defaultdict(list)
    for i, d in enumerate(dates):
        month_groups[d[:7]].append(i)
    hits = set()
    for indices in month_groups.values():
        for idx in indices[-n:]:
            hits.add(idx)
    mask = np.zeros(len(df), dtype=bool)
    for i in hits:
        mask[i] = True
    return pd.Series(mask, index=df.index)


def eval_turn_of_month(df: pd.DataFrame, params: dict) -> pd.Series:
    n = int(params.get("n_days", 3))
    from collections import defaultdict
    if hasattr(df.index, "strftime"):
        dates = df.index.strftime("%Y-%m-%d").tolist()
    else:
        dates = [str(d)[:10] for d in df.index]
    month_groups: dict[str, list[int]] = defaultdict(list)
    for i, d in enumerate(dates):
        month_groups[d[:7]].append(i)
    hits = set()
    for indices in month_groups.values():
        for idx in indices[:n]:
            hits.add(idx)
    mask = np.zeros(len(df), dtype=bool)
    for i in hits:
        mask[i] = True
    return pd.Series(mask, index=df.index)


def eval_day_of_week(df: pd.DataFrame, params: dict) -> pd.Series:
    weekday = int(params.get("weekday", 0))
    if hasattr(df.index, "weekday"):
        return pd.Series(df.index.weekday == weekday, index=df.index)
    mask = np.array([
        datetime.date.fromisoformat(str(d)[:10]).weekday() == weekday
        for d in df.index
    ], dtype=bool)
    return pd.Series(mask, index=df.index)


def eval_fomc_proximity(df: pd.DataFrame, params: dict) -> pd.Series:
    proximity = int(params.get("proximity_days", 0))
    fomc = _calendar_dates("fomc_meeting", proximity_days=proximity)
    if hasattr(df.index, "strftime"):
        dates = df.index.strftime("%Y-%m-%d")
    else:
        dates = [str(d)[:10] for d in df.index]
    return pd.Series([d in fomc for d in dates], index=df.index, dtype=bool)


def eval_opex_week(df: pd.DataFrame, params: dict) -> pd.Series:
    opex_dates = _calendar_dates("options_expiry")
    opex_weeks: set[str] = set()
    for ds in opex_dates:
        d = datetime.date.fromisoformat(ds)
        opex_weeks.add((d - datetime.timedelta(days=d.weekday())).isoformat())
    if hasattr(df.index, "date"):
        mondays = [(d - datetime.timedelta(days=d.weekday())).isoformat() for d in df.index.date]
    else:
        mondays = [
            (datetime.date.fromisoformat(str(d)[:10]) - datetime.timedelta(
                days=datetime.date.fromisoformat(str(d)[:10]).weekday()
            )).isoformat()
            for d in df.index
        ]
    return pd.Series([m in opex_weeks for m in mondays], index=df.index, dtype=bool)


def eval_triple_witching_week(df: pd.DataFrame, params: dict) -> pd.Series:
    tw_dates = _calendar_dates("triple_witching")
    tw_weeks: set[str] = set()
    for ds in tw_dates:
        d = datetime.date.fromisoformat(ds)
        tw_weeks.add((d - datetime.timedelta(days=d.weekday())).isoformat())
    if hasattr(df.index, "date"):
        mondays = [(d - datetime.timedelta(days=d.weekday())).isoformat() for d in df.index.date]
    else:
        mondays = [
            (datetime.date.fromisoformat(str(d)[:10]) - datetime.timedelta(
                days=datetime.date.fromisoformat(str(d)[:10]).weekday()
            )).isoformat()
            for d in df.index
        ]
    return pd.Series([m in tw_weeks for m in mondays], index=df.index, dtype=bool)


# ── Sector conditions ─────────────────────────────────────────────────────────

_sector_rank_cache:  dict[str, dict[str, int]]   = {}
_sector_rs20d_cache: dict[str, dict[str, float]] = {}
_iwm_spy_cache:      dict[tuple, set[str]]       = {}


def _sector_ranks(sector_ticker: str) -> dict[str, int]:
    if sector_ticker in _sector_rank_cache:
        return _sector_rank_cache[sector_ticker]
    from atlas_research.db.connection import get_raw_engine
    from sqlalchemy import text
    try:
        with get_raw_engine().connect() as conn:
            rows = conn.execute(text("""
                SELECT date::text, rank_among_sectors
                FROM sector_relative_strength
                WHERE sector_ticker = :t AND rank_among_sectors IS NOT NULL
                ORDER BY date
            """), {"t": sector_ticker}).fetchall()
        result = {r[0]: int(r[1]) for r in rows}
    except Exception:
        result = {}
    _sector_rank_cache[sector_ticker] = result
    return result


def _sector_rs20d(sector_ticker: str) -> dict[str, float]:
    if sector_ticker in _sector_rs20d_cache:
        return _sector_rs20d_cache[sector_ticker]
    from atlas_research.db.connection import get_raw_engine
    from sqlalchemy import text
    try:
        with get_raw_engine().connect() as conn:
            rows = conn.execute(text("""
                SELECT date::text, rs_vs_spy_20d
                FROM sector_relative_strength
                WHERE sector_ticker = :t AND rs_vs_spy_20d IS NOT NULL
                ORDER BY date
            """), {"t": sector_ticker}).fetchall()
        result = {r[0]: float(r[1]) for r in rows}
    except Exception:
        result = {}
    _sector_rs20d_cache[sector_ticker] = result
    return result


def eval_sector_leading_nd(df: pd.DataFrame, params: dict) -> pd.Series:
    sector_ticker   = str(params.get("sector_ticker", "XLV"))
    rank_threshold  = int(params.get("rank_threshold", 2))
    n_days          = int(params.get("n_days", 20))
    rank_by_date    = _sector_ranks(sector_ticker)
    if not rank_by_date:
        return pd.Series(False, index=df.index)
    if hasattr(df.index, "strftime"):
        dates = df.index.strftime("%Y-%m-%d").tolist()
    else:
        dates = [str(d)[:10] for d in df.index]
    rank_series = pd.Series(
        [rank_by_date.get(d, 99) for d in dates], index=df.index, dtype=float
    )
    # n_days consecutive days all <= rank_threshold
    at_threshold = (rank_series <= rank_threshold).astype(int)
    return (at_threshold.rolling(n_days).sum() == n_days).fillna(False)


def eval_xly_vs_xlp(df: pd.DataFrame, params: dict) -> pd.Series:
    xly = _sector_rs20d("XLY")
    xlp = _sector_rs20d("XLP")
    if hasattr(df.index, "strftime"):
        dates = df.index.strftime("%Y-%m-%d").tolist()
    else:
        dates = [str(d)[:10] for d in df.index]
    return pd.Series(
        [d in xly and d in xlp and xly[d] > xlp[d] for d in dates],
        index=df.index, dtype=bool,
    )


def eval_iwm_vs_spy(df: pd.DataFrame, params: dict) -> pd.Series:
    outperform = float(params.get("outperform_pct", 2.0)) / 100.0
    n_days     = int(params.get("n_days", 10))
    cache_key  = (outperform, n_days)
    if cache_key not in _iwm_spy_cache:
        from atlas_research.db.connection import get_raw_engine
        from sqlalchemy import text
        try:
            with get_raw_engine().connect() as conn:
                iwm_rows = conn.execute(text(
                    "SELECT date::text, close FROM raw_bars WHERE ticker='IWM' ORDER BY date"
                )).fetchall()
                spy_rows = conn.execute(text(
                    "SELECT date::text, close FROM raw_bars WHERE ticker='SPY' ORDER BY date"
                )).fetchall()
        except Exception:
            _iwm_spy_cache[cache_key] = set()
            return pd.Series(False, index=df.index)
        iwm = {r[0]: float(r[1]) for r in iwm_rows}
        spy = {r[0]: float(r[1]) for r in spy_rows}
        dates_sorted = sorted(set(iwm) & set(spy))
        iwm_arr = np.array([iwm[d] for d in dates_sorted], dtype=np.float64)
        spy_arr = np.array([spy[d] for d in dates_sorted], dtype=np.float64)
        outperforming: set[str] = set()
        for j in range(n_days, len(dates_sorted)):
            iwm_ret = (iwm_arr[j] - iwm_arr[j - n_days]) / iwm_arr[j - n_days]
            spy_ret = (spy_arr[j] - spy_arr[j - n_days]) / spy_arr[j - n_days]
            if iwm_ret - spy_ret >= outperform:
                outperforming.add(dates_sorted[j])
        _iwm_spy_cache[cache_key] = outperforming
    valid = _iwm_spy_cache[cache_key]
    if hasattr(df.index, "strftime"):
        dates = df.index.strftime("%Y-%m-%d").tolist()
    else:
        dates = [str(d)[:10] for d in df.index]
    return pd.Series([d in valid for d in dates], index=df.index, dtype=bool)


# ── OMNI / Oscar / HMA conditions ────────────────────────────────────────────

def _omni_mask(indices: list[int], df: pd.DataFrame) -> pd.Series:
    return _idx_to_mask(indices, len(df), df.index)


def eval_omni_cross_up(df: pd.DataFrame, params: dict) -> pd.Series:
    period = int(params.get("period", 87))
    close  = df["close"].to_numpy(dtype=np.float64)
    return _omni_mask(omni_proxy.omni_cross_up_indices(close, period), df)


def eval_omni_cross_down(df: pd.DataFrame, params: dict) -> pd.Series:
    period = int(params.get("period", 87))
    close  = df["close"].to_numpy(dtype=np.float64)
    return _omni_mask(omni_proxy.omni_cross_down_indices(close, period), df)


def eval_omni_green_nd(df: pd.DataFrame, params: dict) -> pd.Series:
    period = int(params.get("period", 87))
    n_days = int(params.get("n_days", 3))
    close  = df["close"].to_numpy(dtype=np.float64)
    return _omni_mask(omni_proxy.omni_above_nd_indices(close, period, n_days), df)


def eval_omni_red_nd(df: pd.DataFrame, params: dict) -> pd.Series:
    period = int(params.get("period", 87))
    n_days = int(params.get("n_days", 3))
    close  = df["close"].to_numpy(dtype=np.float64)
    return _omni_mask(omni_proxy.omni_below_nd_indices(close, period, n_days), df)


def eval_oscar_cross_up(df: pd.DataFrame, params: dict) -> pd.Series:
    period = int(params.get("period", 87))
    close  = df["close"].to_numpy(dtype=np.float64)
    high   = df["high"].to_numpy(dtype=np.float64)
    low    = df["low"].to_numpy(dtype=np.float64)
    return _omni_mask(omni_proxy.oscar_cross_up_indices(high, low, close, period), df)


def eval_oscar_cross_down(df: pd.DataFrame, params: dict) -> pd.Series:
    period = int(params.get("period", 87))
    close  = df["close"].to_numpy(dtype=np.float64)
    high   = df["high"].to_numpy(dtype=np.float64)
    low    = df["low"].to_numpy(dtype=np.float64)
    return _omni_mask(omni_proxy.oscar_cross_down_indices(high, low, close, period), df)


def eval_oscar_above_50(df: pd.DataFrame, params: dict) -> pd.Series:
    period = int(params.get("period", 87))
    close  = df["close"].to_numpy(dtype=np.float64)
    high   = df["high"].to_numpy(dtype=np.float64)
    low    = df["low"].to_numpy(dtype=np.float64)
    return _omni_mask(omni_proxy.oscar_above_50_indices(high, low, close, period), df)


def eval_ema_lows_cross_up(df: pd.DataFrame, params: dict) -> pd.Series:
    period = int(params.get("period", 87))
    close  = df["close"].to_numpy(dtype=np.float64)
    low    = df["low"].to_numpy(dtype=np.float64)
    return _omni_mask(omni_proxy.ema_lows_cross_up_indices(low, close, period), df)


def eval_ema_lows_cross_down(df: pd.DataFrame, params: dict) -> pd.Series:
    period = int(params.get("period", 87))
    close  = df["close"].to_numpy(dtype=np.float64)
    low    = df["low"].to_numpy(dtype=np.float64)
    return _omni_mask(omni_proxy.ema_lows_cross_down_indices(low, close, period), df)


def eval_ema_lows_support(df: pd.DataFrame, params: dict) -> pd.Series:
    period    = int(params.get("period", 87))
    touch_pct = float(params.get("touch_pct", 0.005))
    close     = df["close"].to_numpy(dtype=np.float64)
    low       = df["low"].to_numpy(dtype=np.float64)
    open_     = df["open"].to_numpy(dtype=np.float64)
    return _omni_mask(omni_proxy.ema_lows_support_indices(low, close, open_, period, touch_pct), df)


def eval_ema_lows_above_nd(df: pd.DataFrame, params: dict) -> pd.Series:
    period = int(params.get("period", 82))
    n_days = int(params.get("n_days", 3))
    close  = df["close"].to_numpy(dtype=np.float64)
    low    = df["low"].to_numpy(dtype=np.float64)
    return _omni_mask(omni_proxy.ema_lows_above_nd_indices(low, close, period, n_days), df)


def eval_ema_lows_green_slope(df: pd.DataFrame, params: dict) -> pd.Series:
    period     = int(params.get("period", 82))
    slope_bars = int(params.get("slope_bars", 5))
    close      = df["close"].to_numpy(dtype=np.float64)
    low        = df["low"].to_numpy(dtype=np.float64)
    return _omni_mask(omni_proxy.ema_lows_green_slope_indices(low, close, period, slope_bars), df)


def eval_hma_cross_up(df: pd.DataFrame, params: dict) -> pd.Series:
    period = int(params.get("period", 87))
    close  = df["close"].to_numpy(dtype=np.float64)
    return _omni_mask(omni_proxy.hma_cross_up_indices(close, period), df)


def eval_hma_cross_down(df: pd.DataFrame, params: dict) -> pd.Series:
    period = int(params.get("period", 87))
    close  = df["close"].to_numpy(dtype=np.float64)
    return _omni_mask(omni_proxy.hma_cross_down_indices(close, period), df)


# ── Dispatch registry ─────────────────────────────────────────────────────────

REGISTRY: dict[str, Callable[[pd.DataFrame, dict], pd.Series]] = {
    # Price / return
    "consecutive_down":    eval_consecutive_down,
    "consecutive_up":      eval_consecutive_up,
    "gap_down":            eval_gap_down,
    "gap_up":              eval_gap_up,
    "near_52w_low":        eval_near_52w_low,
    "near_52w_high":       eval_near_52w_high,
    "breakout_52w_high":   eval_breakout_52w_high,
    "above_level":         eval_above_level,
    "below_sma":           eval_below_sma,
    "above_sma":           eval_above_sma,
    # Volume
    "high_volume":         eval_high_volume,
    "volume_climax_down":  eval_volume_climax_down,
    "volume_climax_up":    eval_volume_climax_up,
    # Volatility
    "nr7":                 eval_nr7,
    # RSI
    "oversold_rsi":        eval_oversold_rsi,
    "overbought_rsi":      eval_overbought_rsi,
    # Candlestick
    "candle":              eval_candle,
    # Calendar
    "end_of_month":        eval_end_of_month,
    "turn_of_month":       eval_turn_of_month,
    "day_of_week":         eval_day_of_week,
    "fomc_proximity":      eval_fomc_proximity,
    "opex_week":           eval_opex_week,
    "triple_witching_week": eval_triple_witching_week,
    # Sector
    "sector_leading_nd":   eval_sector_leading_nd,
    "xly_vs_xlp":          eval_xly_vs_xlp,
    "iwm_vs_spy":          eval_iwm_vs_spy,
    # OMNI / Oscar / HMA
    "omni_cross_up":          eval_omni_cross_up,
    "omni_cross_down":        eval_omni_cross_down,
    "omni_green_nd":          eval_omni_green_nd,
    "omni_red_nd":            eval_omni_red_nd,
    "oscar_cross_up":         eval_oscar_cross_up,
    "oscar_cross_down":       eval_oscar_cross_down,
    "oscar_above_50":         eval_oscar_above_50,
    "ema_lows_cross_up":      eval_ema_lows_cross_up,
    "ema_lows_cross_down":    eval_ema_lows_cross_down,
    "ema_lows_support":       eval_ema_lows_support,
    "ema_lows_above_nd":      eval_ema_lows_above_nd,
    "ema_lows_green_slope":   eval_ema_lows_green_slope,
    "hma_cross_up":           eval_hma_cross_up,
    "hma_cross_down":         eval_hma_cross_down,
    # Aliases for probability engine compatibility
    "down_streak":         eval_consecutive_down,
    "up_streak":           eval_consecutive_up,
}


def evaluate(df: pd.DataFrame, condition_type: str, params: dict) -> pd.Series:
    """
    Evaluate a condition against a OHLCV DataFrame.

    Parameters
    ----------
    df             : DataFrame with columns open/high/low/close/volume, DatetimeIndex
    condition_type : one of the keys in REGISTRY
    params         : condition parameters dict

    Returns
    -------
    pd.Series[bool] aligned to df.index — True where signal fires
    """
    fn = REGISTRY.get(condition_type)
    if fn is None:
        raise ValueError(
            f"Unknown condition_type {condition_type!r}. "
            f"Available: {sorted(REGISTRY)}"
        )
    result = fn(df, params)
    return result.astype(bool)
