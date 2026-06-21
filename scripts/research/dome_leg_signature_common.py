"""
dome_leg_signature_common.py
===============================
Shared config, DB/env bootstrap, and stats helpers for the dome/leg
early-signature study (research/dome-leg-signature branch).

FOUNDATION MEASUREMENT, not a predictor, not a trading signal. Continues
two open threads already in this codebase:
  1. The dome-symmetry audit (branch research/dome-symmetry, commit
     dbc98ee): swing_legs() in ta/patterns.py only ever detected the
     bullish up-leg ("dome": low->peak->correction); a symmetric down-leg
     detector ("bowl": high->trough->bounce) was designed and coded
     (commit 0535cdb) but never wired into pattern_memory or run on 5m.
  2. The original swing_leg commit's own stated open question (commit
     8aacd83): "do the first 2-5 bars predict the hump height &
     correction?" -- never answered.
  3. The user's own read-only exploration this session: candle geometry
     at confirmed swing tops/bottoms differs sharply from baseline
     (large, robust, replicates per-ticker) -- but a zero-look-ahead
     real-time shape filter does NOT translate that into a usable
     forward-return signal (consistent with the setup-formation v1/v2
     and pattern-fulfillment nulls already in this research arc).

This module/branch formalizes and re-verifies all three with a proper
walk-forward split, baseline comparison, and significance testing -- the
same discipline as the prior research phases.
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

# Swing-pivot fractal width -- structure.py's own default, reused as-is
# (same value used throughout this research arc).
PIVOT_WIDTH = 3

# A pivot only counts as a "significant" trend-change point if the move
# from the immediately preceding opposite-kind pivot is >= this many ATR14.
# Tried 2.0/2.5/3.0 during the exploratory pass; all gave the same
# qualitative picture. 2.5 used as the single reported value here.
AMP_MULT = 2.5

# Early-signature window (bars off the leg's start) -- same default the
# existing swing_legs()/swing_legs_down() use.
EARLY_N = 5

# Real-time shape filter thresholds (Part B) -- the multi-feature
# combination found, during exploration, to mark confirmed tops/bottoms:
# dominant wick + elevated range/ATR + elevated volume. Applied here with
# zero look-ahead, to every bar, not just confirmed pivots.
WICK_PCT_MIN = 30.0
RNG_ATR_MIN = 1.1
VOL_RATIO_MIN = 1.15

FORWARD_K_LIST = [3, 6, 12, 24]
TRAIN_FRACTION = 0.70
MIN_CELL_N = 30


def build_feature_frame(feat_df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=feat_df.index)
    rng = feat_df["candle_rng"]
    out["body_pct"] = feat_df["body_pct"]
    out["upper_wick_pct"] = feat_df["upper_wick"] / rng * 100.0
    out["lower_wick_pct"] = feat_df["lower_wick"] / rng * 100.0
    out["rng_atr_ratio"] = feat_df["candle_rng"] / feat_df["atr14"]
    out["vol_ratio"] = feat_df["vol_ratio"]
    out["close_loc"] = (feat_df["close"] - feat_df["low"]) / rng.replace(0, np.nan) * 100.0
    out["is_green"] = feat_df["is_green"]
    return out


def walk_forward_split_mask(n: int, train_fraction: float = TRAIN_FRACTION) -> np.ndarray:
    split_idx = int(n * train_fraction)
    return np.arange(n) < split_idx


def ci95_mean(x: pd.Series) -> dict:
    x = pd.Series(x).dropna()
    n = len(x)
    if n == 0:
        return {"n": 0, "mean": np.nan, "ci_lo": np.nan, "ci_hi": np.nan}
    m = x.mean()
    se = x.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
    return {"n": int(n), "mean": float(m),
            "ci_lo": float(m - 1.96 * se) if n > 1 else np.nan,
            "ci_hi": float(m + 1.96 * se) if n > 1 else np.nan}


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


def pearson_with_p(a, b) -> dict:
    """Pearson r + a Fisher z-transform normal-approx two-sided p-value."""
    a = np.asarray(a, float); b = np.asarray(b, float)
    mask = ~(np.isnan(a) | np.isnan(b))
    a, b = a[mask], b[mask]
    n = len(a)
    if n < 4:
        return {"r": np.nan, "n": n, "p": np.nan}
    r = float(np.corrcoef(a, b)[0, 1])
    r_clamped = max(min(r, 0.999999), -0.999999)
    z = np.arctanh(r_clamped)
    se = 1.0 / np.sqrt(n - 3)
    from math import erf, sqrt
    p = float(2 * (1 - 0.5 * (1 + erf(abs(z / se) / sqrt(2)))))
    return {"r": r, "n": n, "p": p}


def significant_pivots(piv, atr: np.ndarray, amp_mult: float = AMP_MULT) -> list:
    """Filter structure.swing_pivots() output to pivots where the move from
    the immediately preceding opposite-kind pivot is >= amp_mult * ATR14 at
    this pivot -- excludes noise-level zigzags, keeps real trend changes."""
    out, last_opp_price = [], None
    for p in piv:
        if last_opp_price is not None and not np.isnan(atr[p.idx]) and atr[p.idx] > 0:
            if abs(p.price - last_opp_price) >= amp_mult * atr[p.idx]:
                out.append(p)
        last_opp_price = p.price
    return out


def build_legs(sig_pivots: list, close: np.ndarray, early_n: int = EARLY_N) -> list[dict]:
    """Pairs consecutive significant pivots into legs: L->H = up-leg/dome,
    H->L = down-leg/bowl. Field semantics mirror atlas_research.ta.patterns
    ._legs()/swing_legs_down()/swing_legs_all() on branch
    research/dome-symmetry (commit 0535cdb, fully committed, not pushed to
    origin, not merged into fix/model-validity -- reproduced here rather
    than depending on an unmerged branch, same reasoning as v2/phase-3's
    reuse of feat/channels-and-5m).

    LOOK-AHEAD GUARD: leg geometry (start_idx, peak_idx, leg_amp, early_*)
    is established from the two pivots that define the leg itself (a, b),
    both already-confirmed by the time the leg exists. corr_depth/corr_bars
    derive from a THIRD pivot after the leg -- a forward OUTCOME (used only
    as a label for the "does the early signature predict the eventual
    correction" study), never as a feature.
    """
    legs = []
    for i in range(len(sig_pivots) - 1):
        a, b = sig_pivots[i], sig_pivots[i + 1]
        if a.kind == "L" and b.kind == "H":
            leg_dir = "up"
        elif a.kind == "H" and b.kind == "L":
            leg_dir = "down"
        else:
            continue
        if a.price <= 0:
            continue
        leg_amp = abs(b.price - a.price) / a.price
        leg_bars = b.idx - a.idx

        c = sig_pivots[i + 2] if i + 2 < len(sig_pivots) else None
        corr_depth = corr_bars = None
        if c is not None and b.price > 0:
            if leg_dir == "up" and c.kind == "L":
                corr_depth = (b.price - c.price) / b.price
                corr_bars = c.idx - b.idx
            elif leg_dir == "down" and c.kind == "H":
                corr_depth = (c.price - b.price) / b.price
                corr_bars = c.idx - b.idx

        e_end = min(a.idx + early_n, b.idx, len(close) - 1)
        early_gain = (close[e_end] - a.price) / a.price if leg_dir == "up" else (a.price - close[e_end]) / a.price
        early_bars = e_end - a.idx
        early_slope = (early_gain / early_bars) if early_bars else None

        legs.append(dict(
            leg_dir=leg_dir, start_idx=a.idx, peak_idx=b.idx,
            corr_idx=(c.idx if c is not None else None),
            leg_amp=float(leg_amp), leg_bars=int(leg_bars),
            corr_depth=(float(corr_depth) if corr_depth is not None else None),
            corr_bars=(int(corr_bars) if corr_bars is not None else None),
            early_gain=(float(early_gain) if early_gain is not None else None),
            early_bars=int(early_bars),
            early_slope=(float(early_slope) if early_slope is not None else None),
        ))
    return legs
