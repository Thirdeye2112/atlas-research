"""
True Independent Alignment Backtest
====================================
Re-scores confluence using only genuinely independent, bidirectional components:
  - ML rank (0.40 weight)
  - Feature IC (0.35 weight)
  - Regime (0.25 weight)

Pattern and probability are demoted to a supplementary momentum bias:
  +0.10 confidence bonus (not a vote) when they agree with core direction.

Compares 5-component (original) vs 3-component (true independent) alignment:
  - Hit rate at each aligned_count bucket
  - Conviction level distribution
  - HR delta by conviction level

Usage:
    python scripts/run_true_alignment_backtest.py
"""
from __future__ import annotations

import sys
import warnings
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

from run_confluence_backtest import (
    load_static_stats,
    build_model_map,
    compute_forward_returns,
    HORIZONS,
    MIN_SAMPLE,
    WEIGHTS,
)
from run_conviction_backtest import add_conviction
from run_edge_hierarchy import (
    load_and_score_extended,
)
from config.settings import PARQUET_OUTPUT_DIR, MODEL_DIR
from atlas_research.utils.logging import get_logger

log = get_logger("true_alignment")

# ── True independent weights ─────────────────────────────────────────────────
TRUE_WEIGHTS = {
    "ml":        0.40,
    "feature_ic": 0.35,
    "regime":    0.25,
}

MOMENTUM_BONUS = 0.10  # applied to confluence_score (not a vote)

# ── Conviction thresholds (recalibrated for 3-component max) ─────────────────
# With max aligned=3: VERY_HIGH=3 aligned, HIGH=2, MODERATE=1
TRUE_CONVICTION_THRESHOLDS = {
    "VERY_HIGH": 0.75,   # 3/3 aligned
    "HIGH":      0.55,   # 2/3 aligned
    "MODERATE":  0.35,   # 1/3 aligned
}


def _recompute_true_alignment(df: pd.DataFrame) -> pd.DataFrame:
    """
    Re-compute alignment using only ml_rank, feature_ic, regime.
    Pattern and probability become a supplementary momentum bonus.
    """
    n = len(df)

    comps = {
        "ml":        ("ml_dir",      "ml_str",    None,          TRUE_WEIGHTS["ml"]),
        "feature_ic":("feat_ic_dir", "feat_str",  "feat_avail",  TRUE_WEIGHTS["feature_ic"]),
        "regime":    ("regime_dir",  "regime_str","regime_avail",TRUE_WEIGHTS["regime"]),
    }

    bull_w = np.zeros(n); bear_w = np.zeros(n)
    bull_c = np.zeros(n, int); bear_c = np.zeros(n, int)
    total_a = np.zeros(n, int)

    for name, (dcol, scol, acol, cw) in comps.items():
        cd = df[dcol].to_numpy(dtype=int)
        cs = df[scol].to_numpy(dtype=float) if scol in df.columns else np.ones(n)
        ca = df[acol].to_numpy(dtype=bool) if acol and acol in df.columns else np.ones(n, bool)
        total_a += ca.astype(int)
        bull_w  += np.where(ca & (cd == 1),  cs * cw, 0)
        bear_w  += np.where(ca & (cd == -1), cs * cw, 0)
        bull_c  += np.where(ca & (cd == 1),  1, 0)
        bear_c  += np.where(ca & (cd == -1), 1, 0)

    dominant   = np.where(bull_w > bear_w * 1.15, 1, np.where(bear_w > bull_w * 1.15, -1, 0))
    aligned_c  = np.where(dominant == 1, bull_c, np.where(dominant == -1, bear_c, 0)).astype(int)
    align_r    = np.where(total_a > 0, aligned_c / total_a, 0.0)

    # Compute base confidence
    al_str = np.zeros(n); al_wt = np.zeros(n)
    for name, (dcol, scol, acol, cw) in comps.items():
        cd = df[dcol].to_numpy(dtype=int)
        cs = df[scol].to_numpy(dtype=float) if scol in df.columns else np.ones(n)
        ca = df[acol].to_numpy(dtype=bool) if acol and acol in df.columns else np.ones(n, bool)
        is_al = ca & (cd == dominant) & (dominant != 0)
        al_str += np.where(is_al, cs * cw, 0)
        al_wt  += np.where(is_al, cw, 0)

    with np.errstate(divide="ignore", invalid="ignore"):
        avg_al = np.where(al_wt > 0, al_str / al_wt, 0)

    has_con = (dominant != 0) & (aligned_c > 0)
    base    = np.where(has_con, (0.65 * avg_al + 0.35 * align_r) * 100, 0)

    # Regime fitness
    mkt = df["market_regime"].values
    _FIT = {("bull",1):1.00,("bull",-1):0.72,("bull",0):0.85,
            ("bear",-1):1.00,("bear",1):0.72,("bear",0):0.85,
            ("range",1):0.88,("range",-1):0.88,("range",0):0.80}
    fitness = np.array([_FIT.get((mr, int(d)), 0.85) for mr, d in zip(mkt, dominant)])
    conf    = base * fitness

    # Momentum bias bonus: when pattern and/or probability agree with dominant
    pat_agrees  = (df["pat_dir"].to_numpy(dtype=int)  == dominant) & (dominant != 0)
    prob_agrees = (df["prob_dir"].to_numpy(dtype=int) == dominant) & (dominant != 0)
    bonus       = np.where(pat_agrees | prob_agrees, MOMENTUM_BONUS * 100, 0)
    conf_final  = np.clip(conf + bonus, 0, 100)

    # Conviction using true 3-component thresholds
    # Score: aligned_count/3 mapped to level
    frac = np.where(total_a > 0, aligned_c / np.clip(total_a, 1, None), 0)
    true_level = np.where(
        (dominant == 0),         "NEUTRAL",
        np.where(frac >= 0.75,  "VERY_HIGH",
        np.where(frac >= 0.55,  "HIGH",
        np.where(frac >= 0.35,  "MODERATE",
        "LOW")))
    )

    out = df.copy()
    out["true_dominant_dir"]   = dominant
    out["true_aligned_count"]  = aligned_c
    out["true_total_available"]= total_a
    out["true_confidence"]     = np.round(conf_final, 2)
    out["true_conviction"]     = true_level
    return out


def _metrics(df: pd.DataFrame, dir_col: str, fwd_col: str = "fwd_5d") -> dict:
    dirs = df[dir_col].to_numpy(dtype=int)
    rets = df[fwd_col].to_numpy(dtype=float)
    mask = (dirs != 0) & ~np.isnan(rets)
    if mask.sum() < MIN_SAMPLE:
        return {"n": int(mask.sum()), "hit_rate": None, "expectancy": None}
    d = dirs[mask]; r = rets[mask]
    return {
        "n":          int(mask.sum()),
        "hit_rate":   round(float((d * r > 0).mean()), 4),
        "expectancy": round(float(r.mean()), 6),
    }


def main() -> int:
    from datetime import date
    start_date = date(2015, 1, 1)
    end_date   = date.today()

    print("\nTrue Independent Alignment Backtest")
    print(f"Period: {start_date} to {end_date}")
    print("-" * 60)

    print("\nLoading stats and models...")
    pattern_stats, calib_stats, regime_stats = load_static_stats()
    model_map   = build_model_map(Path(MODEL_DIR))
    parquet_dir = Path(PARQUET_OUTPUT_DIR)

    print("Scoring all dates (extended)...")
    scored = load_and_score_extended(
        start_date, end_date, parquet_dir, model_map,
        pattern_stats, calib_stats, regime_stats,
    )
    if scored.empty:
        print("No scored rows. Aborting.")
        return 1

    print("Computing forward returns...")
    scored = compute_forward_returns(scored)
    scored = add_conviction(scored)

    print("Recomputing true alignment...")
    scored = _recompute_true_alignment(scored)

    # ── Comparison: Original 5-component vs True 3-component ─────────────────
    print("\n" + "=" * 60)
    print("ORIGINAL (5-component) vs TRUE INDEPENDENT (3-component)")
    print("=" * 60)

    orig_m = _metrics(scored, "dominant_dir")
    true_m = _metrics(scored, "true_dominant_dir")
    print(f"\n{'':30s} {'N':>8s}  {'HR':>6s}  {'Exp':>8s}")
    print(f"{'Original confluence':30s} {orig_m['n']:>8,}  {orig_m['hit_rate']:.3f}  {orig_m['expectancy']:+.5f}" if orig_m['hit_rate'] else "Original: insufficient data")
    print(f"{'True independent':30s} {true_m['n']:>8,}  {true_m['hit_rate']:.3f}  {true_m['expectancy']:+.5f}" if true_m['hit_rate'] else "True: insufficient data")

    # ── By aligned count bucket ───────────────────────────────────────────────
    print("\nORIGINAL — By aligned_count (5-component scale):")
    for ac in sorted(scored["aligned_count"].unique()):
        sub = scored[scored["aligned_count"] == ac]
        m   = _metrics(sub, "dominant_dir")
        if m["hit_rate"] is None: continue
        print(f"  aligned={ac}: n={m['n']:>7,}  HR={m['hit_rate']:.3f}  exp={m['expectancy']:+.5f}")

    print("\nTRUE INDEPENDENT — By aligned_count (3-component scale):")
    for ac in sorted(scored["true_aligned_count"].unique()):
        sub = scored[scored["true_aligned_count"] == ac]
        m   = _metrics(sub, "true_dominant_dir")
        if m["hit_rate"] is None: continue
        print(f"  aligned={ac}: n={m['n']:>7,}  HR={m['hit_rate']:.3f}  exp={m['expectancy']:+.5f}")

    # ── By conviction level ───────────────────────────────────────────────────
    print("\nORIGINAL — By conviction_level:")
    for lvl in ["VERY_HIGH", "HIGH", "MODERATE", "LOW", "NEUTRAL"]:
        sub = scored[scored["conviction_level"] == lvl]
        if sub.empty: continue
        m = _metrics(sub, "dominant_dir")
        if m["hit_rate"] is None: continue
        print(f"  {lvl:12s}: n={m['n']:>7,}  HR={m['hit_rate']:.3f}  exp={m['expectancy']:+.5f}")

    print("\nTRUE INDEPENDENT — By true_conviction:")
    for lvl in ["VERY_HIGH", "HIGH", "MODERATE", "LOW", "NEUTRAL"]:
        sub = scored[scored["true_conviction"] == lvl]
        if sub.empty: continue
        m = _metrics(sub, "true_dominant_dir")
        if m["hit_rate"] is None: continue
        print(f"  {lvl:12s}: n={m['n']:>7,}  HR={m['hit_rate']:.3f}  exp={m['expectancy']:+.5f}")

    # ── Direction mismatch ────────────────────────────────────────────────────
    print("\nDIRECTION DISAGREEMENT (orig != true):")
    mismatch = scored[scored["dominant_dir"] != scored["true_dominant_dir"]]
    if not mismatch.empty:
        m_orig = _metrics(mismatch, "dominant_dir")
        m_true = _metrics(mismatch, "true_dominant_dir")
        print(f"  Mismatch rows: {len(mismatch):,}")
        print(f"  Original direction HR on mismatch: {m_orig['hit_rate']:.3f}" if m_orig['hit_rate'] else "  Original: insufficient")
        print(f"  True direction HR on mismatch:     {m_true['hit_rate']:.3f}" if m_true['hit_rate'] else "  True: insufficient")
    else:
        print("  No direction mismatches (true independent and original agree on direction for all rows)")

    # ── Correlation check ─────────────────────────────────────────────────────
    pat_dir = scored["pat_dir"].to_numpy(dtype=int)
    prob_dir = scored["prob_dir"].to_numpy(dtype=int)
    both_fire = (pat_dir != 0) & (prob_dir != 0)
    if both_fire.sum() > 0:
        agree = (pat_dir[both_fire] == prob_dir[both_fire]).mean()
        print(f"\nPATTERN × PROBABILITY agreement (when both fire): {agree:.3f}")

    pat_ml = (pat_dir != 0) & (scored["ml_dir"].to_numpy(dtype=int) != 0)
    if pat_ml.sum() > 0:
        agree_ml = (pat_dir[pat_ml] == scored["ml_dir"].to_numpy(dtype=int)[pat_ml]).mean()
        print(f"PATTERN × ML_RANK agreement (when both fire):    {agree_ml:.3f}")

    prob_ml = (prob_dir != 0) & (scored["ml_dir"].to_numpy(dtype=int) != 0)
    if prob_ml.sum() > 0:
        agree_prob_ml = (prob_dir[prob_ml] == scored["ml_dir"].to_numpy(dtype=int)[prob_ml]).mean()
        print(f"PROBABILITY × ML_RANK agreement (when both fire):{agree_prob_ml:.3f}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
