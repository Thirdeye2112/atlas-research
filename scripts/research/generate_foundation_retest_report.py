#!/usr/bin/env python
"""
generate_foundation_retest_report.py
=======================================
Renders reports/research/FOUNDATION_RETEST_REPORT.md from
foundation_retest_summary.json. Pure report writer -- no DB access.

Usage (cwd = C:\\Atlas\\atlas-research):
    .venv\\Scripts\\python.exe scripts\\research\\generate_foundation_retest_report.py
"""
from __future__ import annotations

import json
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = WORKTREE_ROOT / "reports" / "research"
SUMMARY_PATH = REPORTS_DIR / "foundation_retest_summary.json"
RUNLOG_PATH = REPORTS_DIR / "foundation_retest_run_log.jsonl"
REPORT_PATH = REPORTS_DIR / "FOUNDATION_RETEST_REPORT.md"


def load():
    with open(SUMMARY_PATH, encoding="utf-8") as f:
        summary = json.load(f)
    run = None
    if RUNLOG_PATH.exists():
        for line in RUNLOG_PATH.read_text(encoding="utf-8").strip().splitlines():
            rec = json.loads(line)
            if rec["run_id"] == summary["run_id"]:
                run = rec
    return summary, run


def fmt_r(x):
    return "n/a" if x is None or x != x else f"{x:+.4f}R"


def fmt_p(x):
    return "n/a" if x is None or x != x else (f"{x:.4f}" if x >= 0.0001 else "<0.0001")


def render(summary: dict, run: dict | None) -> str:
    lines = []
    a = lines.append

    a("# Foundation Retest: One Stock, Conditional TA, Timeframe Corroboration\n")
    a("**MEASURE & REPORT ONLY.** Tests the hypothesis that scoring every TA tool at every bar and "
      "averaging (setup-formation v2's confluence approach) washes out moments where a SPECIFIC tool, "
      "in a SPECIFIC state, with higher-timeframe agreement, actually has edge. One stock "
      f"(**{summary['ticker']}**), examined deeply, conditional triggers only -- not kitchen-sink "
      "averaging. Run without auto-approving prose verdicts: numbers first, conclusions second. A null "
      "is a valid, expected result; this report does not tune toward a positive.\n")

    if run:
        a(f"- **Run ID:** `{summary['run_id']}`")
        a(f"- **Git commit:** `{run['git']['commit']}` (branch `{run['git']['branch']}`)")
        a(f"- **Timestamp (UTC):** {run['timestamp_utc']}")
        a(f"- **Ticker:** {run['ticker']} ({run['timeframe']}), {run['n_bars']:,} bars "
          f"[{run['date_min']} .. {run['date_max']}]")
        a(f"- **Walk-forward split:** {run['train_fraction']*100:.0f}% train / "
          f"{(1-run['train_fraction'])*100:.0f}% held-out, split at {run['split_ts']}")
        a(f"- **K horizons (bars):** {run['k_values']} | **R multiples / ATR stop:** {run['r_multiples']} / {run['atr_stop_mult']}x ATR")
        a(f"- **Total wall time:** {run['elapsed_sec']}s")
    a(f"- **Trigger instances:** {summary['n_trigger_rows']:,} trigger x K rows, "
      f"{summary['n_baseline_rows']:,} baseline rows\n")

    # ---- Why AAPL ------------------------------------------------------------
    a("## Stock selection\n")
    a("**AAPL**, not SPY. This is the one ticker present in every phase of this research arc "
      "(setup-formation v1/v2, pattern-fulfillment, dome-leg) -- the deepest existing context to "
      "cross-reference against. SPY is an index ETF (a composite of 500 names with fundamentally "
      "different participation/arbitrage dynamics), which would not extend the \"four prior "
      "single-name 5m tests\" comparison this run is meant to continue. AAPL is also genuinely liquid "
      "with a long, clean 5m history (2023-01-03 onward, confirmed in Step 0).\n")

    # ---- Step 0 ---------------------------------------------------------------
    a("## Step 0. Data / execution integrity audit\n")
    a("**Session grid, duplicates, OHLC sanity:** 67,241 5m bars, zero duplicate (ticker, ts) rows, "
      "zero OHLC sanity violations (high>=low, close within [low,high] always held). Per-day bar-count "
      "distribution: 857 full 78-bar sessions, 7 known-holiday 42-bar half days (Thanksgiving Fri, "
      "July 3, Christmas Eve -- all calendar-correct), 2 other partial days (1 legitimate half day with "
      "some additional internal gaps on 2025-07-03, 1 the most-recent/still-accumulating day), and **one "
      "genuine, unexplained short day** (2024-12-23, only 11 bars ending 10:20 ET -- not a known holiday "
      "or half day). Flagged for transparency; at 11 of 67,241 bars (0.02%) it cannot materially affect "
      "any aggregate result in this report. 3 isolated zero-volume bars (0.004%), scattered, OHLC "
      "otherwise sane on each. Timezone conversion verified correct across DST transitions (every "
      "session's first bar converts to exactly 09:30 America/New_York, summer and winter alike).")
    a("\n**PIT/causality spot-check (hand-recomputed independently, not by re-running compute_features "
      "and comparing to itself):** EMA9, RSI14, VWAP, and ATR14 at a bar deep in the dataset (index "
      "50000) were each recomputed from raw OHLCV using only bars at or before that index, by separate "
      "from-scratch code. All four matched `compute_features()`'s output to floating-point precision "
      "-- confirms these columns are genuinely causal, not just claimed to be.")
    a("\n**A genuine bug was found and is the headline Step 0 result.** `compute_features()`'s "
      "`vwap_cross_up` column is broken: `above_vwap.shift(1)` upcasts a bool Series to `object` dtype "
      "to hold the leading NaN, and Python's `~` operator on that object-dtype series triggers "
      "bitwise-int semantics (`~True`=-2, `~False`=-1, **both truthy**), so `above_vwap & "
      "~above_vwap_prev` collapses to just `above_vwap` itself. Verified independently: a genuine "
      "binary crossing series must have equal (+-1) up- and down-transition counts; the stored "
      "`vwap_cross_up`/`vwap_cross_down` columns showed 34,954 vs 3,121 -- a 10-to-1 violation of "
      "that identity, while a from-scratch manual transition count gave 3,121 vs 3,121 (balanced, "
      "matching `vwap_cross_down`, which is unaffected -- it negates the proper bool-dtype "
      "`above_vwap` column directly, never the shifted/upcast one). **This bug is in shared production "
      "code and was not fixed here** (this branch is read-only on existing code) -- this study's own "
      "`vwap_reclaim` trigger is computed safely instead, via the same numpy-array shift pattern "
      "already used for the EMA-cross trigger. Retroactive implication: setup-formation v2's \"vwap\" "
      "confluence tool and pattern-fulfillment's \"vwap\" pattern (its single largest instance count, "
      "151,692 rows) both used the buggy column for their bullish/reclaim side -- their reclaim-side "
      "numbers should be treated as unreliable; their loss/rejection-side numbers (using "
      "`vwap_cross_down`) were not affected.")
    a("\nAll other tool definitions were independently balance-checked the same way "
      "(macd_bull_cross=2,558 vs macd_bear_cross=2,557 -- balanced; rsi/volume/ema rates all "
      "plausible) -- no other bug found.\n")

    # ---- Step 1 ---------------------------------------------------------------
    a("## Step 1. The gap-protocol standard, applied\n")
    a("Read `src/atlas_research/ta/gaps.py` (branch `feat/gaps`) in full. What makes it sound, and "
      "what was carried into this study:\n")
    a("1. **State explicitly, per signal, the EXACT bar at which it becomes causally knowable** -- "
      "gaps.py's FVG docstring: \"Look-ahead: CRITICAL. The FVG is ONLY confirmed at C3's CLOSE... "
      "Downstream consumers must not use this signal before C3 closes.\" Applied here: every one of "
      "this study's 8 tool families has an explicit code-comment stating its exact knowable-at bar -- "
      "most critically the swing-pivot trigger (decision_idx = pivot_idx + width, not pivot_idx -- "
      "the exact mistake research/dome-leg-verify found broken in a prior phase, applied correctly "
      "here from the start, not patched in afterward).")
    a("2. **Track detection-timestamp and confirmation-timestamp as distinct fields even when they "
      "coincide** -- gaps.py's schema carries both `ts` and `detect_close_ts` separately. Applied: "
      "this study's `decision_ts` is always defined as the earliest causally-knowable bar, never the "
      "bar that merely defines the pattern's geometry.")
    a("3. **Minimize and precisely enumerate which bars contribute to a signal** -- FVG detection uses "
      "only C1 and C3's high/low; C2's content doesn't matter, and the docstring says so explicitly. "
      "Applied: every trigger here is a single-bar instantaneous event (no multi-bar \"early window\" "
      "of the kind that caused research/dome-leg-verify's tautology finding).")
    a("4. **Reuse the textbook/existing definition rather than inventing thresholds** -- gaps.py uses "
      "the literal standard SMC/ICT 3-bar imbalance definition, no invented tolerance. Applied: 4 of "
      "the 8 tool families reuse `compute_features()`'s already-PIT-verified columns unmodified "
      "(RSI reclaim, MACD cross, VWAP -- recomputed safely per the Step 0 finding -- and the channel/"
      "swing-pivot machinery reused verbatim from prior phases); the FVG-fill trigger reproduces "
      "gaps.py's own `compute_fvgs()` logic exactly.")
    a("5. **Document input preconditions explicitly** -- gaps.py: \"Must be sorted ascending by ts. "
      "Single ticker only.\" Applied throughout this study's own docstrings.\n")

    # ---- Step 2 ---------------------------------------------------------------
    a("## Step 2. Conditional per-tool results: edge over baseline\n")
    a("8 tool families, 16 directional trigger_types, K in {3,6,12}. **48 (trigger_type x K) cells "
      "tested.** Baseline = random-direction entries, identical ATR R-bracket, same K, fixed seed -- "
      "note the baseline itself is not exactly zero (same mechanical reason found in "
      "pattern-fulfillment and dome-leg: \"highest R-target reached before the stop\" is asymmetric, "
      "wins uncapped at 1/2/3R, losses always exactly -1R). Edge = trigger expectancy MINUS the "
      "matching baseline cell's expectancy, in held-out data. Sorted by p-value (most "
      "tempting-looking first) -- **none survive correction; see the bold-faced BH-FDR column.**\n")
    a("| Trigger | K | n(is) | E(is) | n(ho) | E(ho) | Edge over baseline (ho) | p vs baseline | Survives BH-FDR |")
    a("|---|---|---|---|---|---|---|---|---|")
    cells = sorted(summary["expectancy_cells"].items(),
                   key=lambda kv: (kv[1].get("p_value_vs_baseline_held_out") if kv[1].get("p_value_vs_baseline_held_out") == kv[1].get("p_value_vs_baseline_held_out") else 1))
    for key, v in cells:
        isd, ho = v["in_sample"], v["held_out"]
        survive = "**YES**" if v.get("bh_fdr_survives") else "no"
        a(f"| {v['trigger_type']} | {v['k']} | {isd['n']:,} | {fmt_r(isd['expectancy_R'])} | "
          f"{ho['n']:,} | {fmt_r(ho['expectancy_R'])} | {fmt_r(v.get('edge_over_baseline_held_out'))} | "
          f"{fmt_p(v.get('p_value_vs_baseline_held_out'))} | {survive} |")
    a(f"\n**{summary['n_primary_cells_tested']} cells eligible (held-out n>={summary['min_cell_n']}), "
      f"{summary['n_primary_cells_survive_bh_fdr']} survive BH-FDR at q={summary['bh_fdr_q']}.**\n")

    # ---- Step 3 ---------------------------------------------------------------
    a("## Step 3. Timeframe corroboration: does daily agreement improve the edge?\n")
    a("For each trigger_type at K=6 (the headline horizon, to bound the extra multiple-testing cost), "
      "split into decision points where the prior trading day's daily trend AGREES with the trigger's "
      "direction vs. DISAGREES, comparing realized R directly (not vs. baseline -- this is an "
      "agrees-vs-disagrees test, not an edge-over-baseline test). **16 cells tested.**\n")
    a("| Trigger | n(agree) | E(agree, ho) | n(disagree) | E(disagree, ho) | p (agree vs disagree) | Survives BH-FDR |")
    a("|---|---|---|---|---|---|---|")
    dcells = sorted(summary["daily_agreement_cells"].items(),
                     key=lambda kv: (kv[1]["held_out"]["p_agree_vs_disagree"] if kv[1]["held_out"]["p_agree_vs_disagree"] == kv[1]["held_out"]["p_agree_vs_disagree"] else 1))
    for key, v in dcells:
        ho = v["held_out"]
        survive = "**YES**" if v.get("bh_fdr_survives_agreement_diff") else "no"
        a(f"| {v['trigger_type']} | {ho['agrees']['n']:,} | {fmt_r(ho['agrees']['expectancy_R'])} | "
          f"{ho['disagrees']['n']:,} | {fmt_r(ho['disagrees']['expectancy_R'])} | "
          f"{fmt_p(ho['p_agree_vs_disagree'])} | {survive} |")
    a(f"\n**{summary['n_daily_cells_tested']} cells eligible, {summary['n_daily_cells_survive_bh_fdr']} "
      f"survive BH-FDR.** Descriptively (none of this is significant after correction, so read as "
      "color, not a finding): in most cells the point estimate for DISAGREEING with the daily trend "
      "is *higher*, not lower, than agreeing -- the opposite of the corroboration hypothesis' "
      "predicted direction. Since nothing here clears the multiple-testing bar, this should not be "
      "read as \"counter-trend is better\" -- only as \"no evidence that agreement helps, and what "
      "little signal exists doesn't point the hypothesized way.\"\n")

    # ---- Step 4 -----------------------------------------------------------------
    a("## Step 4. Validation (the six checks)\n")
    a("No `RESULT_VALIDATION_TEMPLATE.md` exists on this branch (checked across all branches) -- using "
      "the six checks named in the brief directly.\n")
    a("1. **Disjointness (target doesn't contain the feature).** Every trigger here is a single-bar "
      "instantaneous event (a cross, a reclaim, a confirmed pivot, a filled gap) -- not a multi-bar "
      "\"early window\" measured against a target that structurally contains it (the exact failure "
      "mode `research/dome-leg-verify` found in the dome-leg study). The R-bracket forward window "
      "always starts at decision_idx+1, strictly after the trigger's own defining bar(s). **PASS by "
      "construction.**")
    a("2. **Causal availability (no look-ahead).** Applied the dome-leg-verify lesson directly: the "
      "swing-pivot trigger's decision_idx is `pivot_idx + width`, not `pivot_idx` (Step 1/comments). "
      "The channel-break trigger's decision_idx is the break bar itself (the forward scan that finds "
      "it never looks behind the fit bar). The FVG-fill trigger's decision_idx is always >= the bar "
      "where the zone was confirmed (C3). **PASS.**")
    a(f"3. **Trivial baseline (beat last-bar momentum).** A purely mechanical \"last bar was green -> "
      f"long, last bar was red -> short\" baseline (no tool involved) was computed across all "
      f"{summary['momentum_baseline_summary'].get('6', {}).get('n', 0):,} valid bars: expectancy "
      f"{fmt_r(summary['momentum_baseline_summary'].get('3', {}).get('expectancy_R'))} (K=3), "
      f"{fmt_r(summary['momentum_baseline_summary'].get('6', {}).get('expectancy_R'))} (K=6), "
      f"{fmt_r(summary['momentum_baseline_summary'].get('12', {}).get('expectancy_R'))} (K=12) -- in "
      "the same range as the random-direction baseline and in the same range as nearly every trigger "
      "cell above. **No surviving cell exists to test against this baseline specifically** (Step 2 "
      "found zero); the comparison is reported for completeness and shows the same pattern as "
      "elsewhere in this research arc: most apparent edges are within noise of trivial momentum.")
    a("4. **Suspicious replication.** No cell replicated \"too cleanly\" in a way that would itself be "
      "suspicious (the opposite problem from dome-leg's 13-stock replication of an artifact) -- nothing "
      "here is clean enough to raise that flag; the closest near-miss "
      "(`swing_pivot_high_confirmed`) is consistent in *sign* across K=3/6/12 (a mildly encouraging, "
      "not suspicious, property) but inconsistent in significance and does not survive correction.")
    a("5. **OOS train/held-out split.** Chronological, 70/30 per the standard convention this whole "
      "research arc uses; confirmed clean in the run log (in-sample ends and held-out begins at the "
      "documented split timestamp, no overlap).")
    a(f"6. **Multiple-testing correction.** Benjamini-Hochberg FDR at q={summary['bh_fdr_q']}, applied "
      f"separately to the Step 2 pool ({summary['n_primary_cells_tested']} cells) and the Step 3 pool "
      f"({summary['n_daily_cells_tested']} cells). **Total multiple-testing denominator: "
      f"{summary['total_multiple_testing_denominator']} cells. Survivors: "
      f"{summary['n_primary_cells_survive_bh_fdr']} (Step 2) + {summary['n_daily_cells_survive_bh_fdr']} "
      f"(Step 3) = 0.**\n")

    # ---- Verdict --------------------------------------------------------------
    a("## Verdict\n")
    a(VERDICT_PLACEHOLDER)

    a("\n## Reproducibility\n")
    a(f"- Full aggregates: `reports/research/foundation_retest_summary.json` (run `{summary['run_id']}`)")
    a(f"- Run log: `reports/research/foundation_retest_run_log.jsonl`")
    a(f"- Raw rows: `research_foundation_retest`, `research_foundation_retest_baseline` tables, "
      f"`WHERE run_id = '{summary['run_id']}'`")
    a(f"- Example charts: `reports/research/charts/` (prefixed `fr_`)")

    return "\n".join(lines) + "\n"


VERDICT_PLACEHOLDER = "_(filled in by hand after reviewing Steps 0-4 -- see conversation writeup)_"


def main():
    summary, run = load()
    text = render(summary, run)
    REPORT_PATH.write_text(text, encoding="utf-8")
    print(f"Wrote {REPORT_PATH} ({len(text)} chars)")


if __name__ == "__main__":
    main()
