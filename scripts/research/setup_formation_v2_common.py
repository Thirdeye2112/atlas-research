"""
setup_formation_v2_common.py
==============================
Shared config, DB/env bootstrap, and the multi-tool POINT-IN-TIME STATE
SNAPSHOT builder for the setup-formation v2 measurement (research/setup-
formation-v2 branch). See reports/research/SETUP_FORMATION_V2_REPORT.md.

This is a FOUNDATION MEASUREMENT, not a predictor and not a trading signal.
Single-timeframe (5m) only -- no daily context attached here by design (that
is an explicitly deferred later phase). N=2 only this round.

v1 (commit 076bc86, branch research/setup-formation) used a thin feature set:
candle geometry + ATR + vol_ratio + 19 candlestick patterns + daily S/R
context, and found a null result. v2's question: does the FULL tool-state
picture (every PIT-computable 5m indicator, not just candle shape) change
that null result? See SETUP_FORMATION_V2_REPORT.md Section "Step 0" for the
full v1-vs-v2 feature diff.

Reuses, without modification:
    atlas_research.intraday.features.compute_features
        -- VWAP, EMAs, RSI, MACD, ATR, volume ratio, opening-range breakout,
           candle geometry. Verified PIT-safe column-by-column (every column
           is .shift()/.rolling()/.ewm()/.cumsum()-within-day only). ONE
           caveat found and worked around here, not in features.py itself:
           or_high/or_low are correct (backward-looking) for bars AFTER the
           opening range, but for bars INSIDE the opening range window itself
           (in_or=True) they reflect the full completed OR range, which is a
           lookahead relative to those early bars. orb_bull_signal/
           orb_bear_signal are unaffected (gated by ~in_or already), but the
           descriptive above_or_high/below_or_low state must NOT be read
           during in_or bars -- see build_tool_snapshot's "orb" block, which
           reports state_orb="in_opening_range" for those bars instead.
    atlas_research.ta.candlesticks.detect_all_candles / prior_trend
        -- same EQ_TOL_5M=0.0008 tuning v1 established (build_candle_memory.py
           precedent), reused verbatim for continuity/comparability with v1.
    atlas_research.ta.structure.swing_pivots / classify_trend
        -- pure-numpy, timeframe-agnostic. PIT subtlety handled explicitly in
           build_swing_lookup(): a pivot at bar index i is only "known" once
           bar i+width has been observed (the fractal test looks `width` bars
           forward), so it is folded into the trend state only from index
           i+width onward, never earlier.

Deliberately NOT used (see SETUP_FORMATION_V2_REPORT.md Step 1 for why):
    - Channel detection: does not exist anywhere in this codebase (daily or
      5m) -- a genuine gap, not a scoping choice.
    - Stochastic oscillator: does not exist (OSCAR exists but is a different,
      daily-only formula).
    - OMNI-82 (EMA-of-lows): exists in atlas_research.features.omni_proxy but
      is daily-only in practice, never wired to 5m bars.
    - gaps/FVG and vwap_5m (DB tables): both now exist live in the database
      (applied today as migrations 0048_gaps.sql / 0047_vwap_5m.sql) but are
      products of separate, still-in-flux work on branch feat/gaps, not on
      the branch this worktree is built from. vwap_5m is also, as of this
      run, missing AAPL entirely (mid-backfill) -- confirmed by direct query.
      Per explicit user decision, excluded from this run; flagged as a v3
      candidate once that work stabilizes and is merged.
    - Full dome/swing-leg "early signature" metrics (early_gain/early_slope/
      leg_amp/corr_depth in atlas_research.ta.patterns.swing_legs): a deeper,
      separate research thread (branch research/dome-symmetry). Used the
      lighter swing_pivots+classify_trend trend-state instead, to keep the
      tool count (and therefore the combination-testing space in Step 3)
      bounded -- consistent with v1's own "reuse what exists, do not invent
      new pattern logic" discipline.
"""
from __future__ import annotations

import sys
from pathlib import Path

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_WORKTREE_ROOT / "src"))
sys.path.insert(0, str(_WORKTREE_ROOT))

from dotenv import load_dotenv, find_dotenv  # noqa: E402
# Same worktree dotenv-discovery fix as v1: load_dotenv() with no path does
# stack-inspection on THIS file's location (no .env in this worktree), so it
# would silently fall back to settings.py's placeholder DB URL. usecwd=True
# forces cwd-based discovery -- only correct when invoked with cwd = the main
# repo checkout (C:\Atlas\atlas-research), where the real .env lives.
load_dotenv(find_dotenv(usecwd=True), override=True)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from atlas_research.intraday.features import compute_features  # noqa: E402
from atlas_research.ta.candlesticks import detect_all_candles, prior_trend  # noqa: E402
from atlas_research.ta.structure import swing_pivots, classify_trend  # noqa: E402

import config.settings as settings  # noqa: E402

DATABASE_URL = settings.DATABASE_URL


# ---------------------------------------------------------------------------
# Measurement parameters
# ---------------------------------------------------------------------------

TICKERS = ["AAPL", "NKE", "INTC"]
N_WINDOW = 2                 # fixed this round -- v2 step 0/1/2 brief: "Start with N=2 ONLY"
K_VALUES = [1, 2, 3, 4, 5]
MAX_K = max(K_VALUES)

# Candlestick tolerance -- reused verbatim from v1 / build_candle_memory.py's
# own 5m tuning (daily default EQ_TOL=0.003 over-fires at 5m resolution).
EQ_TOL_5M = 0.0008

# Candle/geometry trigger thresholds -- reused verbatim from v1.
GEOM_BODY_PCT_MIN  = 60.0
GEOM_SIZE_ATR_MULT = 1.2

# ATR "expanding" threshold -- the codebase only defines the compressed side
# (vol_compressed: atr14 < atr14_ma*0.75, in features.py). No existing
# precedent for the opposite side, so this mirrors it symmetrically
# (1/0.75 = the reciprocal ratio) rather than inventing an unrelated number.
ATR_EXPAND_MULT = 1.0 / 0.75   # ~= 1.333

# Swing-pivot fractal width -- structure.py's own default, reused as-is.
PIVOT_WIDTH = 3
SWING_TREND_LOOKBACK = 4       # classify_trend's own default, reused as-is.

# Forward-outcome ATR target -- identical definition to v1, for comparability.
ATR_HIT_MULT = 1.0
FORWARD_RETURN_FLAT_EPS = 0.02

# Walk-forward split -- identical convention to v1.
TRAIN_FRACTION = 0.70

# Multiple-testing / reporting threshold -- identical convention to v1.
MIN_CELL_N = 30

TOOL_NAMES = ["candle", "volume", "macd", "rsi", "ema", "vwap", "atr", "swing", "orb"]


# ---------------------------------------------------------------------------
# Raw data loading
# ---------------------------------------------------------------------------

def load_intraday_bars(engine, ticker: str) -> pd.DataFrame:
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


# ---------------------------------------------------------------------------
# Candlestick pattern lookup (computed ONCE per ticker over full history) --
# identical approach to v1's build_pattern_lookup.
# ---------------------------------------------------------------------------

def build_pattern_lookup(o: np.ndarray, h: np.ndarray, l: np.ndarray, c: np.ndarray) -> dict:
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
# Swing-structure lookup -- PIT-safe: a pivot at idx i is only known from bar
# i+PIVOT_WIDTH onward (the fractal test looks PIVOT_WIDTH bars forward).
# ---------------------------------------------------------------------------

def build_swing_lookup(high: np.ndarray, low: np.ndarray) -> dict:
    n = len(high)
    pivots = swing_pivots(high, low, width=PIVOT_WIDTH)

    state = np.full(n, "range", dtype=object)
    active = np.zeros(n, dtype=bool)

    if not pivots:
        return {"state": state, "active": active}

    known_at = [p.idx + PIVOT_WIDTH for p in pivots]
    event_trend = [classify_trend(pivots[: i + 1], lookback=SWING_TREND_LOOKBACK) for i in range(len(pivots))]

    for i, ka in enumerate(known_at):
        if ka >= n:
            continue
        active[ka] = True
        nxt = known_at[i + 1] if i + 1 < len(known_at) else n
        state[ka:min(nxt, n)] = event_trend[i]

    return {"state": state, "active": active}


# ---------------------------------------------------------------------------
# Tool-state snapshot: for every bar T, the state + active(="notable event
# at T") flag for each of the 9 tools, plus confluence_count.
# ---------------------------------------------------------------------------

def build_tool_snapshot(feat_df: pd.DataFrame, pattern_lookup: dict, swing_lookup: dict) -> pd.DataFrame:
    n = len(feat_df)

    # -- candle (N=2 trigger: identical logic to v1's N=2 classifier, minus
    #    v1's FLAT override -- FLAT was a property of the whole window's
    #    volatility, not of one tool's state; v2 reports each tool
    #    independently, so "nothing notable" already covers that case.)
    candle_rng = feat_df["candle_rng"].to_numpy(dtype=float)
    atr14 = feat_df["atr14"].to_numpy(dtype=float)
    body_pct = feat_df["body_pct"].to_numpy(dtype=float)
    is_green = feat_df["is_green"].to_numpy(dtype=bool)
    is_red = feat_df["is_red"].to_numpy(dtype=bool)

    pat_name = pattern_lookup["name"]
    pat_dir = pattern_lookup["direction"]
    pat_span = pattern_lookup["span"]
    has_pattern = np.array([nm is not None for nm in pat_name])
    pattern_fits = has_pattern & (pat_span <= N_WINDOW)

    prev_green = np.concatenate([[False], is_green[:-1]])
    prev_red = np.concatenate([[False], is_red[:-1]])
    dir_long_geo = is_green & prev_green
    dir_short_geo = is_red & prev_red
    size_ok = candle_rng >= GEOM_SIZE_ATR_MULT * atr14
    body_ok = body_pct >= GEOM_BODY_PCT_MIN
    geo_signal = size_ok & body_ok & (dir_long_geo | dir_short_geo)

    setup_from_pattern = pattern_fits
    setup_from_geo = geo_signal & ~setup_from_pattern
    active_candle = setup_from_pattern | setup_from_geo

    state_candle = np.full(n, None, dtype=object)
    direction_candle = np.full(n, None, dtype=object)
    idx_pat = np.where(setup_from_pattern)[0]
    for i in idx_pat:
        state_candle[i] = pat_name[i]
        direction_candle[i] = pat_dir[i]
    idx_geo = np.where(setup_from_geo)[0]
    for i in idx_geo:
        if dir_long_geo[i]:
            state_candle[i] = "directional_thrust_up"
            direction_candle[i] = "long"
        else:
            state_candle[i] = "directional_thrust_down"
            direction_candle[i] = "short"

    # -- volume
    vol_ratio = feat_df["vol_ratio"]
    high_vol = feat_df["high_vol"].fillna(False)
    very_hi_vol = feat_df["very_hi_vol"].fillna(False)
    state_volume = np.select(
        [very_hi_vol, high_vol, vol_ratio < 0.7],
        ["very_high", "high", "low"],
        default="normal",
    )
    active_volume = (
        (high_vol & ~high_vol.shift(1).fillna(False))
        | (very_hi_vol & ~very_hi_vol.shift(1).fillna(False))
    ).to_numpy()

    # -- macd
    macd = feat_df["macd"]
    macd_signal = feat_df["macd_signal_line"]
    state_macd = np.where(macd >= macd_signal, "bull", "bear")
    active_macd = (feat_df["macd_bull_cross"].fillna(False) | feat_df["macd_bear_cross"].fillna(False)).to_numpy()

    # -- rsi
    rsi_oversold = feat_df["rsi_oversold"].fillna(False)
    rsi_overbought = feat_df["rsi_overbought"].fillna(False)
    state_rsi = np.select([rsi_oversold, rsi_overbought], ["oversold", "overbought"], default="neutral")
    active_rsi = (
        feat_df["rsi_reclaim_bull"].fillna(False)
        | feat_df["rsi_reclaim_bear"].fillna(False)
        | (rsi_oversold & ~rsi_oversold.shift(1).fillna(False))
        | (rsi_overbought & ~rsi_overbought.shift(1).fillna(False))
    ).to_numpy()

    # -- ema (price vs ema9 vs ema20 "stack")
    price_above_ema9 = feat_df["price_above_ema9"].fillna(False)
    ema9_above_ema20 = feat_df["ema9_above_ema20"].fillna(False)
    stack_bull = price_above_ema9 & ema9_above_ema20
    stack_bear = (~price_above_ema9) & (~ema9_above_ema20)
    state_ema = np.select([stack_bull, stack_bear], ["bull_stack", "bear_stack"], default="mixed")
    active_ema = (pd.Series(state_ema) != pd.Series(state_ema).shift(1)).to_numpy().copy()
    active_ema[0] = False

    # -- vwap (compute_features' own cumulative-from-open VWAP -- not the new
    #    vwap_5m DB table, which is mid-backfill and missing AAPL entirely)
    above_vwap = feat_df["above_vwap"].fillna(False)
    state_vwap = np.where(above_vwap, "above", "below")
    active_vwap = (feat_df["vwap_cross_up"].fillna(False) | feat_df["vwap_cross_down"].fillna(False)).to_numpy()

    # -- atr / realized vol
    vol_compressed = feat_df["vol_compressed"].fillna(False)
    vol_expanding = (feat_df["atr14"] > feat_df["atr14_ma"] * ATR_EXPAND_MULT).fillna(False)
    state_atr = np.select([vol_compressed, vol_expanding], ["compressed", "expanding"], default="normal")
    active_atr = (
        (vol_compressed & ~vol_compressed.shift(1).fillna(False))
        | (vol_expanding & ~vol_expanding.shift(1).fillna(False))
    ).to_numpy()

    # -- swing structure (precomputed lookup, PIT-lag already applied)
    state_swing = swing_lookup["state"]
    active_swing = swing_lookup["active"]

    # -- opening range breakout. in_or bars get an honest "in_opening_range"
    #    state instead of reading above_or_high/below_or_low, which are not
    #    yet PIT-valid until the OR window itself has fully closed.
    in_or = feat_df["in_or"].fillna(False)
    above_or_high = feat_df["above_or_high"].fillna(False)
    below_or_low = feat_df["below_or_low"].fillna(False)
    state_orb = np.select(
        [in_or, above_or_high, below_or_low],
        ["in_opening_range", "above_or_high", "below_or_low"],
        default="inside_range",
    )
    active_orb = (feat_df["orb_bull_signal"].fillna(False) | feat_df["orb_bear_signal"].fillna(False)).to_numpy()

    active_mat = np.column_stack([
        active_candle, active_volume, active_macd, active_rsi,
        active_ema, active_vwap, active_atr, active_swing, active_orb,
    ])
    confluence_count = active_mat.sum(axis=1).astype(int)
    active_tools_csv = [
        ",".join(name for name, flag in zip(TOOL_NAMES, row) if flag)
        for row in active_mat
    ]

    valid = ~(feat_df["atr14_ma"].isna() | feat_df["vol_ma20"].isna() | feat_df["atr14"].isna())

    out = pd.DataFrame({
        "state_candle": state_candle, "direction_candle": direction_candle, "active_candle": active_candle,
        "state_volume": state_volume, "active_volume": active_volume,
        "state_macd": state_macd, "active_macd": active_macd,
        "state_rsi": state_rsi, "active_rsi": active_rsi,
        "state_ema": state_ema, "active_ema": active_ema,
        "state_vwap": state_vwap, "active_vwap": active_vwap,
        "state_atr": state_atr, "active_atr": active_atr,
        "state_swing": state_swing, "active_swing": active_swing,
        "state_orb": state_orb, "active_orb": active_orb,
        "confluence_count": confluence_count,
        "active_tools_csv": active_tools_csv,
        "_valid": valid.to_numpy(),
    })
    return out
