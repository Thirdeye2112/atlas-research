#!/usr/bin/env python
"""
run_dome_leg_verify_full.py
==============================
Master runner: executes all 5 adversarial checks against the dome-leg
early-signature result, writes every metric to research_dome_leg_verification
(long format), and renders reports/research/DOME_LEG_VERIFICATION.md.

Usage (cwd = C:\\Atlas\\atlas-research):
    .venv\\Scripts\\python.exe scripts\\research\\run_dome_leg_verify_full.py
"""
from __future__ import annotations

import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text
from psycopg2.extras import execute_values

from dome_leg_verify import (
    DATABASE_URL, ORIGINAL_3, FRESH_5, PIVOT_WIDTH, AMP_MULT, EARLY_N,
    process_ticker, legs_to_df, pearson_p, permutation_test, check4_recompute_from_raw,
)
from dome_leg_verify_corrdepth import build_corrdepth_check
from atlas_research.intraday.features import compute_features
from atlas_research.ta.structure import swing_pivots
from dome_leg_verify import significant_pivots, load_5m_bars

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = WORKTREE_ROOT / "reports" / "research"
REPORT_PATH = REPORTS_DIR / "DOME_LEG_VERIFICATION.md"

ROWS = []  # (check_name, scope, leg_dir, metric_name, metric_value, n, p_value, notes)


def log(check, scope, leg_dir, metric, value, n=None, p=None, notes=None):
    ROWS.append((check, scope, leg_dir, metric,
                  None if value is None or (isinstance(value, float) and np.isnan(value)) else float(value),
                  None if n is None else int(n),
                  None if p is None or (isinstance(p, float) and np.isnan(p)) else float(p),
                  notes))


def get_git_info():
    def _git(*a):
        try:
            return subprocess.check_output(["git", *a], cwd=str(WORKTREE_ROOT), text=True).strip()
        except Exception as e:
            return f"<unavailable: {e}>"
    return {"commit": _git("rev-parse", "HEAD"), "branch": _git("rev-parse", "--abbrev-ref", "HEAD")}


def main():
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    git_info = get_git_info()
    print(f"[run_id={run_id}] git={git_info}")

    print("Loading legs for original_3 + fresh_5 ...")
    all_legs = {}
    for ticker in ORIGINAL_3 + FRESH_5:
        legs = process_ticker(engine, ticker)
        all_legs[ticker] = legs
        print(f"  {ticker}: {len(legs)} non-tautological (leg_bars>{EARLY_N}) legs")

    # ============= CHECK 1 + 2 + 3 (combined, per scope/leg_dir) =============
    check123 = {}
    for scope, tickers in [("original_3", ORIGINAL_3), ("fresh_5", FRESH_5)]:
        df = legs_to_df([l for t in tickers for l in all_legs[t]])
        check123[scope] = {}
        for leg_dir in ("up", "down"):
            sub = df[df["leg_dir"] == leg_dir]

            r_naive, n_naive, p_naive = pearson_p(sub["early_gain_naive"], sub["leg_amp"])
            log("check1_tautology", scope, leg_dir, "r_early_vs_TOTAL_leg_amp", r_naive, n_naive, p_naive,
                "ORIGINAL definition: replicates the prior report's headline r")

            valid_rem = sub.dropna(subset=["remaining_amp_naive"])
            r_disj, n_disj, p_disj = pearson_p(valid_rem["early_gain_naive"], valid_rem["remaining_amp_naive"])
            log("check1_tautology", scope, leg_dir, "r_early_vs_REMAINING_amp_disjoint", r_disj, n_disj, p_disj,
                "FIX: leg size measured only AFTER the early window (no accounting overlap)")

            conf = sub.dropna(subset=["early_gain_confirmed", "remaining_amp_confirmed"])
            r_conf, n_conf, p_conf = pearson_p(conf["early_gain_confirmed"], conf["remaining_amp_confirmed"])
            log("check2_lookahead", scope, leg_dir, "r_early_confirmed_vs_remaining_disjoint", r_conf, n_conf, p_conf,
                "FIX: early window starts at the CONFIRMATION bar (a.idx+width), not the pivot bar itself")

            real_r, perm_rs, perm_p = permutation_test(valid_rem["early_gain_naive"], valid_rem["remaining_amp_naive"], n_perm=2000)
            log("check3_permutation", scope, leg_dir, "real_r_disjoint", real_r, n_disj, None)
            log("check3_permutation", scope, leg_dir, "perm_null_mean", float(perm_rs.mean()), None, None)
            log("check3_permutation", scope, leg_dir, "perm_null_std", float(perm_rs.std()), None, None)
            log("check3_permutation", scope, leg_dir, "perm_p_value", perm_p, None, perm_p,
                "fraction of 2000 reshuffled pairings with |r| >= real disjoint r")

            r_triv_tot, n_triv_tot, p_triv_tot = pearson_p(sub["first_bar_move"], sub["leg_amp"])
            log("check3_permutation", scope, leg_dir, "trivial_baseline_r_first_bar_vs_TOTAL", r_triv_tot, n_triv_tot, p_triv_tot)
            triv_rem = sub.dropna(subset=["remaining_amp_naive"])
            r_triv_rem, n_triv_rem, p_triv_rem = pearson_p(triv_rem["first_bar_move"], triv_rem["remaining_amp_naive"])
            log("check3_permutation", scope, leg_dir, "trivial_baseline_r_first_bar_vs_REMAINING", r_triv_rem, n_triv_rem, p_triv_rem,
                "compare to the 5-bar early signature's disjoint r -- is the fancy window better than 1 bar?")

            check123[scope][leg_dir] = {
                "r_total": r_naive, "n_total": n_naive,
                "r_disjoint": r_disj, "n_disjoint": n_disj,
                "r_confirmed_disjoint": r_conf, "n_confirmed": n_conf,
                "perm_p": perm_p, "trivial_total": r_triv_tot, "trivial_remaining": r_triv_rem,
            }

    # ============= corr_depth supplementary (already structurally disjoint) =
    corrdepth_rows = []
    for ticker in ORIGINAL_3 + FRESH_5:
        bars = load_5m_bars(engine, ticker)
        feat_df = compute_features(bars)
        h = feat_df["high"].to_numpy(float); l = feat_df["low"].to_numpy(float)
        c = feat_df["close"].to_numpy(float); atr = feat_df["atr14"].to_numpy(float)
        piv = swing_pivots(h, l, width=PIVOT_WIDTH)
        sig = significant_pivots(piv, atr, AMP_MULT)
        corrdepth_rows += build_corrdepth_check(ticker, sig, c)
    cdf = pd.DataFrame(corrdepth_rows)

    corrdepth_results = {}
    for scope, tickers in [("original_3", ORIGINAL_3), ("fresh_5", FRESH_5)]:
        sub_scope = cdf[cdf["ticker"].isin(tickers)]
        corrdepth_results[scope] = {}
        for leg_dir in ("up", "down"):
            sub = sub_scope[sub_scope["leg_dir"] == leg_dir]
            r_naive, n_naive, p_naive = pearson_p(sub["early_slope_naive"], sub["corr_depth"])
            r_conf, n_conf, p_conf = pearson_p(sub["early_slope_confirmed"], sub["corr_depth"])
            log("check2_lookahead", scope, leg_dir, "r_early_slope_NAIVE_vs_corr_depth", r_naive, n_naive, p_naive,
                "this metric was ALREADY structurally disjoint in the original (b->c, separate from a->b)")
            log("check2_lookahead", scope, leg_dir, "r_early_slope_CONFIRMED_vs_corr_depth", r_conf, n_conf, p_conf,
                "after the look-ahead fix -- does it survive?")
            corrdepth_results[scope][leg_dir] = {"r_naive": r_naive, "n_naive": n_naive,
                                                   "r_confirmed": r_conf, "n_confirmed": n_conf}

    # trivial baseline for corr_depth too
    trivial_corrdepth = {}
    for scope, tickers in [("original_3", ORIGINAL_3), ("fresh_5", FRESH_5)]:
        df = legs_to_df([l for t in tickers for l in all_legs[t]])
        trivial_corrdepth[scope] = {}
        for leg_dir in ("up", "down"):
            sub = df[(df["leg_dir"] == leg_dir) & df["corr_depth"].notna()]
            r_triv, n_triv, p_triv = pearson_p(sub["first_bar_move"], sub["corr_depth"])
            log("check3_permutation", scope, leg_dir, "trivial_baseline_r_first_bar_vs_corr_depth", r_triv, n_triv, p_triv)
            trivial_corrdepth[scope][leg_dir] = {"r": r_triv, "n": n_triv}

    # ============= CHECK 4: recompute prior report numbers from raw DB rows =
    check4 = check4_recompute_from_raw(engine)
    for leg_dir in ("up", "down"):
        for portion in ("in_sample", "held_out"):
            d = check4[leg_dir][portion]
            log("check4_recompute", "original_3", leg_dir, f"r_early_gain_leg_amp_{portion}", d["r_early_leg_amp"], d["n"], d["p"],
                "recomputed independently from raw research_dome_leg_signature rows")
            log("check4_recompute", "original_3", leg_dir, f"r_early_slope_corr_depth_{portion}", d["r_early_slope_corr_depth"], d["n_corr"], d["p_corr"])
    for leg_dir in ("up", "down"):
        for portion in ("in_sample", "held_out"):
            d = check4["10stock"][leg_dir][portion]
            log("check4_recompute", "10stock", leg_dir, f"r_early_gain_leg_amp_{portion}", d["r_early_leg_amp"], d["n"], d["p"])

    # ---- write to DB --------------------------------------------------------
    records = [(run_id, *r) for r in ROWS]
    raw_conn = engine.raw_connection()
    try:
        cur = raw_conn.cursor()
        sql = ("INSERT INTO research_dome_leg_verification "
               "(run_id, check_name, scope, leg_dir, metric_name, metric_value, n, p_value, notes) VALUES %s")
        execute_values(cur, sql, records, page_size=1000)
        raw_conn.commit()
    finally:
        raw_conn.close()
    print(f"Wrote {len(records)} verification metric rows to research_dome_leg_verification (run_id={run_id})")

    return run_id, git_info, check123, corrdepth_results, trivial_corrdepth, check4, all_legs


if __name__ == "__main__":
    main()
