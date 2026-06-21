"""
pattern_fulfillment_indicators.py
====================================
Builds Candidate records for the 6 indicator-based patterns that have a
real, self-contained confirm/invalidate structure in pattern_reference:
macd, omni_82, oscar_87, sma_stack (all "confirmed_immediately" -- the
textual confirmation_condition IS the recognition event itself, e.g. "MACD
crosses above signal line" -- so the real test of whether the signal held
up or whipsawed is left entirely to Stage B's R-bracket, not a separate
Stage A check) and vwap, rsi (genuine two-stage recognition->confirmation,
handled with a small bespoke forward scan over the INDICATOR's own series
rather than price, passed through Candidate.extra["precomputed_stage_a"]
since the shared engine's generic Stage A monitors closing price against a
level, not an indicator series against its own threshold).

EXCLUDED from this module and from the whole Step 2/3/4 framework: adx,
atr, swing_leg, volume_ratio. Per pattern_reference's own text these are
context/filter indicators with no self-contained direction+confirm+
invalidate of their own (adx/atr/swing_leg literally say "N/A -- not a
signal" / "pure volatility context"; volume_ratio's text is explicitly
conditional on "any directional signal" elsewhere, not a standalone setup).
Forcing a fake direction onto them would not be honest measurement. They
are still reported in Step 1's instance/coverage inventory, just with no
expectancy entry. See PATTERN_FULFILLMENT_REPORT.md Step 1.

macd/vwap/rsi/volume_ratio run on 5m (atlas_research.intraday.features.
compute_features, reused verbatim, already PIT-verified in the setup-
formation v2 measurement). omni_82/oscar_87/sma_stack run on daily (these
are confirmed daily-only in practice elsewhere in the codebase).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from atlas_research.features.omni_proxy import (
    ema_lows, ema_lows_cross_up_indices, oscar, oscar_cross_up_indices,
)
from pattern_fulfillment_common import Candidate

OMNI_PERIOD = 82
OSCAR_PERIOD = 87
SMA_FAST, SMA_MID, SMA_SLOW = 50, 150, 200
RSI_OVERSOLD, RSI_OVERBOUGHT = 30.0, 70.0
RSI_RECLAIM_BULL_LEVEL, RSI_RECLAIM_BEAR_LEVEL = 40.0, 60.0
VWAP_HOLD_BARS = 1   # simplified from pattern_reference's "1-2 bars" -- documented


def build_macd_candidates(feat_df: pd.DataFrame, ticker: str) -> list[Candidate]:
    bull = feat_df["macd_bull_cross"].fillna(False).to_numpy()
    bear = feat_df["macd_bear_cross"].fillna(False).to_numpy()
    out = []
    for i in np.where(bull)[0]:
        out.append(Candidate("macd", ticker, "5m", int(i), "long",
                              confirm_level=None, invalidate_level=None, confirmed_immediately=True))
    for i in np.where(bear)[0]:
        out.append(Candidate("macd", ticker, "5m", int(i), "short",
                              confirm_level=None, invalidate_level=None, confirmed_immediately=True))
    return sorted(out, key=lambda c: c.idx)


def build_rsi_candidates(feat_df: pd.DataFrame, ticker: str, window: int) -> list[Candidate]:
    rsi = feat_df["rsi14"].to_numpy()
    n = len(rsi)
    oversold = feat_df["rsi_oversold"].fillna(False).to_numpy()
    overbought = feat_df["rsi_overbought"].fillna(False).to_numpy()
    prev_oversold = np.concatenate([[False], oversold[:-1]])
    prev_overbought = np.concatenate([[False], overbought[:-1]])
    enter_oversold = oversold & ~prev_oversold
    enter_overbought = overbought & ~prev_overbought

    out = []
    for i0 in np.where(enter_oversold)[0]:
        stage_a = _scan_series_cross(rsi, i0, n, window, RSI_RECLAIM_BULL_LEVEL, "above")
        out.append(Candidate("rsi", ticker, "5m", int(i0), "long",
                              confirm_level=None, invalidate_level=None,
                              extra={"precomputed_stage_a": stage_a}))
    for i0 in np.where(enter_overbought)[0]:
        stage_a = _scan_series_cross(rsi, i0, n, window, RSI_RECLAIM_BEAR_LEVEL, "below")
        out.append(Candidate("rsi", ticker, "5m", int(i0), "short",
                              confirm_level=None, invalidate_level=None,
                              extra={"precomputed_stage_a": stage_a}))
    return sorted(out, key=lambda c: c.idx)


def _scan_series_cross(series, i0, n, window, level, direction):
    """Generic helper: from i0, scan forward `window` bars for the first bar
    where `series` crosses beyond `level` in `direction` ('above'/'below').
    Used for RSI reclaim (series=rsi14, no separate invalidation level --
    'stays extreme' is the NEITHER_A timeout)."""
    lo, hi = i0 + 1, min(n - 1, i0 + window)
    for j in range(lo, hi + 1):
        if np.isnan(series[j]):
            continue
        if direction == "above" and series[j] > level:
            return ("CONFIRMED", j, "long")
        if direction == "below" and series[j] < level:
            return ("CONFIRMED", j, "short")
    return ("NEITHER_A", None, None)


def build_vwap_candidates(feat_df: pd.DataFrame, ticker: str) -> list[Candidate]:
    close = feat_df["close"].to_numpy()
    vwap = feat_df["vwap"].to_numpy()
    cross_up = feat_df["vwap_cross_up"].fillna(False).to_numpy()
    cross_down = feat_df["vwap_cross_down"].fillna(False).to_numpy()
    n = len(close)
    out = []
    for i0 in np.where(cross_up)[0]:
        stage_a = _vwap_hold_check(close, vwap, i0, n, "long")
        out.append(Candidate("vwap", ticker, "5m", int(i0), "long",
                              confirm_level=None, invalidate_level=None,
                              extra={"precomputed_stage_a": stage_a}))
    for i0 in np.where(cross_down)[0]:
        stage_a = _vwap_hold_check(close, vwap, i0, n, "short")
        out.append(Candidate("vwap", ticker, "5m", int(i0), "short",
                              confirm_level=None, invalidate_level=None,
                              extra={"precomputed_stage_a": stage_a}))
    return sorted(out, key=lambda c: c.idx)


def _vwap_hold_check(close, vwap, i0, n, direction):
    """Confirmed: holds beyond VWAP for VWAP_HOLD_BARS bars after the cross.
    Invalidated: returns back across VWAP within 1 bar (pattern_reference's
    own wording for the long-reclaim case; applied symmetrically here)."""
    j = i0 + 1
    if j >= n:
        return ("NEITHER_A", None, None)
    holds = (close[j] > vwap[j]) if direction == "long" else (close[j] < vwap[j])
    if holds:
        return ("CONFIRMED", j, direction)
    return ("INVALIDATED", j, direction)


def build_omni82_candidates(high, low, close, open_, ticker: str) -> list[Candidate]:
    close = np.asarray(close, float); low = np.asarray(low, float)
    cross_up_idx = ema_lows_cross_up_indices(low, close, OMNI_PERIOD)
    out = []
    for i in cross_up_idx:
        out.append(Candidate("omni_82", ticker, "daily", int(i), "long",
                              confirm_level=None, invalidate_level=None, confirmed_immediately=True))
    return out


def build_oscar87_candidates(high, low, close, ticker: str) -> list[Candidate]:
    high = np.asarray(high, float); low = np.asarray(low, float); close = np.asarray(close, float)
    cross_up_idx = oscar_cross_up_indices(high, low, close, OSCAR_PERIOD)
    out = []
    for i in cross_up_idx:
        out.append(Candidate("oscar_87", ticker, "daily", int(i), "long",
                              confirm_level=None, invalidate_level=None, confirmed_immediately=True))
    return out


def build_sma_stack_candidates(close, ticker: str) -> list[Candidate]:
    close_s = pd.Series(np.asarray(close, float))
    sma50 = close_s.rolling(SMA_FAST).mean()
    sma150 = close_s.rolling(SMA_MID).mean()
    sma200 = close_s.rolling(SMA_SLOW).mean()
    stacked = (sma50 > sma150) & (sma150 > sma200)
    slope_up = sma50.diff(3) > 0
    aligned = (stacked & slope_up).fillna(False).to_numpy()
    prev_aligned = np.concatenate([[False], aligned[:-1]])
    newly_aligned = aligned & ~prev_aligned
    out = []
    for i in np.where(newly_aligned)[0]:
        out.append(Candidate("sma_stack", ticker, "daily", int(i), "long",
                              confirm_level=None, invalidate_level=None, confirmed_immediately=True))
    return out
