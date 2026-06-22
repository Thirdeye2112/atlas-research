"""
foundation_retest_common.py
==============================
Shared config, DB/env bootstrap, and the measurement engine for the
foundation retest (research/foundation-retest branch). One stock (AAPL),
5m, deep — CONDITIONAL per-tool triggers, not kitchen-sink averaging.

FOUNDATION MEASUREMENT, not a predictor, not a trading signal.

GOOD-SETUP CHECKLIST (extracted from ta/gaps.py, branch feat/gaps, the
methodology the user named as trusted -- see Step 1 of
FOUNDATION_RETEST_REPORT.md for the full writeup):
  1. State explicitly, per trigger, the EXACT bar at which the signal
     becomes causally knowable -- not just "uses past bars."
  2. Where a trigger's "defining bar" and its "earliest knowable bar"
     differ (the swing-pivot-confirmed and channel-break triggers), track
     them as separate fields and decide from the LATTER, never the former.
     This is the exact lesson research/dome-leg-verify found broken: an
     early-signature window that started at the pivot bar itself was
     measuring 3 bars before swing_pivots(width=3) could even confirm a
     pivot existed there. Applied here from the start, not bolted on after.
  3. Minimize and precisely enumerate which bars contribute to each
     trigger; no hidden dependencies.
  4. Reuse the textbook/existing definition (compute_features()'s already
     PIT-verified RSI/MACD/EMA/VWAP/volume columns) rather than inventing
     new thresholds; where a fresh threshold IS needed (e.g. the ATR
     R-bracket multiples), expose it as an explicit, disclosed constant.
  5. Document input preconditions (sort order, single-ticker).

R-bracket / baseline / stats engine reproduces (not imports)
pattern_fulfillment_common.py's design (research/pattern-fulfillment,
already tested across ~700k instances) -- same ATR_STOP_MULT/R_MULTIPLES
convention, for direct comparability with that phase's expectancy numbers.
BH-FDR and the permutation-test helper reproduce dome_leg_signature_common.py
/ dome_leg_verify.py's design (research/dome-leg-signature,
research/dome-leg-verify).
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

TICKER = "AAPL"
TIMEFRAME = "5m"

# Forward measurement
K_VALUES = [3, 6, 12]
R_MULTIPLES = [1, 2, 3]
ATR_STOP_MULT = 1.0
FORWARD_WINDOW = 24          # bars scanned for the R-bracket outcome (covers K=12 plus headroom)

# Pivot / channel detection (same values used throughout this research arc)
PIVOT_WIDTH = 3
AMP_MULT = 2.5               # swing-pivot significance filter, in ATR multiples

# Daily corroboration
TRAIN_FRACTION = 0.70
MIN_CELL_N = 30
BH_FDR_Q = 0.10
RNG_SEED = 20260624


# ---------------------------------------------------------------------------
# R-bracket outcome (identical convention to pattern_fulfillment_common.py)
# ---------------------------------------------------------------------------

def r_bracket_outcome(direction: str, entry: float, atr: float,
                       high: np.ndarray, low: np.ndarray, close: np.ndarray,
                       t_anchor: int, window: int = FORWARD_WINDOW, k_cap: int | None = None):
    """Stop = 1xATR against; targets = 1/2/3xATR in favor. Settlement: first
    bar (chronologically, capped at k_cap if given) that breaches either the
    stop or a target decides the outcome; if both breach on the same bar,
    the stop wins (conservative). Returns dict with outcome/max_r/realized_R/t_exit."""
    n = len(close)
    if atr is None or not np.isfinite(atr) or atr <= 0:
        return {"outcome": "NEITHER", "max_r": 0, "realized_R": np.nan, "t_exit": None}

    sign = 1.0 if direction == "long" else -1.0
    stop_price = entry - sign * ATR_STOP_MULT * atr
    target_prices = {r: entry + sign * r * atr for r in R_MULTIPLES}

    lo = t_anchor + 1
    hi = min(n - 1, t_anchor + (k_cap if k_cap else window))

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
            return {"outcome": "LOSS", "max_r": 0, "realized_R": -1.0, "t_exit": j}
        if max_r_this_bar > 0:
            return {"outcome": "WIN", "max_r": max_r_this_bar, "realized_R": float(max_r_this_bar), "t_exit": j}

    j_end = hi
    if j_end < lo:
        return {"outcome": "NEITHER", "max_r": 0, "realized_R": np.nan, "t_exit": None}
    mtm_r = (close[j_end] - entry) / atr * sign
    return {"outcome": "NEITHER", "max_r": 0, "realized_R": float(mtm_r), "t_exit": j_end}


def simple_forward_return(close: np.ndarray, t_anchor: int, k: int) -> tuple[float, str]:
    n = len(close)
    if t_anchor + k >= n:
        return np.nan, None
    entry = close[t_anchor]
    fwd = close[t_anchor + k]
    ret = (fwd - entry) / entry * 100.0 if entry > 0 else np.nan
    direction = "up" if ret > 0.02 else ("down" if ret < -0.02 else "flat")
    return ret, direction


def baseline_outcomes_for_k(close: np.ndarray, high: np.ndarray, low: np.ndarray, atr: np.ndarray,
                            valid_mask: np.ndarray, k: int, sample_every: int = 1,
                            seed: int = RNG_SEED) -> pd.DataFrame:
    """Random-direction baseline, same R-bracket, capped at k bars -- the
    'edge over doing nothing' reference for that specific K."""
    rng = np.random.default_rng(seed + k)
    idxs = np.where(valid_mask)[0][::sample_every]
    directions = rng.choice(["long", "short"], size=len(idxs))
    rows = []
    for i, i0 in enumerate(idxs):
        res = r_bracket_outcome(directions[i], close[i0], atr[i0], high, low, close, i0, k_cap=k)
        fwd_ret, fwd_dir = simple_forward_return(close, i0, k)
        rows.append({"idx": int(i0), "direction": directions[i], "fwd_return": fwd_ret,
                     "fwd_direction": fwd_dir, **res})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Stats helpers (reproduced from pattern_fulfillment_common.py / dome_leg_*)
# ---------------------------------------------------------------------------

def expectancy_stats(realized_r: pd.Series) -> dict:
    x = pd.Series(realized_r).dropna()
    n = len(x)
    if n == 0:
        return {"n": 0, "expectancy_R": np.nan, "ci_lo": np.nan, "ci_hi": np.nan, "win_rate": np.nan}
    mean = x.mean()
    se = x.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
    wins = x[x > 0]
    return {
        "n": int(n), "expectancy_R": float(mean),
        "ci_lo": float(mean - 1.96 * se) if n > 1 else np.nan,
        "ci_hi": float(mean + 1.96 * se) if n > 1 else np.nan,
        "win_rate": float(len(wins) / n),
    }


def welch_t_pvalue(a, b) -> float:
    a = pd.Series(a).dropna().to_numpy()
    b = pd.Series(b).dropna().to_numpy()
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return np.nan
    va, vb = a.var(ddof=1), b.var(ddof=1)
    se2 = va / na + vb / nb
    if se2 <= 0:
        return np.nan
    t = (a.mean() - b.mean()) / np.sqrt(se2)
    from math import erf, sqrt
    return float(2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2)))))


def permutation_test(a, b, n_perm: int = 2000, seed: int = RNG_SEED) -> tuple[float, float]:
    """Null: does shuffling which baseline-row pairs with which trigger-row
    change the mean DIFFERENCE as much as observed? Returns (real_diff, p)."""
    a = pd.Series(a).dropna().to_numpy()
    b = pd.Series(b).dropna().to_numpy()
    real_diff = float(a.mean() - b.mean())
    pool = np.concatenate([a, b])
    na = len(a)
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_perm)
    for i in range(n_perm):
        rng.shuffle(pool)
        diffs[i] = pool[:na].mean() - pool[na:].mean()
    p = float((np.abs(diffs) >= abs(real_diff)).mean())
    return real_diff, p


def bh_fdr(pvalues: pd.Series, q: float = BH_FDR_Q) -> pd.Series:
    valid = pvalues.dropna().sort_values()
    m = len(valid)
    if m == 0:
        return pd.Series(False, index=pvalues.index)
    ranks = np.arange(1, m + 1)
    thresh = ranks / m * q
    passed = valid.to_numpy() <= thresh
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
