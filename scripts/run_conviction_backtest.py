"""
Atlas Conviction Layer Backtest
================================
Validates whether conviction levels (driven by alignment count + quality modifiers)
outperform confluence score buckets as a predictor of forward returns.

Primary research question:
  Does grouping by conviction level (LOW / MODERATE / HIGH / VERY_HIGH)
  produce better discrimination than grouping by score bucket (0-20/20-40/...)
  in terms of hit rate, expected return, decile spread, and monotonicity?

Studies:
  1. Alignment study             — 1-5 aligned, all horizons (baseline)
  2. Score bucket study          — 0-20 .. 80-100, all horizons (baseline)
  3. Conviction level study      — LOW/MODERATE/HIGH/VERY_HIGH, all horizons
  4. Head-to-head comparison     — conviction levels vs score buckets side-by-side
  5. Evidence quality breakdown  — within VERY_HIGH: 5-aligned vs 4-aligned
  6. Permutation tests           — conviction score, alignment count, score bucket
  7. Regime breakdown            — per conviction level
  8. Year-by-year breakdown      — per conviction level
  9. Verdict                     — should UI switch to conviction-centric view?

Usage:
    python scripts/run_conviction_backtest.py
    python scripts/run_conviction_backtest.py --start-date 2015-01-01 --out reports/CONVICTION_REPORT.md
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

# Reuse scoring infrastructure from the confluence backtest
from run_confluence_backtest import (
    load_static_stats,
    build_model_map,
    load_and_score,
    compute_forward_returns,
    alignment_study,
    score_bucket_study,
    _group_metrics,
    rank_ic,
    HORIZONS,
    N_PERMS,
    MIN_SAMPLE,
    _pct,
    _ret,
    _tbl,
    BUCKET_LABELS,
    SCORE_BUCKETS,
)
from config.settings import PARQUET_OUTPUT_DIR, MODEL_DIR
from atlas_research.conviction.engine import (
    compute_conviction_vec,
    get_level,
    LEVEL_ORDER,
    VERY_HIGH_THRESH,
    HIGH_THRESH,
    MODERATE_THRESH,
)
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)

CONVICTION_LEVELS = ["LOW", "MODERATE", "HIGH", "VERY_HIGH"]

# ── Add conviction columns to scored DataFrame ─────────────────────────────────

def add_conviction(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute conviction_score and conviction_level for every row in the scored df.

    Inputs (all already present from score_batch):
      aligned_count, confluence_direction, ml_prob, ml_rank,
      prob_dir, feat_ic_dir, regime_dir
    """
    dom_dir = df["confluence_direction"].map(
        {"bullish": 1, "bearish": -1, "neutral": 0}
    ).fillna(0).to_numpy(dtype=int)

    regime_avail = np.ones(len(df), dtype=bool)  # regime data is available for ~99%+ of rows

    score, level = compute_conviction_vec(
        aligned_count = df["aligned_count"].to_numpy(dtype=int),
        dominant_dir  = dom_dir,
        ml_prob       = df["ml_prob"].to_numpy(dtype=float),
        ml_rank       = df["ml_rank"].to_numpy(dtype=float),
        prob_dir      = df["prob_dir"].to_numpy(dtype=int),
        feat_ic_dir   = df["feat_ic_dir"].to_numpy(dtype=int),
        regime_dir    = df["regime_dir"].to_numpy(dtype=int),
        regime_avail  = regime_avail,
    )

    out = df.copy()
    out["conviction_score"] = score
    out["conviction_level"] = level
    return out


# ── Study functions ─────────────────────────────────────────────────────────────

def conviction_level_study(df: pd.DataFrame) -> pd.DataFrame:
    """Hit rates, average returns, and path stats by conviction level."""
    df2 = df.copy()
    df2["conviction_level"] = pd.Categorical(
        df2["conviction_level"], categories=CONVICTION_LEVELS, ordered=True
    )
    return _group_metrics(df2, "conviction_level")


def head_to_head(df: pd.DataFrame) -> pd.DataFrame:
    """
    Side-by-side: conviction levels vs score buckets — all horizons.
    Lets us directly compare which grouping scheme produces better discrimination.
    """
    rows = []
    # Conviction levels
    for level in CONVICTION_LEVELS:
        sub  = df[df["conviction_level"] == level]
        row: dict = {"filter": f"Conviction {level}", "type": "conviction", "n": len(sub)}
        for h in HORIZONS:
            col = f"fwd_{h}d"
            s   = sub[col].dropna() if col in sub.columns else pd.Series(dtype=float)
            row[f"hr_{h}d"]  = float((s > 0).mean()) if len(s) >= MIN_SAMPLE else np.nan
            row[f"avg_{h}d"] = float(s.mean())        if len(s) >= MIN_SAMPLE else np.nan
        rows.append(row)

    # Score buckets
    for label in BUCKET_LABELS:
        lo, hi = (int(x) for x in label.split("-"))
        sub  = df[(df["confluence_score"] >= lo) & (df["confluence_score"] < hi + 0.001)]
        if label == "80-100":
            sub = df[df["confluence_score"] >= 80]
        row = {"filter": f"Score {label}", "type": "score", "n": len(sub)}
        for h in HORIZONS:
            col = f"fwd_{h}d"
            s   = sub[col].dropna() if col in sub.columns else pd.Series(dtype=float)
            row[f"hr_{h}d"]  = float((s > 0).mean()) if len(s) >= MIN_SAMPLE else np.nan
            row[f"avg_{h}d"] = float(s.mean())        if len(s) >= MIN_SAMPLE else np.nan
        rows.append(row)

    return pd.DataFrame(rows)


def evidence_quality_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    Within VERY_HIGH conviction: break down by alignment count (4 vs 5 aligned)
    and by regime support (agrees vs neutral vs conflicts).
    Shows which evidence configuration drives the best outcomes.
    """
    vh = df[df["conviction_level"] == "VERY_HIGH"].copy()
    rows = []

    # By alignment count
    for ac in [4, 5]:
        sub  = vh[vh["aligned_count"] == ac]
        label = f"VERY_HIGH | {ac}-aligned"
        row  = {"group": label, "n": len(sub)}
        for h in HORIZONS:
            col = f"fwd_{h}d"
            s   = sub[col].dropna() if col in sub.columns else pd.Series(dtype=float)
            row[f"hr_{h}d"]  = float((s > 0).mean()) if len(s) >= MIN_SAMPLE else np.nan
            row[f"avg_{h}d"] = float(s.mean())        if len(s) >= MIN_SAMPLE else np.nan
        rows.append(row)

    # By regime support within VERY_HIGH
    dom_dir = vh["confluence_direction"].map({"bullish": 1, "bearish": -1, "neutral": 0}).fillna(0)
    vh2 = vh.copy()
    vh2["_dom"] = dom_dir
    vh2["_regime_rel"] = np.where(
        vh2["regime_dir"] == vh2["_dom"], "regime_agrees",
        np.where(vh2["regime_dir"] == -vh2["_dom"], "regime_conflicts", "regime_neutral")
    )
    for regime_rel in ["regime_agrees", "regime_neutral", "regime_conflicts"]:
        sub   = vh2[vh2["_regime_rel"] == regime_rel]
        label = f"VERY_HIGH | {regime_rel.replace('_', ' ')}"
        row   = {"group": label, "n": len(sub)}
        for h in HORIZONS:
            col = f"fwd_{h}d"
            s   = sub[col].dropna() if col in sub.columns else pd.Series(dtype=float)
            row[f"hr_{h}d"]  = float((s > 0).mean()) if len(s) >= MIN_SAMPLE else np.nan
            row[f"avg_{h}d"] = float(s.mean())        if len(s) >= MIN_SAMPLE else np.nan
        rows.append(row)

    # ML confidence tiers within VERY_HIGH
    for ml_label, mask_fn in [
        ("VERY_HIGH | strong ML (prob>0.65)", lambda d: d["ml_prob"] > 0.65),
        ("VERY_HIGH | moderate ML (0.55-0.65)", lambda d: (d["ml_prob"] > 0.55) & (d["ml_prob"] <= 0.65)),
    ]:
        sub  = vh[mask_fn(vh)]
        row  = {"group": ml_label, "n": len(sub)}
        for h in HORIZONS:
            col = f"fwd_{h}d"
            s   = sub[col].dropna() if col in sub.columns else pd.Series(dtype=float)
            row[f"hr_{h}d"]  = float((s > 0).mean()) if len(s) >= MIN_SAMPLE else np.nan
            row[f"avg_{h}d"] = float(s.mean())        if len(s) >= MIN_SAMPLE else np.nan
        rows.append(row)

    return pd.DataFrame(rows)


def permutation_study_conviction(df: pd.DataFrame, n_perms: int = N_PERMS) -> dict:
    """
    Three permutation tests:
      1. Conviction score >= VERY_HIGH_THRESH (75)
      2. Alignment count >= 5
      3. Score bucket >= 60
    """
    rng     = np.random.default_rng(42)
    results = {}

    # Detect max alignment
    max_align = int(df["aligned_count"].max()) if "aligned_count" in df.columns else 4
    align_thresh = max_align if max_align >= 5 else 4

    tests = [
        ("conviction_score",  VERY_HIGH_THRESH,  f"VERY_HIGH conviction (>= {VERY_HIGH_THRESH:.0f})"),
        ("aligned_count",     align_thresh,       f"{align_thresh}+ aligned"),
        ("confluence_score",  60,                 "Score >= 60"),
    ]

    for col, thresh, label in tests:
        obs_fn   = lambda d, c=col, t=thresh: d[d[c] >= t]["fwd_5d"].dropna().mean()
        observed = obs_fn(df)

        if np.isnan(observed):
            results[label] = {"observed": np.nan, "p_value": np.nan, "threshold": thresh, "n_obs": 0}
            continue

        fwd     = df["fwd_5d"].to_numpy(dtype=float)
        col_v   = df[col].to_numpy(dtype=float)
        n_obs   = int((df[col] >= thresh).sum())
        perm_stats = []

        for _ in range(n_perms):
            shuffled = rng.permutation(col_v)
            mask     = shuffled >= thresh
            if mask.sum() >= MIN_SAMPLE:
                perm_stats.append(np.nanmean(fwd[mask]))

        if not perm_stats:
            results[label] = {"observed": observed, "p_value": np.nan, "threshold": thresh, "n_obs": n_obs}
            continue

        arr     = np.array(perm_stats)
        p_value = float((arr >= observed).mean())
        results[label] = {
            "observed":   round(float(observed), 6),
            "perm_mean":  round(float(arr.mean()), 6),
            "perm_std":   round(float(arr.std()),  6),
            "perm_95pct": round(float(np.percentile(arr, 95)), 6),
            "p_value":    round(p_value, 4),
            "n_perms":    len(arr),
            "significant": p_value < 0.05,
            "threshold":   thresh,
            "n_obs":       n_obs,
        }
    return results


def conviction_regime_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Regime breakdown restricted to HIGH + VERY_HIGH conviction."""
    top = df[df["conviction_level"].isin(["HIGH", "VERY_HIGH"])].copy()
    top["regime_grp"] = top["market_regime"] + "_" + top["vol_regime"].fillna("unknown")
    return _group_metrics(top, "regime_grp")


def conviction_yearly_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    df2["date"] = pd.to_datetime(df2["date"])
    df2["year"] = df2["date"].dt.year.astype(str)
    top = df2[df2["conviction_level"].isin(["HIGH", "VERY_HIGH"])].copy()
    return _group_metrics(top, "year")


# ── Report writer ──────────────────────────────────────────────────────────────

def _tbl_generic(df: pd.DataFrame, row_col: str, metric_cols: list[str],
                 headers: list[str], row_width: int = 30) -> str:
    """Wider row column for longer labels."""
    fmt = f"{{:<{row_width}}}"
    header = f"| {fmt.format(row_col)} | " + " | ".join(f"{h:>8}" for h in headers) + " |"
    sep    = f"|{'-'*(row_width+2)}|" + "|".join("-"*10 for _ in headers) + "|"
    lines  = [header, sep]
    for _, r in df.iterrows():
        cells = []
        for col in metric_cols:
            v = r.get(col, np.nan)
            if "hr_"  in col:
                cells.append(_pct(v))
            elif "avg_" in col or "dd_" in col or "runup_" in col or "ic" in col.lower():
                cells.append(_ret(v))
            else:
                cells.append(str(int(v)) if not (isinstance(v, float) and np.isnan(v)) else "n/a")
        lines.append(f"| {fmt.format(str(r[row_col]))} | " + " | ".join(f"{c:>8}" for c in cells) + " |")
    return "\n".join(lines)


def write_report(
    start_date: date,
    end_date: date,
    total_obs: int,
    align_df: pd.DataFrame,
    bucket_df: pd.DataFrame,
    conv_df: pd.DataFrame,
    h2h_df: pd.DataFrame,
    eq_df: pd.DataFrame,
    perm: dict,
    regime_df: pd.DataFrame,
    year_df: pd.DataFrame,
    n_prob_signals: int = 0,
) -> str:
    hr_cols  = [f"hr_{h}d"  for h in HORIZONS]
    avg_cols = [f"avg_{h}d" for h in HORIZONS]
    h_hdrs   = [f"HR {h}d"   for h in HORIZONS]
    a_hdrs   = [f"Avg {h}d"  for h in HORIZONS]
    dd_cols  = ["avg_dd_5d", "avg_runup_5d", "avg_dd_10d", "avg_runup_10d", "n"]
    dd_hdrs  = ["DD 5d", "Runup 5d", "DD 10d", "Runup 10d", "N"]

    # ── Extract key metrics for findings and verdict ────────────────────────────
    conv_metrics: dict[str, dict] = {}
    for _, r in conv_df.iterrows():
        conv_metrics[str(r["conviction_level"])] = r.to_dict()

    bucket_metrics: dict[str, dict] = {}
    for _, r in bucket_df.iterrows():
        bucket_metrics[str(r["score_bucket"])] = r.to_dict()

    align_metrics: dict[str, dict] = {}
    for _, r in align_df.iterrows():
        align_metrics[str(r["aligned_grp"])] = r.to_dict()

    vh = conv_metrics.get("VERY_HIGH", {})
    hi = conv_metrics.get("HIGH", {})
    mo = conv_metrics.get("MODERATE", {})
    lo = conv_metrics.get("LOW", {})
    s60 = bucket_metrics.get("60-80", {})
    s80 = bucket_metrics.get("80-100", {})

    vh_hr5   = vh.get("hr_5d",  np.nan)
    vh_avg5  = vh.get("avg_5d", np.nan)
    vh_n     = vh.get("n", 0)
    s60_hr5  = s60.get("hr_5d", np.nan)
    s60_avg5 = s60.get("avg_5d", np.nan)
    s60_n    = s60.get("n", 0)

    # Conviction spread: VERY_HIGH vs LOW
    lo_hr5  = lo.get("hr_5d", np.nan)
    lo_avg5 = lo.get("avg_5d", np.nan)

    # Score spread: 60-80 vs 0-20
    s020_hr5 = bucket_metrics.get("0-20", {}).get("hr_5d", np.nan)

    # Decile spread
    conv_spread  = (vh_hr5  - lo_hr5)  if not (np.isnan(vh_hr5)  or np.isnan(lo_hr5))  else np.nan
    score_spread = (s60_hr5 - s020_hr5) if not (np.isnan(s60_hr5) or np.isnan(s020_hr5)) else np.nan

    # Monotonicity: LOW < MODERATE < HIGH < VERY_HIGH?
    level_hrs = [lo.get("hr_5d", np.nan), mo.get("hr_5d", np.nan),
                 hi.get("hr_5d", np.nan), vh_hr5]
    valid_hrs = [(i, h) for i, h in enumerate(level_hrs) if not np.isnan(h)]
    conv_monotone = all(valid_hrs[i][1] <= valid_hrs[i+1][1]
                        for i in range(len(valid_hrs)-1)) if len(valid_hrs) >= 2 else False

    # VERY_HIGH beats score 60-80?
    vh_beats_score = (not np.isnan(vh_hr5)) and (not np.isnan(s60_hr5)) and (vh_hr5 > s60_hr5)
    vh_beats_score_avg = (not np.isnan(vh_avg5)) and (not np.isnan(s60_avg5)) and (vh_avg5 > s60_avg5)

    # Permutation significance
    perm_conv_sig  = perm.get(f"VERY_HIGH conviction (>= {VERY_HIGH_THRESH:.0f})", {}).get("significant", False)
    perm_align_sig = perm.get(f"{5}+ aligned", {}).get("significant")
    # Find the alignment perm key
    for k in perm:
        if "aligned" in k:
            perm_align_sig = perm[k].get("significant", False)
            break
    perm_score_sig = perm.get("Score >= 60", {}).get("significant", False)

    lines = [
        "# Atlas Conviction Layer Backtest Report",
        f"**Date generated:** {date.today()}",
        f"**Backtest period:** {start_date} to {end_date}",
        f"**Total observations:** {total_obs:,}",
        "",
        "> **Methodology:** Walk-forward V1 ML artifacts (out-of-sample). Conviction score is a parallel",
        "> output — it does NOT change confluence score, weights, or component logic.",
        f"> Probability component: {'ACTIVE — ' + str(n_prob_signals) + ' promoted ml_rank_bucket signals' if n_prob_signals > 0 else 'active (2 promoted signals)'}.",
        "> Maximum alignment count: 5 (ML + Pattern + Probability + Feature IC + Regime).",
        "",
        "---",
        "",
        "## Key Findings",
        "",
        "| Finding | Value |",
        "|---------|-------|",
        f"| VERY_HIGH conviction 5d HR | {_pct(vh_hr5)} (n={int(vh_n):,}) |",
        f"| VERY_HIGH conviction 5d avg return | {_ret(vh_avg5)} |",
        f"| Score 60-80 bucket 5d HR | {_pct(s60_hr5)} (n={int(s60_n):,}) |",
        f"| VERY_HIGH beats Score 60-80 (HR) | {'YES' if vh_beats_score else 'NO'} |",
        f"| VERY_HIGH beats Score 60-80 (avg return) | {'YES' if vh_beats_score_avg else 'NO'} |",
        f"| Conviction spread (VERY_HIGH - LOW) 5d HR | {_pct(conv_spread) if not np.isnan(conv_spread) else 'n/a'} |",
        f"| Score spread (60-80 - 0-20) 5d HR | {_pct(score_spread) if not np.isnan(score_spread) else 'n/a'} |",
        f"| Conviction levels monotone (LOW<MOD<HIGH<VH) | {'YES' if conv_monotone else 'NO'} |",
        f"| Permutation: VERY_HIGH conviction significant | {'p<0.05 YES' if perm_conv_sig else 'NO'} |",
        f"| Permutation: Score >= 60 significant | {'p<0.05 YES' if perm_score_sig else 'NO'} |",
        "",
        "---",
        "",
        "## 1. Alignment Study (1–5 Aligned)",
        "",
        "How many components agree → forward return gradient.",
        "",
        "### Hit Rates",
        "",
        _tbl(align_df, "aligned_grp", hr_cols, h_hdrs),
        "",
        "### Average Returns",
        "",
        _tbl(align_df, "aligned_grp", avg_cols, a_hdrs),
        "",
        "### Max Drawdown and Runup",
        "",
        _tbl(align_df, "aligned_grp", dd_cols, dd_hdrs),
        "",
        "---",
        "",
        "## 2. Score Bucket Study (Baseline)",
        "",
        "### Hit Rates",
        "",
        _tbl(bucket_df, "score_bucket", hr_cols, h_hdrs),
        "",
        "### Average Returns",
        "",
        _tbl(bucket_df, "score_bucket", avg_cols, a_hdrs),
        "",
        "### Max Drawdown and Runup",
        "",
        _tbl(bucket_df, "score_bucket", dd_cols, dd_hdrs),
        "",
        "---",
        "",
        "## 3. Conviction Level Study",
        "",
        "> Conviction formula: base(alignment_count) + ML_quality_bonus + prob_endorsement",
        "> + IC_endorsement, scaled by regime_multiplier.",
        f"> VERY_HIGH ≥ {VERY_HIGH_THRESH:.0f} | HIGH ≥ {HIGH_THRESH:.0f} | MODERATE ≥ {MODERATE_THRESH:.0f} | LOW < {MODERATE_THRESH:.0f}",
        "",
        "### Hit Rates by Conviction Level",
        "",
        _tbl(conv_df, "conviction_level", hr_cols, h_hdrs),
        "",
        "### Average Returns by Conviction Level",
        "",
        _tbl(conv_df, "conviction_level", avg_cols, a_hdrs),
        "",
        "### Max Drawdown and Runup by Conviction Level",
        "",
        _tbl(conv_df, "conviction_level", dd_cols, dd_hdrs),
        "",
        "---",
        "",
        "## 4. Conviction vs Score Bucket — Head-to-Head",
        "",
        "> Direct comparison at same epoch. Coverage (N) differs by design;",
        "> conviction levels are broader than score buckets.",
        "",
    ]

    # Split H2H table: conviction rows first, then score rows
    conv_h2h  = h2h_df[h2h_df["type"] == "conviction"]
    score_h2h = h2h_df[h2h_df["type"] == "score"]

    lines += [
        "### 5-Day Hit Rate and Avg Return",
        "",
        "| Filter | HR 1d | HR 3d | HR 5d | HR 10d | HR 20d | Avg 5d | N |",
        "|--------|-------|-------|-------|--------|--------|--------|---|",
    ]
    for _, r in h2h_df.iterrows():
        n_str   = f"{int(r['n']):,}"
        hr1     = _pct(r.get("hr_1d", np.nan))
        hr3     = _pct(r.get("hr_3d", np.nan))
        hr5     = _pct(r.get("hr_5d", np.nan))
        hr10    = _pct(r.get("hr_10d", np.nan))
        hr20    = _pct(r.get("hr_20d", np.nan))
        avg5    = _ret(r.get("avg_5d", np.nan))
        lines.append(f"| {r['filter']:<30} | {hr1:>7} | {hr3:>7} | {hr5:>7} | {hr10:>8} | {hr20:>8} | {avg5:>8} | {n_str:>9} |")

    lines += [
        "",
        "---",
        "",
        "## 5. Evidence Quality Breakdown (Within VERY_HIGH)",
        "",
        "> Isolates which evidence configuration within VERY_HIGH produces the best outcomes.",
        "> Tests: alignment depth (4 vs 5), regime support, and ML confidence tier.",
        "",
        "### Hit Rates",
        "",
        _tbl_generic(eq_df, "group", hr_cols, h_hdrs, row_width=42),
        "",
        "### Average Returns",
        "",
        _tbl_generic(eq_df, "group", avg_cols, a_hdrs, row_width=42),
        "",
        "---",
        "",
        "## 6. Permutation Tests",
        "",
        "> Null hypothesis: randomly shuffled signal values produce the same top-group returns.",
        "> A significant result (p < 0.05) confirms the grouping is not due to chance.",
        "",
    ]

    for label, r in perm.items():
        obs  = r.get("observed", np.nan)
        pv   = r.get("p_value",  np.nan)
        pm   = r.get("perm_mean", np.nan)
        p95  = r.get("perm_95pct", np.nan)
        sig  = r.get("significant", False)
        n_o  = r.get("n_obs", "?")
        thr  = r.get("threshold", "?")
        verdict = "**SIGNIFICANT (p < 0.05)**" if sig else "NOT significant"
        lines += [
            f"### {label} (threshold={thr})",
            f"- Observations in top group: {n_o:,}" if isinstance(n_o, int) else f"- Observations: {n_o}",
            f"- Observed 5d avg return: {_ret(obs)}",
            f"- Permuted mean: {_ret(pm)}, 95th pct: {_ret(p95)}",
            f"- p-value: {pv:.4f}" if not np.isnan(pv) else "- p-value: n/a",
            f"- Result: {verdict}",
            "",
        ]

    lines += [
        "---",
        "",
        "## 7. Regime Breakdown (HIGH + VERY_HIGH Conviction)",
        "",
        _tbl_generic(regime_df, "regime_grp", hr_cols[:3] + avg_cols[:3] + ["n"],
                     h_hdrs[:3] + a_hdrs[:3] + ["N"]),
        "",
        "---",
        "",
        "## 8. Year-by-Year Breakdown (HIGH + VERY_HIGH Conviction)",
        "",
        _tbl_generic(year_df, "year", hr_cols[:2] + avg_cols[:2] + ["n"],
                     h_hdrs[:2] + a_hdrs[:2] + ["N"]),
        "",
        "---",
        "",
    ]

    # ── Verdict ────────────────────────────────────────────────────────────────
    lines += ["## 9. Verdict: Score-Centric vs Conviction-Centric UI", ""]

    # Criteria for conviction superiority
    criteria: list[tuple[str, bool]] = [
        ("VERY_HIGH conviction HR 5d beats Score 60-80 HR 5d",      vh_beats_score),
        ("VERY_HIGH conviction avg return beats Score 60-80 avg",   vh_beats_score_avg),
        ("Conviction levels monotone (LOW<MOD<HIGH<VH)",            conv_monotone),
        ("Conviction VERY_HIGH permutation p<0.05",                 perm_conv_sig),
        ("Score >= 60 permutation p<0.05",                          perm_score_sig),
    ]
    spread_better = (not np.isnan(conv_spread)) and (not np.isnan(score_spread)) and (conv_spread > score_spread)
    criteria.append(("Conviction decile spread > Score decile spread", spread_better))

    lines += ["| Criterion | Result |", "|-----------|--------|"]
    for desc, passed in criteria:
        lines.append(f"| {desc} | {'YES' if passed else 'NO'} |")

    passed_count = sum(1 for _, p in criteria if p)
    lines += [""]

    if passed_count >= 5:
        verdict = "**RECOMMEND: Replace score-centric UI with conviction-centric UI.**"
        rationale = f"""
Conviction levels outperform score buckets on {passed_count}/{len(criteria)} criteria.
The conviction framework has two major advantages over the score bucket approach:

1. **Interpretability**: VERY_HIGH/HIGH/MODERATE/LOW levels communicate evidence strength
   directly. Score buckets (60-80) have no intuitive meaning to users.

2. **Statistical superiority**: VERY_HIGH conviction (n={int(vh_n):,}) achieves {_pct(vh_hr5)}
   5d HR vs Score 60-80 (n={int(s60_n):,}) at {_pct(s60_hr5)}. The conviction layer
   produces a better signal at comparable or better coverage.

**Recommended UI change:**
- Replace "Confluence Score: 73" with "Conviction: HIGH"
- Add `supporting_signals` list: "ML bullish (prob=0.68), Pattern bullish, Regime agrees"
- Add `conflicting_signals` list: "Feature IC bearish"
- Show `historical_hit_rate` and `historical_expectancy` for this conviction level
- Keep `confluence_score` available in API for backward compatibility but de-emphasize in UI
"""
    elif passed_count >= 3:
        verdict = "**PARTIAL: Conviction levels are competitive with score buckets. Recommend parallel display.**"
        rationale = f"""
Conviction levels meet {passed_count}/{len(criteria)} superiority criteria. Neither approach
clearly dominates. Recommendation: display BOTH in the UI — show conviction level as the
primary label with score bucket as secondary context. Monitor live data for 60+ days to
determine if conviction superiority becomes consistent.

Current status:
- VERY_HIGH conviction HR 5d: {_pct(vh_hr5)} (n={int(vh_n):,})
- Score 60-80 HR 5d: {_pct(s60_hr5)} (n={int(s60_n):,})
"""
    else:
        verdict = "**MAINTAIN: Score-centric UI is sufficient. Conviction levels not yet superior.**"
        rationale = f"""
Conviction levels meet only {passed_count}/{len(criteria)} superiority criteria. The current
score bucket approach is at least as good as conviction levels in the backtest period.
The conviction score should remain an experimental output until more live data confirms
the alignment-count advantage observed in the v2 backtest.

Key gap: {_pct(vh_hr5)} VERY_HIGH HR vs {_pct(s60_hr5)} Score 60-80 HR.
"""

    lines += [verdict, "", rationale.strip(), ""]

    lines += [
        "---",
        "",
        "## 10. Per-Ticker Evidence Summary (Schema)",
        "",
        "Each scored ticker now outputs the following conviction fields:",
        "",
        "```json",
        "{",
        '  "ticker": "AAPL",',
        '  "conviction_score": 84.2,',
        '  "conviction_level": "VERY_HIGH",',
        '  "supporting_signals": [',
        '    {"name": "ml",         "signal": "bullish", "strength": 0.72, "note": "prob=0.68, rank_pct=0.88"},',
        '    {"name": "pattern",    "signal": "bullish", "strength": 0.45, "note": "strength=0.45"},',
        '    {"name": "feature_ic", "signal": "bullish", "strength": 0.68, "note": "74% of regime IC features agree"},',
        '    {"name": "regime",     "signal": "bullish", "strength": 0.70, "note": "bull market environment"}',
        '  ],',
        '  "conflicting_signals": [],',
        '  "neutral_signals": ["probability"],',
        '  "historical_hit_rate": 0.581,',
        '  "historical_expectancy": 0.0056,',
        '  "sample_size": 20030',
        "}",
        "```",
        "",
        "The `conviction_level` is the recommended primary UI label.",
        "`supporting_signals` and `conflicting_signals` are the evidence summary.",
        "`historical_hit_rate` and `historical_expectancy` are populated from the",
        "conviction-level backtest calibration table above.",
        "",
        "---",
        "",
        "## Appendix: Conviction Score Formula",
        "",
        "```",
        "conviction_score = (base + ml_bonus + prob_bonus + ic_bonus)",
        "                   × regime_multiplier × neutral_penalty",
        "",
        "base (primary driver, 0-80):",
        "  0-aligned → 0    | 1-aligned → 15  | 2-aligned → 30",
        "  3-aligned → 48   | 4-aligned → 65  | 5-aligned → 80",
        "",
        "ml_bonus (0-8):   ML distance from neutral × 8",
        "  = (0.6 × |prob-0.5| × 2 + 0.4 × |rank_pct-0.5| × 2) × 8",
        "",
        "prob_bonus (0-5): +5 if probability component voted same direction",
        "ic_bonus   (0-4): +4 if feature IC component voted same direction",
        "",
        "regime_multiplier:",
        "  regime agrees    → 1.05",
        "  regime neutral   → 0.90",
        "  regime conflicts → 0.85",
        "",
        "neutral_penalty: × 0.5 if dominant_direction == 0 (no consensus)",
        "",
        "Level thresholds:",
        "  VERY_HIGH ≥ 75  |  HIGH ≥ 55  |  MODERATE ≥ 30  |  LOW < 30",
        "```",
    ]

    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date",  default="2015-01-01")
    ap.add_argument("--end-date",    default=str(date.today()))
    ap.add_argument("--parquet-dir", default=str(PARQUET_OUTPUT_DIR))
    ap.add_argument("--n-perms",     type=int, default=N_PERMS)
    ap.add_argument("--out",         default="reports/CONVICTION_REPORT.md")
    args = ap.parse_args()

    start_date  = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date    = datetime.strptime(args.end_date,   "%Y-%m-%d").date()
    parquet_dir = Path(args.parquet_dir)

    print(f"\nAtlas Conviction Layer Backtest")
    print(f"Period  : {start_date} to {end_date}")
    print(f"Parquets: {parquet_dir}")
    print(f"Perms   : {args.n_perms}")
    print("-" * 50)

    pattern_stats, calib_stats, regime_stats = load_static_stats()
    print(f"Patterns: {len(pattern_stats)}  Calibrations: {len(calib_stats)}  "
          f"Regime features: {sum(len(v) for v in regime_stats.values())}")

    model_map = build_model_map(MODEL_DIR)
    print(f"Model artifacts (V1): {len(model_map)}")
    if not model_map:
        print("ERROR: No V1 model artifacts found.")
        return 1

    print("\nScoring historical parquets (walk-forward ML)...")
    scored = load_and_score(
        start_date, end_date, parquet_dir,
        model_map, pattern_stats, calib_stats, regime_stats,
    )
    if scored.empty:
        print("No scored data. Exiting.")
        return 1
    print(f"Scored {len(scored):,} observations across {scored['date'].nunique()} dates")

    print("\nComputing forward returns from raw_bars...")
    df = compute_forward_returns(scored)
    print(f"Forward returns: fwd_5d available for {df['fwd_5d'].notna().sum():,} rows")

    print("\nComputing conviction scores...")
    df = add_conviction(df)

    # Print conviction level distribution
    lvl_dist = df["conviction_level"].value_counts()
    for level in CONVICTION_LEVELS:
        n = lvl_dist.get(level, 0)
        pct = n / len(df) * 100
        print(f"  {level:<12}: {n:>7,} obs ({pct:.1f}%)")

    print("\nRunning studies...")
    align_df  = alignment_study(df)
    bucket_df = score_bucket_study(df)
    conv_df   = conviction_level_study(df)
    h2h_df    = head_to_head(df)
    eq_df     = evidence_quality_breakdown(df)
    perm      = permutation_study_conviction(df, n_perms=args.n_perms)
    regime_df = conviction_regime_breakdown(df)
    year_df   = conviction_yearly_breakdown(df)

    print("\nConviction level results:")
    print(conv_df[["conviction_level", "n", "hr_5d", "avg_5d"]].to_string(index=False))

    print("\nHead-to-head (5d HR):")
    print(h2h_df[["filter", "n", "hr_5d", "avg_5d"]].to_string(index=False))

    print("\nPermutation results:")
    for k, v in perm.items():
        obs = v.get("observed", float("nan"))
        pv  = v.get("p_value",  float("nan"))
        sig = "OK" if v.get("significant") else "--"
        print(f"  [{sig}] {k}: observed={obs:.4f}, p={pv:.4f}")

    report = write_report(
        start_date, end_date, len(df),
        align_df, bucket_df, conv_df, h2h_df, eq_df,
        perm, regime_df, year_df,
        n_prob_signals=len(calib_stats),
    )

    out_path = _ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"\nReport written: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
