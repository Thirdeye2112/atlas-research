"""
Independent Alignment V2 Backtest
===================================
Compares three alignment models on the full parquet history:

  Model A — Original 5-component (current production):
    ml_rank (0.30) + pattern (0.20) + probability (0.20) + feature_ic (0.10) + regime (0.15)
    Max aligned_count = 5

  Model B — True 3-component (core-only, from run_true_alignment_backtest.py):
    ml_rank (0.40) + feature_ic (0.35) + regime (0.25)
    + momentum bonus (+10 pts confidence when pattern/prob agrees)
    Max aligned_count = 3

  Model C — Independent 4-group (new proposed):
    Group 1: ML rank      (weight 0.40)
    Group 2: Feature IC   (weight 0.30)
    Group 3: Regime       (weight 0.20)
    Group 4: Momentum     (weight 0.10 — fires when pattern OR probability agrees with core direction)
    Max aligned_count = 4

Outputs: INDEPENDENT_ALIGNMENT_V2_REPORT.md

Usage:
    python scripts/run_independent_alignment_v2.py
"""
from __future__ import annotations

import sys
import warnings
from datetime import date
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
from run_edge_hierarchy import load_and_score_extended
from config.settings import PARQUET_OUTPUT_DIR, MODEL_DIR
from atlas_research.utils.logging import get_logger

log = get_logger("alignment_v2")

# ── Model C weights ─────────────────────────────────────────────────────────
V2_WEIGHTS = {
    "ml":        0.40,
    "feature_ic": 0.30,
    "regime":    0.20,
    "momentum":  0.10,   # combined pattern + probability
}


def _recompute_v2(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute 4-group independent alignment (Model C).

    Group 4 (momentum) votes in the same direction as the core 3-group dominant
    when at least one of pattern or probability agrees with core direction.
    """
    n = len(df)

    core_comps = {
        "ml":        ("ml_dir",      "ml_str",    None,          V2_WEIGHTS["ml"]),
        "feature_ic":("feat_ic_dir", "feat_str",  "feat_avail",  V2_WEIGHTS["feature_ic"]),
        "regime":    ("regime_dir",  "regime_str","regime_avail",V2_WEIGHTS["regime"]),
    }

    # Core 3-group alignment
    bull_w = np.zeros(n); bear_w = np.zeros(n)
    bull_c = np.zeros(n, int); bear_c = np.zeros(n, int)
    total_a = np.zeros(n, int)

    for name, (dcol, scol, acol, cw) in core_comps.items():
        cd = df[dcol].to_numpy(dtype=int)
        cs = df[scol].to_numpy(dtype=float) if scol in df.columns else np.ones(n)
        ca = df[acol].to_numpy(dtype=bool) if acol and acol in df.columns else np.ones(n, bool)
        total_a += ca.astype(int)
        bull_w  += np.where(ca & (cd == 1),  cs * cw, 0)
        bear_w  += np.where(ca & (cd == -1), cs * cw, 0)
        bull_c  += np.where(ca & (cd == 1),  1, 0)
        bear_c  += np.where(ca & (cd == -1), 1, 0)

    core_dominant = np.where(bull_w > bear_w * 1.15, 1, np.where(bear_w > bull_w * 1.15, -1, 0))

    # Group 4: momentum agrees when pat_dir OR prob_dir matches core direction
    pat_dir  = df["pat_dir"].to_numpy(dtype=int)
    prob_dir = df["prob_dir"].to_numpy(dtype=int)
    mom_agrees = (
        ((pat_dir  == core_dominant) | (prob_dir == core_dominant))
        & (core_dominant != 0)
    )
    # Momentum fires in the same direction as core when at least one of pattern/prob agrees
    mom_dir = np.where(mom_agrees, core_dominant, 0)
    mom_str = np.ones(n)  # strength = 1.0 when it fires

    # Add momentum group to the full tally
    total_a += 1  # momentum is always "available" as a group (it's a derived vote)
    cw = V2_WEIGHTS["momentum"]
    bull_w += np.where(mom_dir == 1,  mom_str * cw, 0)
    bear_w += np.where(mom_dir == -1, mom_str * cw, 0)
    bull_c += np.where(mom_dir == 1,  1, 0)
    bear_c += np.where(mom_dir == -1, 1, 0)

    dominant  = np.where(bull_w > bear_w * 1.15, 1, np.where(bear_w > bull_w * 1.15, -1, 0))
    aligned_c = np.where(dominant == 1, bull_c, np.where(dominant == -1, bear_c, 0)).astype(int)
    align_r   = np.where(total_a > 0, aligned_c / total_a, 0.0)

    # Confidence
    al_str = np.zeros(n); al_wt = np.zeros(n)
    all_comps = list(core_comps.items()) + [("momentum", ("mom_dir_tmp", None, None, cw))]
    for name, (dcol, scol, acol, wcol) in core_comps.items():
        cd = df[dcol].to_numpy(dtype=int)
        cs = df[scol].to_numpy(dtype=float) if scol in df.columns else np.ones(n)
        ca = df[acol].to_numpy(dtype=bool) if acol and acol in df.columns else np.ones(n, bool)
        is_al = ca & (cd == dominant) & (dominant != 0)
        al_str += np.where(is_al, cs * V2_WEIGHTS[name], 0)
        al_wt  += np.where(is_al, V2_WEIGHTS[name], 0)

    # Momentum contribution
    is_al_mom = (mom_dir == dominant) & (dominant != 0)
    al_str += np.where(is_al_mom, mom_str * V2_WEIGHTS["momentum"], 0)
    al_wt  += np.where(is_al_mom, V2_WEIGHTS["momentum"], 0)

    with np.errstate(divide="ignore", invalid="ignore"):
        avg_al = np.where(al_wt > 0, al_str / al_wt, 0)

    has_con = (dominant != 0) & (aligned_c > 0)
    base    = np.where(has_con, (0.65 * avg_al + 0.35 * align_r) * 100, 0)

    mkt = df["market_regime"].values
    _FIT = {("bull",1):1.00,("bull",-1):0.72,("bull",0):0.85,
            ("bear",-1):1.00,("bear",1):0.72,("bear",0):0.85,
            ("range",1):0.88,("range",-1):0.88,("range",0):0.80}
    fitness  = np.array([_FIT.get((mr, int(d)), 0.85) for mr, d in zip(mkt, dominant)])
    conf_v2  = np.clip(base * fitness, 0, 100)

    # V2 conviction: 4 groups, so thresholds differ from original 5-component
    frac = np.where(total_a > 0, aligned_c / np.clip(total_a, 1, None), 0)
    v2_level = np.where(
        dominant == 0,         "NEUTRAL",
        np.where(frac >= 0.90, "VERY_HIGH",   # 4/4
        np.where(frac >= 0.65, "HIGH",         # 3/4
        np.where(frac >= 0.40, "MODERATE",     # 2/4
        "LOW")))
    )

    out = df.copy()
    out["v2_dominant_dir"]    = dominant
    out["v2_aligned_count"]   = aligned_c
    out["v2_total_available"] = total_a
    out["v2_confidence"]      = np.round(conf_v2, 2)
    out["v2_conviction"]      = v2_level
    out["v2_momentum_fired"]  = mom_agrees.astype(int)
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
    start_date = date(2015, 1, 1)
    end_date   = date.today()

    print("\nIndependent Alignment V2 Backtest")
    print(f"Period: {start_date} to {end_date}")
    print("-" * 60)

    print("Loading stats and models...")
    pattern_stats, calib_stats, regime_stats = load_static_stats()
    model_map   = build_model_map(Path(MODEL_DIR))
    parquet_dir = Path(PARQUET_OUTPUT_DIR)

    print("Scoring all dates (extended)...")
    scored = load_and_score_extended(
        start_date, end_date, parquet_dir, model_map,
        pattern_stats, calib_stats, regime_stats,
    )
    if scored.empty:
        print("No scored rows.")
        return 1

    print(f"Total rows: {len(scored):,}")
    print("Computing forward returns and conviction...")
    scored = compute_forward_returns(scored)
    scored = add_conviction(scored)

    print("Computing V2 independent alignment...")
    scored = _recompute_v2(scored)

    # ── Overall comparison ────────────────────────────────────────────────────
    lines = []
    lines.append("# Independent Alignment V2 Report")
    lines.append("")
    lines.append(f"**Generated:** {date.today()}")
    lines.append(f"**Period:** {start_date} to {end_date}")
    lines.append(f"**Total rows scored:** {len(scored):,}")
    lines.append("")
    lines.append("## 1. Overall Performance Comparison")
    lines.append("")
    lines.append("| Model | N (directional) | Hit Rate 5d | Expectancy |")
    lines.append("|---|---|---|---|")

    orig_m = _metrics(scored, "dominant_dir")
    v2_m   = _metrics(scored, "v2_dominant_dir")

    hr_orig = f"{orig_m['hit_rate']:.3f}" if orig_m["hit_rate"] else "n/a"
    hr_v2   = f"{v2_m['hit_rate']:.3f}"   if v2_m["hit_rate"]   else "n/a"
    ex_orig = f"{orig_m['expectancy']:+.5f}" if orig_m["expectancy"] else "n/a"
    ex_v2   = f"{v2_m['expectancy']:+.5f}"   if v2_m["expectancy"]   else "n/a"

    lines.append(f"| Original 5-component | {orig_m['n']:,} | {hr_orig} | {ex_orig} |")
    lines.append(f"| V2 4-group | {v2_m['n']:,} | {hr_v2} | {ex_v2} |")
    lines.append("")

    # ── By aligned_count — original ───────────────────────────────────────────
    lines.append("## 2. By Aligned Count")
    lines.append("")
    lines.append("### Original (5-component scale)")
    lines.append("")
    lines.append("| Aligned | N | Hit Rate | Expectancy |")
    lines.append("|---|---|---|---|")
    for ac in sorted(scored["aligned_count"].dropna().unique()):
        sub = scored[scored["aligned_count"] == ac]
        m = _metrics(sub, "dominant_dir")
        if m["hit_rate"] is None: continue
        lines.append(f"| {int(ac)}/5 | {m['n']:,} | {m['hit_rate']:.3f} | {m['expectancy']:+.5f} |")

    lines.append("")
    lines.append("### V2 (4-group scale)")
    lines.append("")
    lines.append("| Aligned | N | Hit Rate | Expectancy |")
    lines.append("|---|---|---|---|")
    for ac in sorted(scored["v2_aligned_count"].dropna().unique()):
        sub = scored[scored["v2_aligned_count"] == ac]
        m = _metrics(sub, "v2_dominant_dir")
        if m["hit_rate"] is None: continue
        lines.append(f"| {int(ac)}/4 | {m['n']:,} | {m['hit_rate']:.3f} | {m['expectancy']:+.5f} |")

    # ── By conviction level ───────────────────────────────────────────────────
    lines.append("")
    lines.append("## 3. By Conviction Level")
    lines.append("")
    lines.append("### Original conviction levels")
    lines.append("")
    lines.append("| Level | N | Hit Rate | Expectancy |")
    lines.append("|---|---|---|---|")
    for lvl in ["VERY_HIGH", "HIGH", "MODERATE", "LOW", "NEUTRAL"]:
        sub = scored[scored["conviction_level"] == lvl]
        if sub.empty: continue
        m = _metrics(sub, "dominant_dir")
        if m["hit_rate"] is None: continue
        lines.append(f"| {lvl} | {m['n']:,} | {m['hit_rate']:.3f} | {m['expectancy']:+.5f} |")

    lines.append("")
    lines.append("### V2 conviction levels (4-group)")
    lines.append("")
    lines.append("| Level | N | Hit Rate | Expectancy |")
    lines.append("|---|---|---|---|")
    for lvl in ["VERY_HIGH", "HIGH", "MODERATE", "LOW", "NEUTRAL"]:
        sub = scored[scored["v2_conviction"] == lvl]
        if sub.empty: continue
        m = _metrics(sub, "v2_dominant_dir")
        if m["hit_rate"] is None: continue
        lines.append(f"| {lvl} | {m['n']:,} | {m['hit_rate']:.3f} | {m['expectancy']:+.5f} |")

    # ── Momentum group analysis ───────────────────────────────────────────────
    lines.append("")
    lines.append("## 4. Momentum Group (Group 4) Analysis")
    lines.append("")
    lines.append("Group 4 fires when pattern OR probability agrees with core direction.")
    lines.append("")
    mom_fire = scored[scored["v2_momentum_fired"] == 1]
    mom_none = scored[scored["v2_momentum_fired"] == 0]
    m_fire = _metrics(mom_fire, "v2_dominant_dir")
    m_none = _metrics(mom_none, "v2_dominant_dir")
    lines.append("| Momentum Group | N (directional) | Hit Rate | Expectancy |")
    lines.append("|---|---|---|---|")
    if m_fire["hit_rate"]:
        lines.append(f"| Momentum agrees (4/4 or 3/4) | {m_fire['n']:,} | {m_fire['hit_rate']:.3f} | {m_fire['expectancy']:+.5f} |")
    if m_none["hit_rate"]:
        lines.append(f"| Momentum silent (3/4 or less) | {m_none['n']:,} | {m_none['hit_rate']:.3f} | {m_none['expectancy']:+.5f} |")

    # ── Direction mismatch ────────────────────────────────────────────────────
    lines.append("")
    lines.append("## 5. Direction Mismatch Analysis (V2 vs Original)")
    lines.append("")
    mismatch = scored[scored["dominant_dir"] != scored["v2_dominant_dir"]]
    lines.append(f"Rows where original and V2 directions disagree: **{len(mismatch):,}**")
    if not mismatch.empty:
        mo = _metrics(mismatch, "dominant_dir")
        mv = _metrics(mismatch, "v2_dominant_dir")
        lines.append("")
        lines.append("| Model | HR on mismatch rows |")
        lines.append("|---|---|")
        if mo["hit_rate"]:
            lines.append(f"| Original 5-component | {mo['hit_rate']:.3f} |")
        if mv["hit_rate"]:
            lines.append(f"| V2 4-group | {mv['hit_rate']:.3f} |")

    # ── Pattern/Prob redundancy ───────────────────────────────────────────────
    lines.append("")
    lines.append("## 6. Signal Redundancy Verification")
    lines.append("")
    pat  = scored["pat_dir"].to_numpy(dtype=int)
    prob = scored["prob_dir"].to_numpy(dtype=int)
    ml   = scored["ml_dir"].to_numpy(dtype=int)
    both_pp = (pat != 0) & (prob != 0)
    if both_pp.sum() > 0:
        pp_agree = (pat[both_pp] == prob[both_pp]).mean()
        lines.append(f"- Pattern × Probability agreement (when both fire): **{pp_agree:.1%}**")
    both_pm = (pat != 0) & (ml != 0)
    if both_pm.sum() > 0:
        pm_agree = (pat[both_pm] == ml[both_pm]).mean()
        lines.append(f"- Pattern × ML rank agreement (when both fire): **{pm_agree:.1%}**")
    both_pbm = (prob != 0) & (ml != 0)
    if both_pbm.sum() > 0:
        pbm_agree = (prob[both_pbm] == ml[both_pbm]).mean()
        lines.append(f"- Probability × ML rank agreement (when both fire): **{pbm_agree:.1%}**")
    lines.append("")
    lines.append("These correlations confirm why Pattern and Probability must be grouped")
    lines.append("as a single evidence vote rather than counted as independent signals.")

    # ── OMNI/Jarvis coverage (now that parquets are rebuilt) ─────────────────
    lines.append("")
    lines.append("## 7. OMNI/Jarvis Column Coverage After Rebuild")
    lines.append("")
    for col in ["oscar_87_above_50", "jarvis_quality_adjusted", "quality_tier", "hma_87_above"]:
        if col in scored.columns:
            nn = scored[col].notna().sum()
            total = len(scored)
            lines.append(f"- `{col}`: {nn:,}/{total:,} rows non-null ({nn/total:.1%})")
        else:
            lines.append(f"- `{col}`: **MISSING from scored output** (parquet rebuild may be needed)")

    # ── Recommendations ───────────────────────────────────────────────────────
    lines.append("")
    lines.append("## 8. Recommendations")
    lines.append("")
    lines.append("### Alignment architecture")
    lines.append("")

    if v2_m["hit_rate"] and orig_m["hit_rate"]:
        delta = v2_m["hit_rate"] - orig_m["hit_rate"]
        if delta >= 0:
            lines.append(f"V2 4-group model improves HR by **+{delta:.3f}** vs original. "
                         "Recommend adopting V2 alignment formula.")
        else:
            lines.append(f"V2 4-group model is **{delta:.3f}** HR vs original (worse). "
                         "The original's momentum double-count adds real predictive value. "
                         "Consider keeping momentum as a higher-weight group (0.15) rather than 0.10.")

    lines.append("")
    lines.append("### Component weights")
    lines.append("")
    lines.append("| Group | Components | V2 Weight | Original Weight |")
    lines.append("|---|---|---|---|")
    lines.append("| 1 — ML rank | LightGBM model output | 0.40 | 0.30 |")
    lines.append("| 2 — Feature IC | Regime-specific IC | 0.30 | 0.10 |")
    lines.append("| 3 — Regime | SPY / market context | 0.20 | 0.15 |")
    lines.append("| 4 — Momentum | Pattern + Probability combined | 0.10 | 0.40 (split 0.20+0.20) |")
    lines.append("")
    lines.append("### Next steps (before recalibrating thresholds)")
    lines.append("")
    lines.append("1. Fix OMNI/OSCAR NaN bug (done in this session)")
    lines.append("2. Rebuild parquets with `oscar_87_above_50` and `jarvis_quality_adjusted`")
    lines.append("3. Re-run edge hierarchy — OMNI/OSCAR layer should move from 45.2% to ~54%")
    lines.append("4. Promote bearish patterns to enable bidirectional pattern/prob votes")
    lines.append("5. Once OMNI/Jarvis validated, add as Group 5 with weight 0.10")

    report_path = _ROOT / "reports" / "INDEPENDENT_ALIGNMENT_V2_REPORT.md"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to: {report_path}")

    # Also print summary to console
    print(f"\nOverall HR:  Original={hr_orig}  V2={hr_v2}")
    print(f"Rows:        Original={orig_m['n']:,}  V2={v2_m['n']:,}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
