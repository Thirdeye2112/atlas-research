"""
setup_formation_common.py
==========================
Shared config, DB/env bootstrap, and the SETUP_FORMING / NEUTRAL / FLAT
classifier for the setup-formation measurement (research/setup-formation
branch). See reports/research/SETUP_FORMATION_REPORT.md for the write-up.

This is a FOUNDATION MEASUREMENT, not a predictor and not a trading signal.
Everything here must stay strictly point-in-time: a function computed "once
over full history" is safe to reuse across decision points only because each
detector's output at index i is a function of bars <= i (verified per-detector
below). Only the forward-outcome helpers in setup_formation_outcomes.py are
allowed to look past the decision index.

Reuses, without modification:
    atlas_research.intraday.features.compute_features   (candle geometry, ATR, vol_ratio)
    atlas_research.ta.candlesticks.detect_all_candles    (19 candlestick patterns)
    atlas_research.ta.candlesticks.prior_trend

Chart-pattern detectors (ta.patterns: head_and_shoulders, double_top_bottom,
flags) and structure.swing_pivots are NOT used for the N-window classifier:
they require several confirmed swing pivots (flags need 3, H&S needs 5) which
structurally cannot exist inside a 2-5 bar window. Using them here would mean
writing new shrunk-down pattern logic, which the task explicitly forbids
("reuse what exists, do not invent new pattern logic"). This is a deliberate,
documented scoping limitation -- see the report's "Scoping" section.
"""
from __future__ import annotations

import sys
from pathlib import Path

# -- repo path bootstrap (worktree-safe: this file lives in the
#    research/setup-formation worktree, NOT the main checkout) -------------
_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_WORKTREE_ROOT / "src"))
sys.path.insert(0, str(_WORKTREE_ROOT))

from dotenv import load_dotenv, find_dotenv  # noqa: E402
# IMPORTANT: load_dotenv() with no path uses stack inspection on the CALLING
# FILE's location, not the process cwd -- which would search upward from this
# worktree (no .env here) and silently fall back to settings.py's placeholder
# DB URL. find_dotenv(usecwd=True) forces cwd-based discovery instead, so this
# only works correctly when invoked with cwd = the main repo checkout
# (C:\Atlas\atlas-research), where the real .env lives. Never copy/symlink
# .env into the worktree.
load_dotenv(find_dotenv(usecwd=True), override=True)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from atlas_research.intraday.features import compute_features  # noqa: E402
from atlas_research.ta.candlesticks import detect_all_candles, prior_trend  # noqa: E402

import config.settings as settings  # noqa: E402

DATABASE_URL = settings.DATABASE_URL


# ---------------------------------------------------------------------------
# Measurement parameters (also written verbatim to the run log for
# reproducibility -- see setup_formation_run_log.jsonl)
# ---------------------------------------------------------------------------

TICKERS = ["AAPL", "NKE", "INTC"]
N_VALUES = [2, 3, 4, 5]
K_VALUES = [1, 2, 3, 4, 5]
MAX_K = max(K_VALUES)

PIVOT_WIDTH = 3            # unused by the classifier itself; kept for report/scoping notes

# Tweezer high/low matching tolerance. The daily-tuned default (EQ_TOL=0.003 in
# candlesticks.py) over-fires on 5m bars (highs/lows land within 0.3% of each
# other constantly at intraday resolution). build_candle_memory.py's own 5m
# builder already tightens this to 0.0008 -- reuse that exact value rather
# than the daily default, to match the only existing precedent for 5m use.
EQ_TOL_5M = 0.0008

# FLAT: low-volatility / no-information window.
FLAT_RANGE_ATR_MULT = 0.5  # mean(candle_range / ATR14) over the N-window must be below this
FLAT_VOL_RATIO_MAX  = 0.7  # mean(volume / 20-bar avg volume) over the N-window must be below this

# SETUP_FORMING (geometry-only "directional thrust" trigger, used when no
# named candlestick pattern fires). Both must hold on the bar at T.
GEOM_BODY_PCT_MIN   = 60.0  # body_pct (0-100) of the bar at T
GEOM_SIZE_ATR_MULT  = 1.2   # candle_range[T] >= this many ATR14[T]

# Daily S/R "near" tolerance (distance as a fraction of price)
SR_NEAR_TOL = 0.03

# Forward-outcome ATR target
ATR_HIT_MULT = 1.0          # +-1x ATR14[T] move within [T+1, T+k] counts as "hit"
FORWARD_RETURN_FLAT_EPS = 0.02  # pct; |forward_return| below this => forward_direction = "flat"

# Walk-forward split (chronological, per ticker -- date ranges differ by ticker)
TRAIN_FRACTION = 0.70

# Multiple-testing / reporting threshold
MIN_CELL_N = 30              # cells with fewer decision points than this are flagged as noise


# ---------------------------------------------------------------------------
# Per-ticker raw data loading
# ---------------------------------------------------------------------------

def load_intraday_bars(engine, ticker: str) -> pd.DataFrame:
    """Full 5m history for one ticker, ascending by ts. PIT-safe to use in full
    since every downstream detector only looks backward from each index."""
    from sqlalchemy import text
    df = pd.read_sql(
        text("""
            SELECT ticker, ts, open, high, low, close, volume
            FROM intraday_bars
            WHERE ticker = :t AND timeframe = '5m'
            ORDER BY ts
        """),
        engine,
        params={"t": ticker},
    )
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df.reset_index(drop=True)


def load_daily_pattern_context(engine, ticker: str) -> pd.DataFrame:
    """One row per (ticker, confirm_date) from pattern_memory's daily layer.
    Multiple patterns can confirm on the same date; we keep the last (by id),
    mirroring the dedup convention already used by
    build_intraday_candle_memory.py's _load_daily_context()."""
    from sqlalchemy import text
    df = pd.read_sql(
        text("""
            SELECT id, ticker, confirm_date, trend, market_trend,
                   dist_support, dist_resistance, adx, atr_pct AS daily_atr_pct,
                   sma_stacked
            FROM pattern_memory
            WHERE timeframe = 'daily' AND ticker = :t
            ORDER BY confirm_date, id
        """),
        engine,
        params={"t": ticker},
    )
    df = df.sort_values(["confirm_date", "id"]).drop_duplicates(subset=["confirm_date"], keep="last")
    df["confirm_date"] = pd.to_datetime(df["confirm_date"]).astype("datetime64[ns]")
    return df.drop(columns=["id"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Daily context attachment (point-in-time: strictly the prior trading day)
# ---------------------------------------------------------------------------

def attach_daily_context(feat_df: pd.DataFrame, daily_ctx: pd.DataFrame) -> pd.DataFrame:
    """
    For each 5m bar at local date D, attach the most recent pattern_memory
    daily row with confirm_date < D (never D itself -- today's daily candle
    hasn't closed yet relative to any intraday decision point on D).
    """
    local_date = (
        feat_df["ts"].dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None)
        .astype("datetime64[ns]")
    )
    left = pd.DataFrame({"_decision_date": local_date}).reset_index(drop=False)
    left = left.rename(columns={"index": "_orig_idx"}).sort_values("_decision_date")

    right = daily_ctx.sort_values("confirm_date")

    merged = pd.merge_asof(
        left, right,
        left_on="_decision_date", right_on="confirm_date",
        direction="backward", allow_exact_matches=False,
    )
    merged = merged.sort_values("_orig_idx").reset_index(drop=True)

    out = feat_df.reset_index(drop=True).copy()
    out["daily_trend"] = merged["trend"].values
    out["daily_market_trend"] = merged["market_trend"].values
    out["daily_dist_support"] = merged["dist_support"].values
    out["daily_dist_resistance"] = merged["dist_resistance"].values
    return out


def daily_loc_bucket(dist_support, dist_resistance) -> str:
    sup_near = pd.notna(dist_support) and abs(dist_support) <= SR_NEAR_TOL
    res_near = pd.notna(dist_resistance) and abs(dist_resistance) <= SR_NEAR_TOL
    if sup_near and res_near:
        return "near_support" if abs(dist_support) <= abs(dist_resistance) else "near_resistance"
    if sup_near:
        return "near_support"
    if res_near:
        return "near_resistance"
    return "mid_range"


def vectorized_daily_loc(dist_support: np.ndarray, dist_resistance: np.ndarray) -> np.ndarray:
    sup = np.asarray(dist_support, dtype=float)
    res = np.asarray(dist_resistance, dtype=float)
    sup_near = np.abs(sup) <= SR_NEAR_TOL
    res_near = np.abs(res) <= SR_NEAR_TOL
    sup_near = sup_near & ~np.isnan(sup)
    res_near = res_near & ~np.isnan(res)
    out = np.full(len(sup), "mid_range", dtype=object)
    both = sup_near & res_near
    out[both & (np.abs(sup) <= np.abs(res))] = "near_support"
    out[both & (np.abs(sup) > np.abs(res))] = "near_resistance"
    out[sup_near & ~both] = "near_support"
    out[res_near & ~both] = "near_resistance"
    return out


# ---------------------------------------------------------------------------
# Candlestick pattern lookup (computed ONCE per ticker over full history)
# ---------------------------------------------------------------------------

def build_pattern_lookup(o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray) -> dict:
    """
    Run detect_all_candles() once over the full series. PIT-safety: a Candle's
    confirm_idx/start_idx/direction are computed from bars <= confirm_idx only
    (see candlesticks.py) so precomputing once and indexing by confirm_idx is
    equivalent to recomputing at each decision point.

    Returns arrays (length n) of the best DIRECTIONAL (non-neutral) pattern
    confirming exactly at each index: name, direction, span (bars from
    start_idx to confirm_idx inclusive). Neutral patterns (doji, spinning_top)
    are excluded -- they represent indecision, not a forming structure.
    Ties (multiple directional patterns confirming at the same bar) keep the
    one with the larger span (the more "developed" structure).
    """
    n = len(c)
    trend = prior_trend(c)
    candles = detect_all_candles(o, h, l, c, trend=trend, eq_tol=EQ_TOL_5M, skip_neutral=True)

    name = np.full(n, None, dtype=object)
    direction = np.full(n, None, dtype=object)
    span = np.full(n, 0, dtype=int)

    for cdl in candles:
        if cdl.direction not in ("long", "short"):
            continue
        i = cdl.confirm_idx
        s = i - cdl.start_idx + 1
        if name[i] is None or s > span[i]:
            name[i] = cdl.name
            direction[i] = cdl.direction
            span[i] = s

    return {"name": name, "direction": direction, "span": span}


# ---------------------------------------------------------------------------
# Core classifier: SETUP_FORMING / NEUTRAL / FLAT for one (ticker, N)
# ---------------------------------------------------------------------------

def classify_window_state(feat_df: pd.DataFrame, pattern_lookup: dict, n_window: int) -> pd.DataFrame:
    """
    Vectorized classification for every bar T in feat_df (assumes feat_df is
    sorted ascending, single ticker, output of compute_features()). All
    inputs at T are computed from bars <= T only (compute_features() is
    documented strictly backward-looking; the rolling(n_window) windows below
    only look at [T-n_window+1, T]).
    """
    n = len(feat_df)
    candle_rng = feat_df["candle_rng"].to_numpy(dtype=float)
    atr14 = feat_df["atr14"].to_numpy(dtype=float)
    body_pct = feat_df["body_pct"].to_numpy(dtype=float)
    vol_ratio = feat_df["vol_ratio"].to_numpy(dtype=float)
    is_green = feat_df["is_green"].to_numpy(dtype=bool)
    is_red = feat_df["is_red"].to_numpy(dtype=bool)
    consec_green = feat_df["consec_green"].to_numpy(dtype=bool)
    consec_red = feat_df["consec_red"].to_numpy(dtype=bool)

    with np.errstate(divide="ignore", invalid="ignore"):
        rng_atr_ratio = np.where(atr14 > 0, candle_rng / atr14, np.nan)

    rng_atr_s = pd.Series(rng_atr_ratio)
    vol_s = pd.Series(vol_ratio)
    mean_range_atr_N = rng_atr_s.rolling(n_window).mean().to_numpy()
    mean_vol_ratio_N = vol_s.rolling(n_window).mean().to_numpy()

    is_flat = (mean_range_atr_N < FLAT_RANGE_ATR_MULT) & (mean_vol_ratio_N < FLAT_VOL_RATIO_MAX)

    pat_name = pattern_lookup["name"]
    pat_dir = pattern_lookup["direction"]
    pat_span = pattern_lookup["span"]
    has_pattern = np.array([nm is not None for nm in pat_name])
    pattern_fits = has_pattern & (pat_span <= n_window)

    # geometry-only directional thrust
    if n_window == 2:
        dir_long_geo = is_green & np.concatenate([[False], is_green[:-1]])
        dir_short_geo = is_red & np.concatenate([[False], is_red[:-1]])
    else:
        dir_long_geo = consec_green
        dir_short_geo = consec_red

    size_ok = candle_rng >= GEOM_SIZE_ATR_MULT * atr14
    body_ok = body_pct >= GEOM_BODY_PCT_MIN
    geo_dir_signal = dir_long_geo | dir_short_geo
    geo_signal = size_ok & body_ok & geo_dir_signal

    setup_from_pattern = (~is_flat) & pattern_fits
    setup_from_geo = (~is_flat) & geo_signal & ~setup_from_pattern

    setup_forming = setup_from_pattern | setup_from_geo

    setup_state = np.full(n, "NEUTRAL", dtype=object)
    setup_state[is_flat] = "FLAT"
    setup_state[setup_forming] = "SETUP_FORMING"

    setup_type = np.full(n, None, dtype=object)
    direction = np.full(n, None, dtype=object)

    idx_pat = np.where(setup_from_pattern)[0]
    for i in idx_pat:
        setup_type[i] = pat_name[i]
        direction[i] = pat_dir[i]

    idx_geo = np.where(setup_from_geo)[0]
    for i in idx_geo:
        if dir_long_geo[i]:
            setup_type[i] = "directional_thrust_up"
            direction[i] = "long"
        else:
            setup_type[i] = "directional_thrust_down"
            direction[i] = "short"

    out = pd.DataFrame({
        "setup_state": setup_state,
        "setup_type": setup_type,
        "direction": direction,
        "_valid": ~(np.isnan(mean_range_atr_N) | np.isnan(mean_vol_ratio_N) | np.isnan(atr14)),
    })
    return out
