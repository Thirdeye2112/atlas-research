#!/usr/bin/env python
"""
aggregate_pattern_fulfillment.py
===================================
Reads research_pattern_fulfillment for the given (or latest) run_id and
computes every statistic the report needs: Stage A accounting, Stage B
expectancy (in-sample/held-out/baseline), Welch's t-test of held-out
pattern expectancy vs held-out baseline (same timeframe, pooled across
tickers), BH-FDR correction across that whole cell universe, and the
Step 4 inversion expectancy (same structure, vs the same baseline).

Pure aggregation -- no new measurement. Writes
reports/research/pattern_fulfillment_summary.json, consumed by
generate_pattern_fulfillment_report.py.

Usage (cwd = C:\\Atlas\\atlas-research):
    .venv\\Scripts\\python.exe scripts\\research\\aggregate_pattern_fulfillment.py [--run-id ID]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from pattern_fulfillment_common import (
    DATABASE_URL, MIN_CELL_N, BH_FDR_Q, expectancy_stats, welch_t_pvalue, bh_fdr,
)

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = WORKTREE_ROOT / "reports" / "research"


def load_data(engine, run_id: str | None) -> pd.DataFrame:
    if run_id is None:
        run_id = pd.read_sql(text("SELECT run_id FROM research_pattern_fulfillment "
                                   "ORDER BY created_at DESC LIMIT 1"), engine).iloc[0, 0]
    df = pd.read_sql(text("SELECT * FROM research_pattern_fulfillment WHERE run_id = :r"),
                      engine, params={"r": run_id})
    return df, run_id


def cell_stats(sub_is: pd.Series, sub_ho: pd.Series, base_is: pd.Series, base_ho: pd.Series) -> dict:
    return {
        "in_sample": expectancy_stats(sub_is),
        "held_out": expectancy_stats(sub_ho),
        "baseline_in_sample": expectancy_stats(base_is),
        "baseline_held_out": expectancy_stats(base_ho),
        "p_value_vs_baseline_held_out": welch_t_pvalue(sub_ho, base_ho),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    df, run_id = load_data(engine, args.run_id)
    print(f"Loaded {len(df)} rows for run_id={run_id}")

    baseline = df[df["pattern_type"] == "__BASELINE__"]
    patterns = df[df["pattern_type"] != "__BASELINE__"]

    # ---- Stage A accounting per (pattern_type, timeframe) -------------------
    stage_a = {}
    for (pt, tf), g in patterns.groupby(["pattern_type", "timeframe"]):
        counts = g["stage_a_outcome"].value_counts().to_dict()
        total = len(g)
        stage_a[f"{pt}|{tf}"] = {
            "pattern_type": pt, "timeframe": tf, "total": int(total),
            "confirmed": int(counts.get("CONFIRMED", 0)),
            "invalidated": int(counts.get("INVALIDATED", 0)),
            "neither_a": int(counts.get("NEITHER_A", 0)),
            "confirmed_pct": counts.get("CONFIRMED", 0) / total if total else None,
            "invalidated_pct": counts.get("INVALIDATED", 0) / total if total else None,
            "neither_pct": counts.get("NEITHER_A", 0) / total if total else None,
        }

    # ---- Stage B expectancy vs baseline, per (pattern_type, timeframe) -----
    expectancy_cells = {}
    pvals_for_fdr = {}
    confirmed = patterns[(patterns["stage_a_outcome"] == "CONFIRMED") & patterns["realized_r_b"].notna()]
    for (pt, tf), g in confirmed.groupby(["pattern_type", "timeframe"]):
        base_tf = baseline[baseline["timeframe"] == tf]
        sub_is = g[g["in_sample_flag"]]["realized_r_b"]
        sub_ho = g[~g["in_sample_flag"]]["realized_r_b"]
        base_is = base_tf[base_tf["in_sample_flag"]]["realized_r_b"]
        base_ho = base_tf[~base_tf["in_sample_flag"]]["realized_r_b"]
        key = f"{pt}|{tf}"
        cs = cell_stats(sub_is, sub_ho, base_is, base_ho)
        expectancy_cells[key] = {"pattern_type": pt, "timeframe": tf, **cs}
        if cs["held_out"]["n"] >= MIN_CELL_N:
            pvals_for_fdr[key] = cs["p_value_vs_baseline_held_out"]

    pvals_series = pd.Series(pvals_for_fdr)
    survives = bh_fdr(pvals_series, q=BH_FDR_Q)
    for key, flag in survives.items():
        expectancy_cells[key]["bh_fdr_survives"] = bool(flag)
    for key in expectancy_cells:
        expectancy_cells[key].setdefault("bh_fdr_survives", False)

    # ---- Step 4: inversion expectancy vs baseline ---------------------------
    inversion_cells = {}
    inv_pvals_for_fdr = {}
    inv = patterns[(patterns["inversion_tested"]) & patterns["realized_r_c"].notna()]
    for (pt, tf), g in inv.groupby(["pattern_type", "timeframe"]):
        base_tf = baseline[baseline["timeframe"] == tf]
        sub_is = g[g["in_sample_flag"]]["realized_r_c"]
        sub_ho = g[~g["in_sample_flag"]]["realized_r_c"]
        base_is = base_tf[base_tf["in_sample_flag"]]["realized_r_b"]
        base_ho = base_tf[~base_tf["in_sample_flag"]]["realized_r_b"]
        key = f"{pt}|{tf}"
        cs = cell_stats(sub_is, sub_ho, base_is, base_ho)
        inversion_cells[key] = {"pattern_type": pt, "timeframe": tf, **cs}
        if cs["held_out"]["n"] >= MIN_CELL_N:
            inv_pvals_for_fdr[key] = cs["p_value_vs_baseline_held_out"]

    inv_pvals_series = pd.Series(inv_pvals_for_fdr)
    inv_survives = bh_fdr(inv_pvals_series, q=BH_FDR_Q)
    for key, flag in inv_survives.items():
        inversion_cells[key]["bh_fdr_survives"] = bool(flag)
    for key in inversion_cells:
        inversion_cells[key].setdefault("bh_fdr_survives", False)

    # ---- baseline summary itself, by timeframe ------------------------------
    baseline_summary = {}
    for tf, g in baseline.groupby("timeframe"):
        baseline_summary[tf] = {
            "in_sample": expectancy_stats(g[g["in_sample_flag"]]["realized_r_b"]),
            "held_out": expectancy_stats(g[~g["in_sample_flag"]]["realized_r_b"]),
        }

    summary = {
        "run_id": run_id,
        "n_total_rows": int(len(df)),
        "n_pattern_rows": int(len(patterns)),
        "n_baseline_rows": int(len(baseline)),
        "n_expectancy_cells_tested": len(pvals_for_fdr),
        "n_expectancy_cells_survive_bh_fdr": int(survives.sum()),
        "n_inversion_cells_tested": len(inv_pvals_for_fdr),
        "n_inversion_cells_survive_bh_fdr": int(inv_survives.sum()),
        "bh_fdr_q": BH_FDR_Q,
        "min_cell_n": MIN_CELL_N,
        "stage_a": stage_a,
        "expectancy_cells": expectancy_cells,
        "inversion_cells": inversion_cells,
        "baseline_summary": baseline_summary,
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / "pattern_fulfillment_summary.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Wrote {out_path}")
    print(f"Expectancy cells: {len(expectancy_cells)} tested, {len(pvals_for_fdr)} eligible (n>={MIN_CELL_N}), "
          f"{int(survives.sum())} survive BH-FDR q={BH_FDR_Q}")
    print(f"Inversion cells: {len(inversion_cells)} tested, {len(inv_pvals_for_fdr)} eligible, "
          f"{int(inv_survives.sum())} survive BH-FDR")


if __name__ == "__main__":
    main()
