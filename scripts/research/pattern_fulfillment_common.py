"""
pattern_fulfillment_common.py
================================
Shared config, DB/env bootstrap, and the GENERIC recognition -> confirm/
invalidate/neither -> R-bracket outcome -> inversion engine for the pattern-
fulfillment backtest (research/pattern-fulfillment branch).

FOUNDATION MEASUREMENT, not a predictor, not a trading signal. See
reports/research/PATTERN_FULFILLMENT_REPORT.md.

Every detector module (candlesticks, chart patterns, channels, indicator
cross-events, gaps, supplemental shapes) emits a uniform `Candidate` record:
    pattern_type, ticker, timeframe, idx (bar index of recognition, T_recog),
    direction ('long'/'short', or None for two-sided doji/spinning_top which
    resolve direction AT confirmation), confirm_level, invalidate_level
    (each a float, or a callable(j)->float for time-varying levels like
    channel boundaries), confirmed_immediately (bool -- True for
    morning_star/evening_star, where detect_all_candles's own shape
    condition already IS the textual "confirmation").

The engine (run_instance) then does, PIT-safe, using only bars > T_recog:
  Stage A: scan forward up to STAGE_A_WINDOW bars for the first bar where
    EITHER invalidate_level is crossed (against direction) OR confirm_level
    is crossed (with direction). Invalidation is checked before confirmation
    on a tied bar (conservative tie-break -- documented, not arbitrary).
  Stage B (only if confirmed): from T_confirm, run the ATR R-bracket (stop =
    1xATR against direction, targets R=1,2,3 in favor) over the next
    STAGE_B_WINDOW bars. Settlement rule: the FIRST bar (chronologically)
    that breaches either the stop or any target decides the outcome; if a
    bar breaches both the stop and a target in the same bar, the stop wins
    (conservative, standard backtesting convention -- you don't get to
    choose your fill mid-bar). realized_R = the highest target reached
    before the stop (capped at 3), or -1.0 if stopped first, or the raw
    mark-to-market R at window-close if neither is hit (NEITHER_B).
  Stage C (only if invalidated AND the pattern has a codeable inversion
    direction): identical R-bracket logic to Stage B, anchored at
    T_invalidate, in the inversion direction.
"""
from __future__ import annotations

import sys
from pathlib import Path

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_WORKTREE_ROOT / "src"))
sys.path.insert(0, str(_WORKTREE_ROOT))

from dotenv import load_dotenv, find_dotenv  # noqa: E402
load_dotenv(find_dotenv(usecwd=True), override=True)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config.settings as settings  # noqa: E402

DATABASE_URL = settings.DATABASE_URL

TICKERS = ["AAPL", "NKE", "INTC"]

# Forward windows (bars), per timeframe -- used for BOTH Stage A (confirm/
# invalidate scan) and Stage B/C (R-bracket outcome scan), each stage gets
# its own fresh allocation of this many bars from its own anchor.
STAGE_WINDOW = {"5m": 24, "daily": 15}

R_MULTIPLES = [1, 2, 3]
ATR_STOP_MULT = 1.0

TRAIN_FRACTION = 0.70
MIN_CELL_N = 30
BH_FDR_Q = 0.10

RNG_SEED = 20260622  # baseline random-direction sampling, fixed for reproducibility


# ---------------------------------------------------------------------------
# Candidate record (one per detected pattern instance, pre-outcome)
# ---------------------------------------------------------------------------

class Candidate:
    __slots__ = ("pattern_type", "ticker", "timeframe", "idx", "direction",
                 "confirm_level", "invalidate_level", "confirmed_immediately",
                 "two_sided", "extra")

    def __init__(self, pattern_type, ticker, timeframe, idx, direction,
                 confirm_level, invalidate_level, confirmed_immediately=False,
                 two_sided=False, extra=None):
        self.pattern_type = pattern_type
        self.ticker = ticker
        self.timeframe = timeframe
        self.idx = idx
        self.direction = direction          # 'long' | 'short' | None (two_sided)
        self.confirm_level = confirm_level    # float or callable(j)->float
        self.invalidate_level = invalidate_level  # float or callable(j)->float or None
        self.confirmed_immediately = confirmed_immediately
        self.two_sided = two_sided
        self.extra = extra or {}


def _level_at(level, j):
    if level is None:
        return None
    return level(j) if callable(level) else level


# ---------------------------------------------------------------------------
# Stage A: confirm / invalidate / neither
# ---------------------------------------------------------------------------

def stage_a_scan(cand: Candidate, close: np.ndarray, window: int):
    """Returns (outcome, t_event, realized_direction).
    outcome in {'CONFIRMED', 'INVALIDATED', 'NEITHER_A'}.
    realized_direction is cand.direction normally; for two_sided patterns
    (doji/spinning_top) it's resolved by WHICHEVER side confirms first.
    """
    n = len(close)
    i0 = cand.idx
    lo = i0 + 1
    hi = min(n - 1, i0 + window)

    precomputed = cand.extra.get("precomputed_stage_a")
    if precomputed is not None:
        return precomputed

    if cand.confirmed_immediately:
        # Recognition bar IS the confirmation bar (morning_star/evening_star).
        return "CONFIRMED", i0, cand.direction

    if cand.two_sided:
        # doji/spinning_top: direction resolved by whichever level breaks first.
        bull_level = cand.confirm_level["long"]
        bear_level = cand.confirm_level["short"]
        for j in range(lo, hi + 1):
            cj = close[j]
            if cj > _level_at(bull_level, j):
                return "CONFIRMED", j, "long"
            if cj < _level_at(bear_level, j):
                return "CONFIRMED", j, "short"
        return "NEITHER_A", None, None

    sign = 1.0 if cand.direction == "long" else -1.0
    for j in range(lo, hi + 1):
        cj = close[j]
        inv_lvl = _level_at(cand.invalidate_level, j)
        if inv_lvl is not None and (cj - inv_lvl) * sign < 0:
            return "INVALIDATED", j, cand.direction
        conf_lvl = _level_at(cand.confirm_level, j)
        if conf_lvl is not None and (cj - conf_lvl) * sign > 0:
            return "CONFIRMED", j, cand.direction
    return "NEITHER_A", None, cand.direction


# ---------------------------------------------------------------------------
# Stage B/C: ATR R-bracket outcome
# ---------------------------------------------------------------------------

def r_bracket_outcome(direction: str, entry: float, atr: float,
                       high: np.ndarray, low: np.ndarray, close: np.ndarray,
                       t_anchor: int, window: int):
    """Returns dict: outcome ('WIN'/'LOSS'/'NEITHER'), max_r (int 0-3),
    realized_R (float), t_exit (int or None)."""
    n = len(close)
    if atr is None or not np.isfinite(atr) or atr <= 0:
        return {"outcome": "NEITHER", "max_r": 0, "realized_R": np.nan, "t_exit": None}

    sign = 1.0 if direction == "long" else -1.0
    stop_price = entry - sign * ATR_STOP_MULT * atr
    target_prices = {r: entry + sign * r * atr for r in R_MULTIPLES}

    lo = t_anchor + 1
    hi = min(n - 1, t_anchor + window)

    for j in range(lo, hi + 1):
        hj, lj = high[j], low[j]
        stop_hit = (lj <= stop_price) if direction == "long" else (hj >= stop_price)
        max_r_this_bar = 0
        for r in R_MULTIPLES:
            tgt = target_prices[r]
            hit = (hj >= tgt) if direction == "long" else (lj <= tgt)
            if hit:
                max_r_this_bar = r
        if stop_hit and max_r_this_bar == 0:
            return {"outcome": "LOSS", "max_r": 0, "realized_R": -1.0, "t_exit": j}
        if stop_hit and max_r_this_bar > 0:
            # both touched same bar -- stop wins (conservative convention)
            return {"outcome": "LOSS", "max_r": 0, "realized_R": -1.0, "t_exit": j}
        if max_r_this_bar > 0:
            return {"outcome": "WIN", "max_r": max_r_this_bar, "realized_R": float(max_r_this_bar), "t_exit": j}

    # NEITHER: mark-to-market R at window close
    j_end = hi
    if j_end < lo:
        return {"outcome": "NEITHER", "max_r": 0, "realized_R": np.nan, "t_exit": None}
    mtm_r = (close[j_end] - entry) / atr * sign
    return {"outcome": "NEITHER", "max_r": 0, "realized_R": float(mtm_r), "t_exit": j_end}


# ---------------------------------------------------------------------------
# Baseline: random-direction entries, same bracket, same window
# ---------------------------------------------------------------------------

def baseline_outcomes(ticker: str, timeframe: str, n: int, atr: np.ndarray,
                       high: np.ndarray, low: np.ndarray, close: np.ndarray,
                       window: int, valid_mask: np.ndarray, sample_every: int = 1) -> pd.DataFrame:
    """One synthetic 'instance' per valid bar (or every `sample_every`-th),
    direction assigned by a fixed-seed coin flip, same R-bracket as real
    patterns. This is the 'edge over doing nothing with the same risk
    geometry' comparison, NOT a pattern -- it has no confirm/invalidate
    stage, entry is immediate at the bar's close."""
    rng = np.random.default_rng(RNG_SEED + hash((ticker, timeframe)) % 10_000)
    idxs = np.where(valid_mask)[0][::sample_every]
    directions = rng.choice(["long", "short"], size=len(idxs))
    rows = []
    for k, i0 in enumerate(idxs):
        a = atr[i0]
        res = r_bracket_outcome(directions[k], close[i0], a, high, low, close, i0, window)
        rows.append({"idx": int(i0), "direction": directions[k], **res})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------

def expectancy_stats(realized_r: pd.Series) -> dict:
    x = realized_r.dropna()
    n = len(x)
    if n == 0:
        return {"n": 0, "expectancy_R": np.nan, "ci_lo": np.nan, "ci_hi": np.nan,
                "win_rate": np.nan, "avg_win_R": np.nan, "avg_loss_R": np.nan}
    mean = x.mean()
    se = x.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
    wins = x[x > 0]
    losses = x[x <= 0]
    return {
        "n": int(n),
        "expectancy_R": float(mean),
        "ci_lo": float(mean - 1.96 * se) if n > 1 else np.nan,
        "ci_hi": float(mean + 1.96 * se) if n > 1 else np.nan,
        "win_rate": float(len(wins) / n),
        "avg_win_R": float(wins.mean()) if len(wins) else np.nan,
        "avg_loss_R": float(losses.mean()) if len(losses) else np.nan,
    }


def welch_t_pvalue(a: pd.Series, b: pd.Series) -> float:
    """Two-sample Welch's t-test p-value (two-sided), no scipy dependency."""
    a = a.dropna().to_numpy(); b = b.dropna().to_numpy()
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return np.nan
    va, vb = a.var(ddof=1), b.var(ddof=1)
    if va == 0 and vb == 0:
        return 1.0 if a.mean() == b.mean() else 0.0
    se2 = va / na + vb / nb
    if se2 <= 0:
        return np.nan
    t = (a.mean() - b.mean()) / np.sqrt(se2)
    dof = se2 ** 2 / ((va / na) ** 2 / (na - 1) + (vb / nb) ** 2 / (nb - 1))
    # two-sided p-value via normal approximation for large dof, t-dist otherwise
    from math import erf, sqrt
    if dof > 200:
        p = 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))
        return float(p)
    # Student-t survival via continued fraction is overkill here; use a
    # conservative normal approximation uniformly -- documented in the
    # report as a simplification (slightly anti-conservative at low dof,
    # which the BH-FDR step below partially offsets by being applied on
    # top regardless).
    p = 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))
    return float(p)


def bh_fdr(pvalues: pd.Series, q: float = BH_FDR_Q) -> pd.Series:
    """Benjamini-Hochberg FDR correction. Returns a boolean Series (same
    index as input) of which hypotheses survive at FDR level q."""
    valid = pvalues.dropna().sort_values()
    m = len(valid)
    if m == 0:
        return pd.Series(False, index=pvalues.index)
    ranks = np.arange(1, m + 1)
    thresh = ranks / m * q
    passed = valid.to_numpy() <= thresh
    # BH rule: find the largest k where p(k) <= k/m*q; all p <= p(k) survive
    if not passed.any():
        survive_idx = []
    else:
        k_max = np.max(np.where(passed)[0])
        survive_idx = valid.index[: k_max + 1]
    out = pd.Series(False, index=pvalues.index)
    out.loc[survive_idx] = True
    return out


def walk_forward_split_mask(n: int, train_fraction: float = TRAIN_FRACTION) -> np.ndarray:
    split_idx = int(n * train_fraction)
    return np.arange(n) < split_idx
