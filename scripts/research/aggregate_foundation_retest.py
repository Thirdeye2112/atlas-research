#!/usr/bin/env python
"""
aggregate_foundation_retest.py
=================================
Reads research_foundation_retest / research_foundation_retest_baseline for
the given (or latest) run_id and computes everything the report needs:
  - per (trigger_type, K): expectancy in-sample/held-out vs. the matching
    random-direction baseline cell, Welch's t-test, BH-FDR across the full
    cell pool (the Step 4 multiple-testing correction)
  - per trigger_type (K=6 only, to bound the extra multiple-testing cost):
    daily_agrees=True vs False edge-over-baseline comparison (Step 3)
  - a trivial "last-bar-momentum" baseline (Step 4 Check 3): same direction
    as the trigger, entered purely because the PRIOR bar was that color, no
    tool involved -- does the tool add anything over plain momentum?

Pure aggregation -- no new measurement. Writes
reports/research/foundation_retest_summary.json.

Usage (cwd = C:\\Atlas\\atlas-research):
    .venv\\Scripts\\python.exe scripts\\research\\aggregate_foundation_retest.py [--run-id ID]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

from foundation_retest_common import (
    DATABASE_URL, MIN_CELL_N, BH_FDR_Q, K_VALUES, TICKER,
    expectancy_stats, welch_t_pvalue, bh_fdr, r_bracket_outcome,
)

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = WORKTREE_ROOT / "reports" / "research"

HEADLINE_K = 6


def load_data(engine, run_id):
    if run_id is None:
        run_id = pd.read_sql(text("SELECT run_id FROM research_foundation_retest "
                                   "ORDER BY created_at DESC LIMIT 1"), engine).iloc[0, 0]
    trig = pd.read_sql(text("SELECT * FROM research_foundation_retest WHERE run_id = :r"), engine, params={"r": run_id})
    base = pd.read_sql(text("SELECT * FROM research_foundation_retest_baseline WHERE run_id = :r"), engine, params={"r": run_id})
    return trig, base, run_id


def momentum_baseline(engine, ticker: str) -> pd.DataFrame:
    """Trivial baseline: direction = same color as the PRIOR bar (pure
    momentum continuation, no tool). Same R-bracket, same K grid."""
    from atlas_research.intraday.features import compute_features
    bars = pd.read_sql(text("SELECT ticker, ts, open, high, low, close, volume FROM intraday_bars "
                             "WHERE ticker = :t AND timeframe = '5m' ORDER BY ts"), engine, params={"t": ticker})
    bars["ts"] = pd.to_datetime(bars["ts"], utc=True)
    feat = compute_features(bars)
    h = feat["high"].to_numpy(float); l = feat["low"].to_numpy(float); c = feat["close"].to_numpy(float)
    atr = feat["atr14"].to_numpy(float)
    is_green = feat["is_green"].to_numpy(); is_red = feat["is_red"].to_numpy()
    n = len(c)
    valid = ~np.isnan(atr)
    rows = []
    for i0 in range(1, n):
        if not valid[i0]:
            continue
        if is_green[i0 - 1]:
            direction = "long"
        elif is_red[i0 - 1]:
            direction = "short"
        else:
            continue
        for k in K_VALUES:
            res = r_bracket_outcome(direction, c[i0], atr[i0], h, l, c, i0, k_cap=k)
            rows.append({"idx": i0, "forward_k": k, "realized_r": res["realized_R"]})
    return pd.DataFrame(rows)


def cell_stats(sub_is, sub_ho, base_is, base_ho) -> dict:
    return {
        "in_sample": expectancy_stats(sub_is), "held_out": expectancy_stats(sub_ho),
        "baseline_in_sample": expectancy_stats(base_is), "baseline_held_out": expectancy_stats(base_ho),
        "p_value_vs_baseline_held_out": welch_t_pvalue(sub_ho, base_ho),
        "edge_over_baseline_held_out": (expectancy_stats(sub_ho)["expectancy_R"] - expectancy_stats(base_ho)["expectancy_R"]
                                          if expectancy_stats(sub_ho)["n"] and expectancy_stats(base_ho)["n"] else np.nan),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    trig, base, run_id = load_data(engine, args.run_id)
    print(f"Loaded {len(trig)} trigger rows, {len(base)} baseline rows for run_id={run_id}")

    # ---- primary: trigger_type x K vs baseline -------------------------------
    expectancy_cells = {}
    pvals_for_fdr = {}
    for (ttype, k), g in trig.groupby(["trigger_type", "forward_k"]):
        base_k = base[base["forward_k"] == k]
        sub_is = g[g["in_sample_flag"]]["realized_r"]
        sub_ho = g[~g["in_sample_flag"]]["realized_r"]
        base_is = base_k[base_k["in_sample_flag"]]["realized_r"]
        base_ho = base_k[~base_k["in_sample_flag"]]["realized_r"]
        key = f"{ttype}|K{k}"
        cs = cell_stats(sub_is, sub_ho, base_is, base_ho)
        expectancy_cells[key] = {"trigger_type": ttype, "k": int(k), **cs}
        if cs["held_out"]["n"] >= MIN_CELL_N:
            pvals_for_fdr[key] = cs["p_value_vs_baseline_held_out"]

    pvals_series = pd.Series(pvals_for_fdr)
    survives = bh_fdr(pvals_series, q=BH_FDR_Q)
    for key, flag in survives.items():
        expectancy_cells[key]["bh_fdr_survives"] = bool(flag)
    for key in expectancy_cells:
        expectancy_cells[key].setdefault("bh_fdr_survives", False)

    n_cells_tested = len(pvals_for_fdr)
    n_cells_survive = int(survives.sum())
    print(f"Primary cells: {len(expectancy_cells)} total, {n_cells_tested} eligible (n>={MIN_CELL_N}), "
          f"{n_cells_survive} survive BH-FDR q={BH_FDR_Q}")

    # ---- secondary: daily agreement, K=6 only --------------------------------
    daily_cells = {}
    daily_pvals = {}
    g6 = trig[trig["forward_k"] == HEADLINE_K]
    base6 = base[base["forward_k"] == HEADLINE_K]
    for ttype, g in g6.groupby("trigger_type"):
        cell = {}
        for portion_name, flag in (("in_sample", True), ("held_out", False)):
            gp = g[g["in_sample_flag"] == flag]
            agree = gp[gp["daily_agrees"] == True]["realized_r"]
            disagree = gp[gp["daily_agrees"] == False]["realized_r"]
            base_p = base6[base6["in_sample_flag"] == flag]["realized_r"]
            cell[portion_name] = {
                "agrees": expectancy_stats(agree), "disagrees": expectancy_stats(disagree),
                "baseline": expectancy_stats(base_p),
                "p_agree_vs_disagree": welch_t_pvalue(agree, disagree),
            }
        key = ttype
        daily_cells[key] = {"trigger_type": ttype, **cell}
        ho = cell["held_out"]
        if ho["agrees"]["n"] >= MIN_CELL_N and ho["disagrees"]["n"] >= MIN_CELL_N:
            daily_pvals[key] = ho["p_agree_vs_disagree"]

    daily_survives = bh_fdr(pd.Series(daily_pvals), q=BH_FDR_Q)
    for key, flag in daily_survives.items():
        daily_cells[key]["bh_fdr_survives_agreement_diff"] = bool(flag)
    for key in daily_cells:
        daily_cells[key].setdefault("bh_fdr_survives_agreement_diff", False)

    n_daily_tested = len(daily_pvals)
    n_daily_survive = int(daily_survives.sum())
    print(f"Daily-agreement cells: {len(daily_cells)} total, {n_daily_tested} eligible, "
          f"{n_daily_survive} survive BH-FDR")

    # ---- trivial momentum baseline, for cells that survived the primary test -
    print("Computing trivial last-bar-momentum baseline ...")
    mom_df = momentum_baseline(engine, TICKER)
    momentum_by_k = {}
    for k, g in mom_df.groupby("forward_k"):
        momentum_by_k[int(k)] = expectancy_stats(g["realized_r"])
        print(f"  K={k}: momentum baseline expectancy={momentum_by_k[int(k)]['expectancy_R']:.4f} (n={momentum_by_k[int(k)]['n']})")

    baseline_summary = {}
    for k, g in base.groupby("forward_k"):
        baseline_summary[int(k)] = {
            "in_sample": expectancy_stats(g[g["in_sample_flag"]]["realized_r"]),
            "held_out": expectancy_stats(g[~g["in_sample_flag"]]["realized_r"]),
        }

    summary = {
        "run_id": run_id, "ticker": TICKER,
        "n_trigger_rows": int(len(trig)), "n_baseline_rows": int(len(base)),
        "n_primary_cells_tested": n_cells_tested, "n_primary_cells_survive_bh_fdr": n_cells_survive,
        "n_daily_cells_tested": n_daily_tested, "n_daily_cells_survive_bh_fdr": n_daily_survive,
        "total_multiple_testing_denominator": n_cells_tested + n_daily_tested,
        "bh_fdr_q": BH_FDR_Q, "min_cell_n": MIN_CELL_N,
        "expectancy_cells": expectancy_cells,
        "daily_agreement_cells": daily_cells,
        "random_baseline_summary": baseline_summary,
        "momentum_baseline_summary": momentum_by_k,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / "foundation_retest_summary.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Wrote {out_path}")
    print(f"\nTOTAL MULTIPLE-TESTING DENOMINATOR: {n_cells_tested + n_daily_tested} cells "
          f"({n_cells_tested} primary + {n_daily_tested} daily-agreement)")
    print(f"Survivors: {n_cells_survive} primary + {n_daily_survive} daily-agreement")


if __name__ == "__main__":
    main()
