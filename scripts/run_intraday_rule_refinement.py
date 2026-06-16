"""
Atlas Intraday Adaptive Learning Loop v1 -- Rule Refinement Orchestrator
=========================================================================
Runs the full adaptive learning loop for intraday setups:
  1. Load setup outcomes from DB
  2. Compute win/loss attribution (which conditions separate winners from losers)
  3. Generate candidate refinements per setup type
  4. Walk-forward test each candidate against original baseline
  5. Promote only refinements that improve OOS performance
  6. Write attribution + refined rules to DB
  7. Generate INTRADAY_ADAPTIVE_LEARNING_REPORT.md

Schedule: Run weekly (not nightly) -- full refinement is CPU-intensive and
needs enough OOS data per condition to be meaningful.

Usage:
    python scripts/run_intraday_rule_refinement.py
    python scripts/run_intraday_rule_refinement.py --horizon 6
    python scripts/run_intraday_rule_refinement.py --dry-run
    python scripts/run_intraday_rule_refinement.py --setup orb_bull

Does NOT auto-trade. Does NOT loosen thresholds. Does NOT modify daily signals.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from atlas_research.intraday.attribution import (
    load_setups_with_outcomes,
    compute_attribution,
    upsert_attribution,
    _expand_confidence_inputs,
    _add_time_bucket,
    _add_week_label,
    SLIPPAGE_PCT,
)
from atlas_research.intraday.rule_refiner import (
    generate_refinements,
    upsert_refined_rules,
    _metrics,
    MIN_BASE_IS_N,
)

DATABASE_URL = os.environ["DATABASE_URL"]
REPORT_PATH  = Path(__file__).parent.parent / "reports" / "INTRADAY_ADAPTIVE_LEARNING_REPORT.md"
ANALYSIS_HORIZON = 6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt_pct(v, d=3):
    if v is None or (isinstance(v, float) and v != v):
        return "n/a"
    return f"{float(v):+.{d}f}%"

def fmt_f(v, d=2):
    if v is None or (isinstance(v, float) and v != v):
        return "n/a"
    return f"{float(v):.{d}f}"

def fmt_pp(v, d=1):
    if v is None or (isinstance(v, float) and v != v):
        return "n/a"
    return f"{float(v)*100:.{d}f}%"


# ---------------------------------------------------------------------------
# Load base data with all feature columns expanded
# ---------------------------------------------------------------------------

def load_full_df(engine, horizon: int) -> pd.DataFrame:
    df = load_setups_with_outcomes(engine, horizon)
    if df.empty:
        return df
    df = _expand_confidence_inputs(df)
    df = _add_time_bucket(df)
    df = _add_week_label(df)
    return df


# ---------------------------------------------------------------------------
# Per-setup attribution summary (for report)
# ---------------------------------------------------------------------------

def top_attributions_for_setup(attr_df: pd.DataFrame, setup_type: str, direction: str, n: int = 5) -> list[dict]:
    rows = attr_df[
        (attr_df["setup_type"] == setup_type) &
        (attr_df["direction"]  == direction)
    ].copy()
    if rows.empty:
        return []
    rows["abs_effect"] = rows["effect_size"].abs()
    rows = rows.sort_values("abs_effect", ascending=False)
    return rows.head(n).to_dict(orient="records")


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(
    full_df: pd.DataFrame,
    attr_df: pd.DataFrame,
    all_rules: list[dict],
    as_of: str,
) -> str:
    promoted  = [r for r in all_rules if r["status"] == "promoted"]
    candidate = [r for r in all_rules if r["status"] == "candidate"]
    rejected  = [r for r in all_rules if r["status"] == "rejected"]
    generated = [r for r in all_rules if r["status"] == "generated"]

    # Failed setups (negative OOS expectancy in original walk-forward)
    failed_setups = []
    top_setups    = []
    for (st, dir_), grp in full_df.groupby(["setup_type", "direction"]):
        grp = grp.sort_values("ts")
        n   = len(grp)
        sp  = int(n * 0.70)
        is_r  = grp["future_return"].values.astype(float)[:sp]
        oos_r = grp["future_return"].values.astype(float)[sp:]
        m_is  = _metrics(is_r)
        m_oos = _metrics(oos_r)
        entry = {"setup_type": st, "direction": dir_, "n": n,
                 "is_exp": m_is["exp"], "oos_exp": m_oos["exp"],
                 "is_pf": m_is["pf"], "oos_pf": m_oos["pf"]}
        if m_oos["exp"] < -0.02:
            failed_setups.append(entry)
        top_setups.append(entry)

    top_setups   = sorted(top_setups,   key=lambda x: x["oos_exp"], reverse=True)
    failed_setups = sorted(failed_setups, key=lambda x: x["oos_exp"])

    lines = [
        "# Atlas Intraday Adaptive Learning Report v1",
        "",
        f"**Generated:** {as_of}",
        f"**Horizon:** {ANALYSIS_HORIZON} bars (30 minutes)",
        "**Status:** ANALYSIS ONLY. No live trades. No signals changed.",
        "**Method:** 70/30 chronological walk-forward. Slippage: 5 bps/side.",
        "",
        "**Data limitation:** ~60 trading days per ticker (Yahoo Finance free tier).",
        "Results are directional, not statistically definitive.",
        "Most refinements will be rejected or marked 'candidate' due to small OOS samples.",
        "Re-run after 90+ trading days for reliable promotion.",
        "",
        "---",
        "",
        "## 1. Which Setups Failed?",
        "",
        "Setups with OOS expectancy < -0.02% after slippage:",
        "",
        "| Setup | Dir | OOS Exp | OOS PF | n |",
        "|---|---|---|---|---|",
    ]
    for r in failed_setups[:10]:
        lines.append(f"| {r['setup_type']} | {r['direction']} "
                     f"| {fmt_pct(r['oos_exp'])} | {fmt_f(r['oos_pf'])} | {r['n']} |")
    if not failed_setups:
        lines.append("| — | — | No setups with clearly negative OOS performance | — | — |")

    # Q2: Why did they fail?
    lines += [
        "",
        "## 2. Why Did They Fail?",
        "",
        "Top attribution signals for failed setups (|effect size| rank):",
        "",
        "| Setup | Dir | Condition | Winner Avg | Loser Avg | Effect | Confidence |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in failed_setups[:5]:
        tops = top_attributions_for_setup(attr_df, r["setup_type"], r["direction"], n=3)
        for t in tops:
            lines.append(
                f"| {r['setup_type']} | {r['direction']} "
                f"| {t['condition_name']} "
                f"| {fmt_f(t.get('winner_mean'), 3)} "
                f"| {fmt_f(t.get('loser_mean'), 3)} "
                f"| {fmt_f(t.get('effect_size'), 3)} "
                f"| {fmt_pp(t.get('confidence'))} |"
            )
    if not failed_setups or attr_df.empty:
        lines.append("| — | — | Not enough attribution data available | — | — | — | — |")

    # Q3: Conditions that separate winners from losers (across all setups)
    lines += [
        "",
        "## 3. What Conditions Separate Winners from Losers?",
        "",
        "Top 20 attribution signals by absolute effect size (all setups combined):",
        "",
        "| Setup | Dir | Condition | Winner | Loser | Effect | n |",
        "|---|---|---|---|---|---|---|",
    ]
    if not attr_df.empty:
        top_attr = attr_df.copy()
        top_attr["abs_effect"] = top_attr["effect_size"].abs()
        top_attr = top_attr.sort_values("abs_effect", ascending=False).head(20)
        for _, row in top_attr.iterrows():
            lines.append(
                f"| {row['setup_type']} | {row['direction']} "
                f"| {row['condition_name']} "
                f"| {fmt_f(row.get('winner_mean'), 3)} "
                f"| {fmt_f(row.get('loser_mean'), 3)} "
                f"| {fmt_f(row.get('effect_size'), 3)} "
                f"| {int(row.get('sample_size', 0))} |"
            )
    else:
        lines.append("| — | — | Not enough data for attribution | — | — | — | — |")

    # Q4: Which refinements improved results?
    lines += [
        "",
        "## 4. Which Refinements Improved Results?",
        "",
    ]
    if promoted:
        lines += [
            "**PROMOTED** (all walk-forward criteria met):",
            "",
            "| Rule | IS Exp | IS PF | OOS Exp | OOS PF | Tickers | Weeks |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in sorted(promoted, key=lambda x: x.get("oos_expectancy") or -9, reverse=True):
            lines.append(
                f"| **{r['rule_expression']}** "
                f"| {fmt_pct(r.get('refined_expectancy'))} "
                f"| {fmt_f(r.get('refined_pf'))} "
                f"| {fmt_pct(r.get('oos_expectancy'))} "
                f"| {fmt_f(r.get('oos_pf'))} "
                f"| {r.get('multi_ticker_breadth',0)} "
                f"| {r.get('multi_week_breadth',0)} |"
            )
    else:
        lines.append("No refinements promoted with current data volume.")

    if candidate:
        lines += [
            "",
            "**CANDIDATE** (OOS positive but not all criteria met):",
            "",
            "| Rule | Orig Exp | Refined Exp | OOS Exp | OOS PF | Tickers | Weeks | Notes |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in sorted(candidate, key=lambda x: x.get("oos_expectancy") or -9, reverse=True)[:10]:
            lines.append(
                f"| {r['rule_expression']} "
                f"| {fmt_pct(r.get('original_expectancy'))} "
                f"| {fmt_pct(r.get('refined_expectancy'))} "
                f"| {fmt_pct(r.get('oos_expectancy'))} "
                f"| {fmt_f(r.get('oos_pf'))} "
                f"| {r.get('multi_ticker_breadth',0)} "
                f"| {r.get('multi_week_breadth',0)} "
                f"| {(r.get('reject_reason') or '')[:50]} |"
            )

    # Q5: Which refinements were overfit?
    overfit = [r for r in rejected if
               (r.get("refined_expectancy") or 0) > (r.get("original_expectancy") or 0) and
               (r.get("oos_expectancy") or -1) <= 0]
    lines += [
        "",
        "## 5. Which Refinements Were Overfit?",
        "",
        "Improved IS but failed OOS:",
        "",
        "| Rule | IS Exp | OOS Exp | Reject Reason |",
        "|---|---|---|---|",
    ]
    for r in sorted(overfit, key=lambda x: x.get("refined_expectancy") or 0, reverse=True)[:10]:
        lines.append(
            f"| {r['rule_expression']} "
            f"| {fmt_pct(r.get('refined_expectancy'))} "
            f"| {fmt_pct(r.get('oos_expectancy'))} "
            f"| {(r.get('reject_reason') or '')[:70]} |"
        )
    if not overfit:
        lines.append("| — | — | — | No clearly overfit refinements detected |")

    # Q6: Which rules to watch?
    lines += [
        "",
        "## 6. Which Refined Rules Should Be Watched?",
        "",
        "Candidates and near-candidates (positive OOS, not yet promoted):",
        "",
        "| Rule | OOS Exp | OOS PF | Tickers | Weeks | Missing Criteria |",
        "|---|---|---|---|---|---|",
    ]
    watchlist = [r for r in all_rules if
                 (r.get("oos_expectancy") or -1) > 0 and r["status"] != "promoted"]
    watchlist = sorted(watchlist, key=lambda x: x.get("oos_expectancy") or -9, reverse=True)
    for r in watchlist[:12]:
        lines.append(
            f"| {r['rule_expression'][:55]} "
            f"| {fmt_pct(r.get('oos_expectancy'))} "
            f"| {fmt_f(r.get('oos_pf'))} "
            f"| {r.get('multi_ticker_breadth',0)} "
            f"| {r.get('multi_week_breadth',0)} "
            f"| {(r.get('reject_reason') or '')[:50]} |"
        )
    if not watchlist:
        lines.append("| — | — | — | — | — | Insufficient data for any watchlist entries |")

    # Q7: Promotable rules
    lines += [
        "",
        "## 7. Which Rules Are Promotable?",
        "",
    ]
    if promoted:
        lines.append(f"**{len(promoted)} rule(s) are promotable:**")
        for r in promoted:
            lines.append(
                f"- **{r['rule_expression']}**: "
                f"OOS Exp={fmt_pct(r.get('oos_expectancy'))}, "
                f"OOS PF={fmt_f(r.get('oos_pf'))}, "
                f"{r.get('multi_ticker_breadth',0)} tickers, "
                f"{r.get('multi_week_breadth',0)} weeks"
            )
    else:
        lines += [
            "No rules promotable at current data volume.",
            "",
            "**What is needed:**",
            f"- ~90+ trading days per ticker (currently ~60)",
            f"- OOS n >= 5 per refinement (most refinements have OOS n < 5 after filtering)",
            f"- 3+ tickers represented in OOS (many refinements are concentrated)",
            "",
            "**Recommendation:** Continue daily ingestion. Re-run refinement after 90 days.",
        ]

    # Summary stats
    lines += [
        "",
        "## 8. Refinement Summary Statistics",
        "",
        f"| Metric | Value |",
        "|---|---|",
        f"| Total setup types analyzed | {full_df['setup_type'].nunique()} |",
        f"| Setup types with enough IS data (n>={MIN_BASE_IS_N}) | "
        f"{sum(1 for (_, _), g in full_df.groupby(['setup_type','direction']) if int(len(g)*0.7)>=MIN_BASE_IS_N)} |",
        f"| Attribution conditions tested | {len(attr_df)} |",
        f"| Refinements generated | {len(all_rules)} |",
        f"| Promoted | {len(promoted)} |",
        f"| Candidate (watch) | {len(candidate)} |",
        f"| Rejected (overfit/low sample) | {len(rejected)} |",
        "",
        "## 9. Top Setups Baseline (OOS Expectancy)",
        "",
        "| Setup | Dir | IS Exp | OOS Exp | OOS PF | n |",
        "|---|---|---|---|---|---|",
    ]
    for r in top_setups[:10]:
        lines.append(
            f"| {r['setup_type']} | {r['direction']} "
            f"| {fmt_pct(r['is_exp'])} | {fmt_pct(r['oos_exp'])} "
            f"| {fmt_f(r['oos_pf'])} | {r['n']} |"
        )

    lines += [
        "",
        "---",
        f"_Generated by run_intraday_rule_refinement.py on {as_of}_",
        "_Analysis only. No live trading. No signals changed._",
        f"_Promotion criteria: OOS exp>0, OOS PF>original PF, "
        f">={MIN_BASE_IS_N} IS samples, >=3 tickers, >=3 weeks, outlier sensitivity<40%_",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizon",  type=int, default=ANALYSIS_HORIZON)
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--setup",    type=str, default=None,
                        help="Only process this setup_type (for debugging)")
    args = parser.parse_args()

    as_of  = date.today()
    as_of_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    engine = create_engine(DATABASE_URL)

    print("=== Atlas Intraday Adaptive Learning Loop v1 ===")
    print(f"As-of: {as_of_str}  horizon={args.horizon} bars ({args.horizon*5} min)")
    print("ANALYSIS ONLY -- no live trading state modified")
    print()

    # Step 1: Load data
    print("[1/6] Loading setup outcomes from DB...")
    full_df = load_full_df(engine, args.horizon)
    if full_df.empty:
        print("  No data -- run ingest_intraday_5m.py first.")
        return
    print(f"  {len(full_df):,} setups  |  {full_df['setup_type'].nunique()} types  |  "
          f"{full_df['ticker'].nunique()} tickers")

    if args.setup:
        full_df = full_df[full_df["setup_type"] == args.setup]
        print(f"  Filtered to setup '{args.setup}': {len(full_df)} setups")
        if full_df.empty:
            print("  No data for this setup.")
            return

    # Step 2: Win/loss attribution
    print("[2/6] Computing win/loss attribution...")
    attr_df = compute_attribution(full_df, as_of)
    print(f"  {len(attr_df)} attribution conditions computed")
    if not attr_df.empty:
        top = attr_df.copy()
        top["abs_eff"] = top["effect_size"].abs()
        top = top.sort_values("abs_eff", ascending=False).head(5)
        for _, row in top.iterrows():
            print(f"  {row['setup_type']:<26} {row['direction']:<6} "
                  f"{row['condition_name']:<35} effect={row['effect_size']:+.3f}")

    if not args.dry_run:
        print("  Writing attribution to DB...")
        n_attr = upsert_attribution(attr_df, engine)
        print(f"  -> {n_attr} rows written")

    # Step 3–4: Generate and test refinements
    print()
    print("[3/6] Generating and testing candidate refinements...")
    all_rules: list[dict] = []

    for (st, direction), grp in full_df.groupby(["setup_type", "direction"]):
        grp = grp.sort_values("ts").reset_index(drop=True)
        n_is = int(len(grp) * 0.70)
        if n_is < MIN_BASE_IS_N:
            continue

        setup_attr = attr_df[
            (attr_df["setup_type"] == st) &
            (attr_df["direction"]  == direction)
        ] if not attr_df.empty else pd.DataFrame()

        rules = generate_refinements(st, direction, grp, setup_attr, as_of)
        all_rules.extend(rules)

        if rules:
            n_promo = sum(1 for r in rules if r["status"] == "promoted")
            n_cand  = sum(1 for r in rules if r["status"] == "candidate")
            n_rej   = sum(1 for r in rules if r["status"] == "rejected")
            print(f"  {st}/{direction}: {len(rules)} rules  "
                  f"[promoted={n_promo} candidate={n_cand} rejected={n_rej}]")

    print(f"\n  Total: {len(all_rules)} refinements")
    promoted_list  = [r for r in all_rules if r["status"] == "promoted"]
    candidate_list = [r for r in all_rules if r["status"] == "candidate"]
    rejected_list  = [r for r in all_rules if r["status"] == "rejected"]
    print(f"  Promoted:  {len(promoted_list)}")
    print(f"  Candidate: {len(candidate_list)}")
    print(f"  Rejected:  {len(rejected_list)}")

    # Step 5: Write to DB
    if not args.dry_run and all_rules:
        print()
        print("[4/6] Writing refined rules to DB...")
        n_rules = upsert_refined_rules(all_rules, engine)
        print(f"  -> {n_rules} rows written to intraday_refined_rules")

    # Step 6: Generate report
    print()
    print("[5/6] Generating INTRADAY_ADAPTIVE_LEARNING_REPORT.md...")
    report = generate_report(full_df, attr_df, all_rules, as_of_str)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  -> {REPORT_PATH}")

    # Final summary
    print()
    print("=== Results ===")
    if promoted_list:
        print("PROMOTED rules:")
        for r in sorted(promoted_list, key=lambda x: x.get("oos_expectancy") or -9, reverse=True):
            print(f"  {r['rule_expression'][:70]}")
            print(f"    OOS Exp={fmt_pct(r.get('oos_expectancy'))}  "
                  f"OOS PF={fmt_f(r.get('oos_pf'))}  "
                  f"Tickers={r.get('multi_ticker_breadth',0)}  "
                  f"Weeks={r.get('multi_week_breadth',0)}")
    else:
        print("No rules promoted. Best candidates:")
        best = sorted(
            [r for r in all_rules if (r.get("oos_expectancy") or -9) > -9],
            key=lambda x: x.get("oos_expectancy") or -9,
            reverse=True,
        )[:5]
        for r in best:
            print(f"  [{r['status'].upper():10}] {r['rule_expression'][:60]}")
            print(f"    OOS Exp={fmt_pct(r.get('oos_expectancy'))}  "
                  f"OOS PF={fmt_f(r.get('oos_pf'))}  "
                  f"Reason: {(r.get('reject_reason') or 'n/a')[:50]}")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
