#!/usr/bin/env python
"""
aggregate_dome_leg_signature.py
==================================
Reads research_dome_leg_signature / research_dome_leg_realtime for the
given (or latest) run_id and computes every statistic the report needs:
  (A) leg-start vs leg-peak/trough geometry congruence, pooled and by leg_dir
  (B) early-signature correlation (early_gain/slope vs leg_amp/corr_depth),
      split in-sample vs held-out (does it replicate OOS?), and a
      non-tautological version restricted to leg_bars > EARLY_N
  (C) real-time shape-filter forward return vs. baseline, by filter_type and
      K, in-sample vs held-out, with a Welch's t-test p-value

Pure aggregation -- no new measurement. Writes
reports/research/dome_leg_signature_summary.json.

Usage (cwd = C:\\Atlas\\atlas-research):
    .venv\\Scripts\\python.exe scripts\\research\\aggregate_dome_leg_signature.py [--run-id ID]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from dome_leg_signature_common import DATABASE_URL, EARLY_N, ci95_mean, welch_t_pvalue, pearson_with_p

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = WORKTREE_ROOT / "reports" / "research"


def load_data(engine, run_id):
    if run_id is None:
        run_id = pd.read_sql(text("SELECT run_id FROM research_dome_leg_signature "
                                   "ORDER BY created_at DESC LIMIT 1"), engine).iloc[0, 0]
    legs = pd.read_sql(text("SELECT * FROM research_dome_leg_signature WHERE run_id = :r"),
                        engine, params={"r": run_id})
    rt = pd.read_sql(text("SELECT * FROM research_dome_leg_realtime WHERE run_id = :r"),
                      engine, params={"r": run_id})
    return legs, rt, run_id


def part_a(legs: pd.DataFrame) -> dict:
    out = {}
    feats = ["body_pct", "upper_wick_pct", "lower_wick_pct", "rng_atr_ratio", "vol_ratio", "close_loc"]
    for leg_dir in ("up", "down"):
        sub = legs[legs["leg_dir"] == leg_dir]
        row = {"n": int(len(sub))}
        for f in feats:
            row[f] = {"start_mean": float(sub[f"start_{f}"].mean()), "peak_mean": float(sub[f"peak_{f}"].mean())}
        row["is_green_pct"] = {"start": float(sub["start_is_green"].mean()), "peak": float(sub["peak_is_green"].mean())}
        out[leg_dir] = row
    return out


def part_b(legs: pd.DataFrame) -> dict:
    out = {}
    for leg_dir in ("up", "down"):
        sub = legs[legs["leg_dir"] == leg_dir]
        long_legs = sub[sub["leg_bars"] > EARLY_N]
        cell = {}
        for portion_name, portion in (("in_sample", sub[sub["in_sample_flag"]]),
                                       ("held_out", sub[~sub["in_sample_flag"]])):
            long_portion = portion[portion["leg_bars"] > EARLY_N]
            cell[portion_name] = {
                "n": int(len(portion)),
                "corr_early_gain_leg_amp_all": pearson_with_p(portion["early_gain"], portion["leg_amp"]),
                "corr_early_gain_leg_amp_nontautological": pearson_with_p(long_portion["early_gain"], long_portion["leg_amp"]),
                "corr_early_slope_corr_depth": pearson_with_p(portion["early_slope"], portion["corr_depth"]),
                "n_nontautological": int(len(long_portion)),
            }
        out[leg_dir] = cell
    return out


def part_c(rt: pd.DataFrame) -> dict:
    out = {}
    base = rt[rt["filter_type"] == "__BASELINE__"]
    for filt in ("bottom_like", "top_like"):
        sub = rt[rt["filter_type"] == filt]
        out[filt] = {}
        for k, gk in sub.groupby("forward_k"):
            base_k = base[base["forward_k"] == k]
            cell = {}
            for portion_name, flag in (("in_sample", True), ("held_out", False)):
                s = gk[gk["in_sample_flag"] == flag]["forward_r"]
                b = base_k[base_k["in_sample_flag"] == flag]["forward_r"]
                cell[portion_name] = {
                    "pattern": ci95_mean(s), "baseline": ci95_mean(b),
                    "p_vs_baseline": welch_t_pvalue(s, b),
                }
            out[filt][int(k)] = cell
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    legs, rt, run_id = load_data(engine, args.run_id)
    print(f"Loaded {len(legs)} leg rows, {len(rt)} realtime rows for run_id={run_id}")

    summary = {
        "run_id": run_id,
        "n_legs": int(len(legs)),
        "n_realtime_rows": int(len(rt)),
        "part_a_congruence": part_a(legs),
        "part_b_early_signature": part_b(legs),
        "part_c_realtime_filter": part_c(rt),
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / "dome_leg_signature_summary.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
