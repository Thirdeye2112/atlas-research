"""
Prediction Error Analysis
==========================
Loads prediction_outcomes from DB, slices by context, runs the discovery engine
to find best/worst performing combinations, and writes PREDICTION_ERROR_ANALYSIS_REPORT.md.

Usage:
    python scripts/analyze_prediction_errors.py
    python scripts/analyze_prediction_errors.py --min-n 200
"""
from __future__ import annotations

import argparse
import os
import sys
import warnings
from datetime import date
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

warnings.filterwarnings("ignore")

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")

REPORT_PATH = _ROOT / "reports" / "PREDICTION_ERROR_ANALYSIS_REPORT.md"
MIN_N       = 100    # default minimum sample per context slice


# ── Data loading ──────────────────────────────────────────────────────────────

def load_outcomes(engine) -> pd.DataFrame:
    sql = """
        SELECT
            ticker, prediction_date, model_version,
            predicted_rank, predicted_prob, predicted_direction,
            actual_return_5d, actual_return_10d, actual_return_20d,
            direction_correct_5d, direction_correct_10d, direction_correct_20d,
            rank_quintile, outcome_quintile, rank_hit,
            jarvis_green, quality_tier, above_sma200,
            sector_regime, vix_regime,
            confluence_score, conviction_level, ml_signal_strength
        FROM prediction_outcomes
        WHERE direction_correct_5d IS NOT NULL
        ORDER BY prediction_date, ticker
    """
    return pd.read_sql(text(sql), engine)


# ── Metrics helpers ───────────────────────────────────────────────────────────

def _metrics(df: pd.DataFrame, min_n: int = MIN_N) -> dict | None:
    """Return accuracy metrics for a slice. None if too few samples."""
    n = len(df)
    if n < min_n:
        return None

    dir5  = df["direction_correct_5d"].dropna()
    dir10 = df["direction_correct_10d"].dropna()
    dir20 = df["direction_correct_20d"].dropna()
    ret5  = df["actual_return_5d"].dropna()
    rh    = df["rank_hit"].dropna()

    return {
        "n":            n,
        "hr_5d":        float(dir5.mean())  if len(dir5)  > 0 else None,
        "hr_10d":       float(dir10.mean()) if len(dir10) > 0 else None,
        "hr_20d":       float(dir20.mean()) if len(dir20) > 0 else None,
        "expectancy":   float(ret5.mean())  if len(ret5)  > 0 else None,
        "rank_hit_rate":float(rh.mean())    if len(rh)    > 0 else None,
    }


def _fmt(m: dict | None, key: str = "hr_5d") -> str:
    if m is None or m.get(key) is None:
        return "n/a"
    v = m[key]
    if key in ("hr_5d", "hr_10d", "hr_20d", "rank_hit_rate"):
        return f"{v:.1%}"
    return f"{v:+.4f}"


# ── Pre-defined context slices ────────────────────────────────────────────────

NAMED_SLICES = {
    # Jarvis
    "Jarvis green":           lambda df: df[df["jarvis_green"] == True],
    "Jarvis red":             lambda df: df[df["jarvis_green"] == False],
    # Regime
    "Bull regime":            lambda df: df[df["sector_regime"] == "bull"],
    "Bear regime":            lambda df: df[df["sector_regime"] == "bear"],
    "Range regime":           lambda df: df[df["sector_regime"] == "range"],
    # VIX
    "VIX low":                lambda df: df[df["vix_regime"] == "low"],
    "VIX moderate":           lambda df: df[df["vix_regime"] == "moderate"],
    "VIX high":               lambda df: df[df["vix_regime"] == "high"],
    # Confluence
    "Confluence ≥ 3 (5-comp)":lambda df: df[df["confluence_score"] >= 60],
    "Confluence < 2 (5-comp)":lambda df: df[df["confluence_score"] < 30],
    # Quality
    "Quality Tier 1":         lambda df: df[df["quality_tier"] == 1],
    "Quality Tier 2":         lambda df: df[df["quality_tier"] == 2],
    "Quality Tier 3":         lambda df: df[df["quality_tier"] == 3],
    "Quality Tier 4":         lambda df: df[df["quality_tier"] == 4],
    # SMA200
    "Above SMA200":           lambda df: df[df["above_sma200"] == True],
    "Below SMA200":           lambda df: df[df["above_sma200"] == False],
    # Conviction
    "Conviction VERY_HIGH":   lambda df: df[df["conviction_level"] == "VERY_HIGH"],
    "Conviction HIGH":        lambda df: df[df["conviction_level"] == "HIGH"],
    "Conviction MODERATE":    lambda df: df[df["conviction_level"] == "MODERATE"],
    "Conviction LOW":         lambda df: df[df["conviction_level"] == "LOW"],
    # Signal strength
    "ML strong (rank ≥ 0.80)":lambda df: df[df["predicted_rank"] >= 0.80],
    "ML moderate (0.60-0.80)":lambda df: df[df["predicted_rank"].between(0.60, 0.80)],
    "ML weak (< 0.60)":       lambda df: df[df["predicted_rank"] < 0.60],
    # Rank quintile
    "Rank Q5 (top predictions)": lambda df: df[df["rank_quintile"] == 5],
    "Rank Q1 (bottom predictions)": lambda df: df[df["rank_quintile"] == 1],
}


# ── Discovery engine — all 2-way combinations ─────────────────────────────────

COMBO_AXES = {
    "jarvis":      {"green": True, "red": False},
    "regime":      {"bull": "bull", "bear": "bear", "range": "range"},
    "vix":         {"low": "low", "moderate": "moderate", "high": "high"},
    "quality":     {1: 1, 2: 2, 3: 3, 4: 4},
    "above_sma200":{"above": True, "below": False},
    "conviction":  {"VERY_HIGH": "VERY_HIGH", "HIGH": "HIGH",
                    "MODERATE": "MODERATE", "LOW": "LOW"},
    "rank_q":      {5: 5, 4: 4, 3: 3, 2: 2, 1: 1},
}

AXIS_COL = {
    "jarvis":      "jarvis_green",
    "regime":      "sector_regime",
    "vix":         "vix_regime",
    "quality":     "quality_tier",
    "above_sma200":"above_sma200",
    "conviction":  "conviction_level",
    "rank_q":      "rank_quintile",
}


def _apply_label_filter(df: pd.DataFrame, axis: str, label) -> pd.DataFrame:
    col = AXIS_COL[axis]
    if col not in df.columns:
        return pd.DataFrame()
    return df[df[col] == label]


def run_discovery_engine(df: pd.DataFrame, min_n: int) -> list[dict]:
    """
    Test all 2-axis combinations.  Returns list of dicts sorted by hr_5d desc.
    Excludes combinations with < min_n samples.
    """
    axes = list(COMBO_AXES.keys())
    results = []

    for ax1, ax2 in combinations(axes, 2):
        for lbl1, val1 in COMBO_AXES[ax1].items():
            sub1 = _apply_label_filter(df, ax1, val1)
            if len(sub1) < min_n:
                continue
            for lbl2, val2 in COMBO_AXES[ax2].items():
                sub2 = _apply_label_filter(sub1, ax2, val2)
                m = _metrics(sub2, min_n)
                if m is None:
                    continue
                results.append({
                    "combo":    f"{ax1}={lbl1} + {ax2}={lbl2}",
                    **m,
                })

    # Also include single-axis slices in the same list for completeness
    for ax, labels in COMBO_AXES.items():
        for lbl, val in labels.items():
            sub = _apply_label_filter(df, ax, val)
            m = _metrics(sub, min_n)
            if m is None:
                continue
            results.append({
                "combo": f"{ax}={lbl}",
                **m,
            })

    return sorted(results, key=lambda r: r.get("hr_5d") or 0, reverse=True)


# ── Report generation ─────────────────────────────────────────────────────────

def _tbl_row(combo: str, m: dict) -> str:
    return (
        f"| {combo} | {m['n']:,} | {_fmt(m,'hr_5d')} "
        f"| {_fmt(m,'hr_10d')} | {_fmt(m,'hr_20d')} "
        f"| {_fmt(m,'expectancy')} | {_fmt(m,'rank_hit_rate')} |"
    )

TBL_HDR = (
    "| Context | N | HR 5d | HR 10d | HR 20d | Expectancy | Rank Hit |"
)
TBL_SEP = "|---|---|---|---|---|---|---|"


def build_report(
    df: pd.DataFrame,
    named_metrics: dict,
    discovery_results: list[dict],
    overall: dict | None,
) -> str:
    lines = []

    lines.append("# Prediction Error Analysis Report")
    lines.append("")
    lines.append(f"**Generated:** {date.today()}")
    lines.append(f"**Rows analysed:** {len(df):,}  (directional predictions with resolved 5d labels)")
    lines.append(f"**Date range:** {df['prediction_date'].min()} to {df['prediction_date'].max()}")
    lines.append("")

    # Overall baseline
    lines.append("## 0. Overall Baseline")
    lines.append("")
    if overall:
        lines.append(f"- **5d hit rate:** {_fmt(overall,'hr_5d')} (n={overall['n']:,})")
        lines.append(f"- **10d hit rate:** {_fmt(overall,'hr_10d')}")
        lines.append(f"- **20d hit rate:** {_fmt(overall,'hr_20d')}")
        lines.append(f"- **Expectancy (5d):** {_fmt(overall,'expectancy')}")
        lines.append(f"- **Rank hit rate:** {_fmt(overall,'rank_hit_rate')}")
    lines.append("")

    # ── Section 1: Accuracy by Context ───────────────────────────────────────
    lines.append("## 1. Accuracy by Context")
    lines.append("")
    lines.append(TBL_HDR)
    lines.append(TBL_SEP)

    context_groups = [
        ("Jarvis signal", ["Jarvis green", "Jarvis red"]),
        ("Market regime", ["Bull regime", "Bear regime", "Range regime"]),
        ("Volatility regime", ["VIX low", "VIX moderate", "VIX high"]),
        ("Confluence", ["Confluence ≥ 3 (5-comp)", "Confluence < 2 (5-comp)"]),
        ("Quality tier", ["Quality Tier 1", "Quality Tier 2", "Quality Tier 3", "Quality Tier 4"]),
        ("Price vs SMA200", ["Above SMA200", "Below SMA200"]),
        ("Conviction level", ["Conviction VERY_HIGH", "Conviction HIGH",
                               "Conviction MODERATE", "Conviction LOW"]),
        ("ML signal strength", ["ML strong (rank ≥ 0.80)", "ML moderate (0.60-0.80)",
                                 "ML weak (< 0.60)"]),
    ]

    for group_name, keys in context_groups:
        lines.append(f"| **{group_name}** | | | | | | |")
        for key in keys:
            m = named_metrics.get(key)
            if m:
                lines.append(_tbl_row(key, m))
            else:
                lines.append(f"| {key} | < {MIN_N} | n/a | n/a | n/a | n/a | n/a |")

    lines.append("")

    # ── Section 2: Accuracy by Signal Strength ────────────────────────────────
    lines.append("## 2. Accuracy by Signal Strength")
    lines.append("")
    lines.append(TBL_HDR)
    lines.append(TBL_SEP)
    for key in ["ML strong (rank ≥ 0.80)", "ML moderate (0.60-0.80)", "ML weak (< 0.60)",
                 "Rank Q5 (top predictions)", "Rank Q1 (bottom predictions)"]:
        m = named_metrics.get(key)
        if m:
            lines.append(_tbl_row(key, m))
    lines.append("")

    # ── Section 3 & 4: Discovery engine top/bottom 25 ────────────────────────
    lines.append("## 3. Best Performing Contexts (Top 25 combinations)")
    lines.append("")
    lines.append(TBL_HDR)
    lines.append(TBL_SEP)
    for r in discovery_results[:25]:
        lines.append(_tbl_row(r["combo"], r))
    lines.append("")

    lines.append("## 4. Worst Performing Contexts (Bottom 25 combinations)")
    lines.append("")
    lines.append(TBL_HDR)
    lines.append(TBL_SEP)
    worst = [r for r in discovery_results if r.get("hr_5d") is not None]
    worst_sorted = sorted(worst, key=lambda r: r["hr_5d"])
    for r in worst_sorted[:25]:
        lines.append(_tbl_row(r["combo"], r))
    lines.append("")

    # ── Section 5: Answers to key questions ──────────────────────────────────
    lines.append("## 5. Key Findings")
    lines.append("")

    # Best single context
    best_named = sorted(
        [(k, m) for k, m in named_metrics.items() if m and m.get("hr_5d")],
        key=lambda x: x[1]["hr_5d"], reverse=True
    )
    worst_named = sorted(
        [(k, m) for k, m in named_metrics.items() if m and m.get("hr_5d")],
        key=lambda x: x[1]["hr_5d"]
    )

    lines.append("### 5.1 Where does Atlas perform best?")
    lines.append("")
    for k, m in best_named[:5]:
        lines.append(f"- **{k}**: HR={_fmt(m,'hr_5d')}, n={m['n']:,}, exp={_fmt(m,'expectancy')}")
    lines.append("")

    lines.append("### 5.2 Where does Atlas perform worst?")
    lines.append("")
    for k, m in worst_named[:5]:
        lines.append(f"- **{k}**: HR={_fmt(m,'hr_5d')}, n={m['n']:,}, exp={_fmt(m,'expectancy')}")
    lines.append("")

    lines.append("### 5.3 Which contexts reliably increase accuracy?")
    lines.append("")
    if overall and overall.get("hr_5d"):
        base = overall["hr_5d"]
        improvers = [(k, m) for k, m in best_named if m["hr_5d"] > base + 0.02 and m["n"] >= MIN_N]
        for k, m in improvers[:8]:
            delta = m["hr_5d"] - base
            lines.append(f"- **{k}**: +{delta:.1%} above baseline (HR={_fmt(m,'hr_5d')}, n={m['n']:,})")
    lines.append("")

    lines.append("### 5.4 Which contexts reliably decrease accuracy?")
    lines.append("")
    if overall and overall.get("hr_5d"):
        base = overall["hr_5d"]
        draggers = [(k, m) for k, m in worst_named if m["hr_5d"] < base - 0.02 and m["n"] >= MIN_N]
        for k, m in draggers[:8]:
            delta = m["hr_5d"] - base
            lines.append(f"- **{k}**: {delta:.1%} below baseline (HR={_fmt(m,'hr_5d')}, n={m['n']:,})")
    lines.append("")

    lines.append("### 5.5 Recommended confidence adjustments")
    lines.append("")
    lines.append("Contexts where HR significantly exceeds baseline — candidates for positive confidence multipliers:")
    lines.append("")
    if discovery_results:
        for r in discovery_results[:10]:
            if r.get("hr_5d") and overall and overall.get("hr_5d"):
                delta = r["hr_5d"] - overall["hr_5d"]
                if delta > 0.03:
                    lines.append(f"- **{r['combo']}**: +{delta:.1%} above baseline, n={r['n']:,}")
    lines.append("")
    lines.append("Contexts where HR significantly underperforms — candidates for confidence reduction or exclusion:")
    lines.append("")
    if worst_sorted:
        for r in worst_sorted[:10]:
            if r.get("hr_5d") and overall and overall.get("hr_5d"):
                delta = r["hr_5d"] - overall["hr_5d"]
                if delta < -0.03:
                    lines.append(f"- **{r['combo']}**: {delta:.1%} below baseline, n={r['n']:,}")
    lines.append("")

    # ── Section 6: Yearly stability ───────────────────────────────────────────
    lines.append("## 6. Yearly Accuracy Stability")
    lines.append("")
    lines.append("| Year | N | HR 5d | HR 10d | HR 20d | Expectancy |")
    lines.append("|---|---|---|---|---|---|")
    df["year"] = pd.to_datetime(df["prediction_date"]).dt.year
    for yr, grp in df.groupby("year"):
        m = _metrics(grp, min_n=50)
        if m:
            lines.append(
                f"| {yr} | {m['n']:,} | {_fmt(m,'hr_5d')} "
                f"| {_fmt(m,'hr_10d')} | {_fmt(m,'hr_20d')} "
                f"| {_fmt(m,'expectancy')} |"
            )
    lines.append("")

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    global MIN_N
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-n", type=int, default=MIN_N)
    args = parser.parse_args()
    MIN_N = args.min_n

    print("\nAtlas Prediction Error Analysis")
    print("-" * 60)

    engine = create_engine(os.environ["DATABASE_URL"])

    print("Loading prediction_outcomes from DB...")
    df = load_outcomes(engine)
    if df.empty:
        print("No outcomes in DB. Run compute_prediction_outcomes.py first.")
        return 1
    print(f"  Rows loaded: {len(df):,}")

    print("Computing named context slices...")
    named_metrics = {}
    for name, fn in NAMED_SLICES.items():
        try:
            sub = fn(df)
            named_metrics[name] = _metrics(sub, MIN_N)
        except Exception as exc:
            print(f"  Warning: slice '{name}' failed: {exc}")
            named_metrics[name] = None

    overall = _metrics(df, min_n=1)

    print(f"Running discovery engine ({len(list(combinations(list(COMBO_AXES.keys()),2)))}"
          f" axis-pairs × label combinations)...")
    discovery_results = run_discovery_engine(df, MIN_N)
    print(f"  Valid combinations found: {len(discovery_results):,}")

    print("Building report...")
    report_text = build_report(df, named_metrics, discovery_results, overall)

    REPORT_PATH.parent.mkdir(exist_ok=True)
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    print(f"Report written: {REPORT_PATH}")

    # Console summary
    if overall:
        print(f"\n--- Overall ---")
        print(f"  5d hit rate:  {_fmt(overall,'hr_5d')} (n={overall['n']:,})")
        print(f"  10d hit rate: {_fmt(overall,'hr_10d')}")
        print(f"  Expectancy:   {_fmt(overall,'expectancy')}")

    top5 = [(k, m) for k, m in named_metrics.items() if m and m.get("hr_5d")]
    top5.sort(key=lambda x: x[1]["hr_5d"], reverse=True)
    if top5:
        print(f"\nTop performing contexts:")
        for k, m in top5[:5]:
            print(f"  {k}: HR={_fmt(m,'hr_5d')}, n={m['n']:,}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
