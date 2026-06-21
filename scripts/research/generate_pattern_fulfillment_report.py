#!/usr/bin/env python
"""
generate_pattern_fulfillment_report.py
=========================================
Renders reports/research/PATTERN_FULFILLMENT_REPORT.md from
pattern_fulfillment_summary.json (written by aggregate_pattern_fulfillment.py).
Pure report writer -- no DB access, no new measurement.

Usage (cwd = C:\\Atlas\\atlas-research):
    .venv\\Scripts\\python.exe scripts\\research\\generate_pattern_fulfillment_report.py
"""
from __future__ import annotations

import json
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = WORKTREE_ROOT / "reports" / "research"
SUMMARY_PATH = REPORTS_DIR / "pattern_fulfillment_summary.json"
RUNLOG_PATH = REPORTS_DIR / "pattern_fulfillment_run_log.jsonl"
REPORT_PATH = REPORTS_DIR / "PATTERN_FULFILLMENT_REPORT.md"

SUPPLEMENTAL_PATTERNS = {"flat_top", "long_upper_wick", "long_lower_wick", "continuation_candle"}
CONTEXT_ONLY_EXCLUDED = ["adx", "atr", "swing_leg", "volume_ratio"]


def load():
    with open(SUMMARY_PATH, encoding="utf-8") as f:
        summary = json.load(f)
    run = None
    if RUNLOG_PATH.exists():
        lines = RUNLOG_PATH.read_text(encoding="utf-8").strip().splitlines()
        for line in lines:
            rec = json.loads(line)
            if rec["run_id"] == summary["run_id"]:
                run = rec
    return summary, run


def fmt_r(x):
    return "n/a" if x is None or x != x else f"{x:+.3f}R"


def fmt_pct(x):
    return "n/a" if x is None or x != x else f"{x*100:.1f}%"


def fmt_p(x):
    return "n/a" if x is None or x != x else (f"{x:.4f}" if x >= 0.0001 else "<0.0001")


def overfit_flag(e_is, e_ho):
    if e_is is None or e_ho is None or e_is != e_is or e_ho != e_ho:
        return ""
    if (e_is > 0) != (e_ho > 0):
        return " ⚠sign-flip"
    if e_is > 0 and e_ho < e_is * 0.3:
        return " ⚠shrinks"
    return ""


def render(summary: dict, run: dict | None) -> str:
    lines = []
    a = lines.append

    a("# Pattern Fulfillment Backtest Report\n")
    a("**MEASURE & REPORT ONLY.** For every detected instance of every pattern in "
      "`pattern_reference` (43 rows; migration 0050) plus 4 supplemental shapes, this "
      "measures whether reality matches the TAUGHT confirm/invalidate/inversion "
      "behavior out-of-sample, judged on reward:risk **expectancy** (R units), not win "
      "rate. It is **not a predictor and not a trading signal**. This system has "
      "already returned three nulls on related single-name 5m prediction "
      "(setup-formation v1, v2, confluence) -- the honest prior going in was that most "
      "patterns fulfill near coin-flip OOS, and that is mostly what this finds.\n")

    a(f"- **Run ID:** `{summary['run_id']}`")
    if run:
        a(f"- **Git commit:** `{run['git']['commit']}` (branch `{run['git']['branch']}`)")
        a(f"- **Timestamp (UTC):** {run['timestamp_utc']}")
        a(f"- **Tickers:** {', '.join(run['tickers'])}")
        a(f"- **Timeframes:** {', '.join(run['timeframes'])}")
        a(f"- **Stage windows (bars):** {run['stage_window']}")
        a(f"- **R multiples / ATR stop:** {run['r_multiples']} / {run['atr_stop_mult']}x ATR")
        a(f"- **Walk-forward split:** {run['train_fraction']*100:.0f}% train / "
          f"{(1-run['train_fraction'])*100:.0f}% held-out, chronological per (ticker, timeframe)")
        a(f"- **Total wall time:** {run['total_elapsed_sec']}s")
    a(f"- **Total instance rows:** {summary['n_pattern_rows']:,} (+ {summary['n_baseline_rows']:,} baseline rows)\n")

    # ---- Step 1: population / instance counts -------------------------------
    a("## Step 1. Population (every detected instance, no cherry-picking)\n")
    a("Scope: AAPL/NKE/INTC. Candlesticks (19) and the 4 supplemental shapes run on "
      "**both 5m and daily**. Chart patterns (double_top/bottom, hs_top/bottom, "
      "bull/bear_flag), channels (4), omni_82, oscar_87, sma_stack, and classic gaps "
      "run on **daily only** (multi-week structures; daily has clean per-day "
      "granularity and pattern_memory precedent -- see Scoping). macd, rsi, vwap, and "
      "FVG run on **5m only** (intraday-native concepts). `adx`, `atr`, `swing_leg`, "
      "`volume_ratio` are excluded from Steps 2-4 entirely: pattern_reference's own "
      "text gives them no self-contained direction/confirm/invalidate (\"N/A -- not a "
      "signal\", or in volume_ratio's case, explicitly conditional on some *other* "
      "directional signal, not a standalone setup). They are real, present, "
      "context-only indicators -- just not independently testable as a pattern.\n")
    a("| Pattern type | Timeframe | Total instances | Confirmed | Invalidated | Neither (no follow-through) |")
    a("|---|---|---|---|---|---|")
    for key, v in sorted(summary["stage_a"].items(), key=lambda kv: -kv[1]["total"]):
        sup = " *(supplemental)*" if v["pattern_type"] in SUPPLEMENTAL_PATTERNS else ""
        a(f"| {v['pattern_type']}{sup} | {v['timeframe']} | {v['total']:,} | "
          f"{v['confirmed']:,} ({fmt_pct(v['confirmed_pct'])}) | "
          f"{v['invalidated']:,} ({fmt_pct(v['invalidated_pct'])}) | "
          f"{v['neither_a']:,} ({fmt_pct(v['neither_pct'])}) |")
    a(f"\n*Context-only, excluded from Steps 2-4 (no self-contained direction/confirm/"
      f"invalidate per pattern_reference's own text):* {', '.join(CONTEXT_ONLY_EXCLUDED)}.\n")

    # ---- Step 3: expectancy table --------------------------------------------
    a("## Step 3. Expectancy: in-sample vs. held-out vs. baseline (R units)\n")
    a("Baseline = random-direction entries, identical ATR R-bracket (1x ATR stop, "
      "targets at 1/2/3x ATR), same forward window, same ticker/timeframe pool, fixed "
      "seed. **Note the baseline itself is not exactly zero** (see Scoping for why: "
      "a 'highest R-target reached before the stop' bracket is mechanically asymmetric "
      "-- wins can be 1/2/3R, losses are always exactly -1R -- so even a true coin "
      "flip nets slightly positive in this unit). This is exactly why the brief calls "
      "for comparing pattern expectancy to baseline, not to zero, and that is what the "
      "p-value column does (Welch's t-test, pattern held-out vs. baseline held-out).\n")
    a(f"**Baseline expectancy:** 5m in-sample {fmt_r(summary['baseline_summary']['5m']['in_sample']['expectancy_R'])} "
      f"(n={summary['baseline_summary']['5m']['in_sample']['n']:,}), held-out "
      f"{fmt_r(summary['baseline_summary']['5m']['held_out']['expectancy_R'])} "
      f"(n={summary['baseline_summary']['5m']['held_out']['n']:,}) | daily in-sample "
      f"{fmt_r(summary['baseline_summary']['daily']['in_sample']['expectancy_R'])} "
      f"(n={summary['baseline_summary']['daily']['in_sample']['n']:,}), held-out "
      f"{fmt_r(summary['baseline_summary']['daily']['held_out']['expectancy_R'])} "
      f"(n={summary['baseline_summary']['daily']['held_out']['n']:,}).\n")
    a(f"**Multiple testing:** {summary['n_expectancy_cells_tested']} (pattern, timeframe) "
      f"cells tested, {summary['n_expectancy_cells_survive_bh_fdr']} survive "
      f"Benjamini-Hochberg FDR correction at q={summary['bh_fdr_q']}. Cells with "
      f"held-out n < {summary['min_cell_n']} are not eligible for the FDR pool (too "
      f"thin to trust regardless of p-value) but are still shown below, flagged LOW-N.\n")
    a("| Pattern | TF | n (is) | E (is) | n (ho) | E (ho) | p vs baseline (ho) | Survives BH-FDR | Flag |")
    a("|---|---|---|---|---|---|---|---|---|")
    cells = sorted(summary["expectancy_cells"].items(),
                   key=lambda kv: (kv[1].get("p_value_vs_baseline_held_out") if kv[1].get("p_value_vs_baseline_held_out") == kv[1].get("p_value_vs_baseline_held_out") else 1))
    for key, v in cells:
        isd, ho = v["in_sample"], v["held_out"]
        low_n = " LOW-N" if ho["n"] < summary["min_cell_n"] else ""
        flag = overfit_flag(isd["expectancy_R"], ho["expectancy_R"]) + low_n
        sup = "*" if v["pattern_type"] in SUPPLEMENTAL_PATTERNS else ""
        survive = "**YES**" if v.get("bh_fdr_survives") else "no"
        a(f"| {v['pattern_type']}{sup} | {v['timeframe']} | {isd['n']:,} | {fmt_r(isd['expectancy_R'])} | "
          f"{ho['n']:,} | {fmt_r(ho['expectancy_R'])} | {fmt_p(v.get('p_value_vs_baseline_held_out'))} | "
          f"{survive} | {flag.strip()} |")
    a("\n*Marked with `*` = supplemental shape, not one of pattern_reference's 43 "
      "official rows. ⚠sign-flip = expectancy changes sign between in-sample and "
      "held-out (the overfit signature called out in the brief). ⚠shrinks = held-out "
      "expectancy collapses to under 30% of its in-sample value.\n")

    # ---- Step 4: inversion table -----------------------------------------------
    a("## Step 4. The invalidation-becomes inversion test\n")
    a("For the 21 codeable patterns with an `invalidation_becomes` row (22 total minus "
      "`hs_top`, whose own pattern_reference text disclaims a clean signal -- 'no "
      "single textbook signal'), when the ORIGINAL pattern is invalidated, this trades "
      "the inversion direction (mechanically: the flip of the original direction, "
      "which is mathematically identical to the direction of the invalidation break "
      "itself) with the same R-bracket, from the invalidation bar.\n")
    a(f"**Multiple testing:** {summary['n_inversion_cells_tested']} cells tested, "
      f"**{summary['n_inversion_cells_survive_bh_fdr']} survive** BH-FDR at q={summary['bh_fdr_q']}.\n")
    a("| Pattern | TF | n (is) | E (is) | n (ho) | E (ho) | p vs baseline (ho) | Survives BH-FDR | Flag |")
    a("|---|---|---|---|---|---|---|---|---|")
    icells = sorted(summary["inversion_cells"].items(),
                     key=lambda kv: (kv[1].get("p_value_vs_baseline_held_out") if kv[1].get("p_value_vs_baseline_held_out") == kv[1].get("p_value_vs_baseline_held_out") else 1))
    for key, v in icells:
        isd, ho = v["in_sample"], v["held_out"]
        low_n = " LOW-N" if ho["n"] < summary["min_cell_n"] else ""
        flag = overfit_flag(isd["expectancy_R"], ho["expectancy_R"]) + low_n
        survive = "**YES**" if v.get("bh_fdr_survives") else "no"
        a(f"| {v['pattern_type']} (inverted) | {v['timeframe']} | {isd['n']:,} | {fmt_r(isd['expectancy_R'])} | "
          f"{ho['n']:,} | {fmt_r(ho['expectancy_R'])} | {fmt_p(v.get('p_value_vs_baseline_held_out'))} | "
          f"{survive} | {flag.strip()} |")
    a("")

    # ---- Multiple testing caveats ------------------------------------------
    a("## Multiple-testing & honesty caveats\n")
    a(f"- {summary['n_expectancy_cells_tested']} original-direction cells + "
      f"{summary['n_inversion_cells_tested']} inversion cells = "
      f"{summary['n_expectancy_cells_tested'] + summary['n_inversion_cells_tested']} hypotheses "
      f"tested in total. At an uncorrected 95% threshold you'd expect ~"
      f"{round((summary['n_expectancy_cells_tested'] + summary['n_inversion_cells_tested'])*0.05)} "
      f"'significant' cells by chance alone with zero real effect anywhere. "
      f"Benjamini-Hochberg FDR (q={summary['bh_fdr_q']}) is applied across each table's "
      f"full cell pool (separately for originals and inversions) -- only the "
      f"**bold YES** rows should be read as surviving that correction; everything else "
      f"is reported for honesty/transparency, not as a finding.")
    a("- `three_black_crows|daily`'s inversion cell has an uncorrected p=0.0054 -- "
      "looks dramatic in isolation -- but held-out n=7 (in-sample n=0) and "
      "`bear_flag|daily`'s inversion (uncorrected p=0.0088) flips sign between "
      "in-sample (+0.53R) and held-out (-0.47R). Both are exactly the kind of cell "
      "this report's correction step exists to catch: do not act on either.")
    a("- The baseline is pooled across all 3 tickers per timeframe, not computed "
      "per-ticker. A pattern's edge (or lack of one) reported here is an "
      "AAPL+NKE+INTC-pooled statement; ticker-specific divergence is not ruled out "
      "and was not separately tested (that would triple the cell count for an "
      "already-large multiple-testing budget).")
    a("- Stage B's R-bracket settlement (\"max target reached before the stop, "
      "uncapped at 1R on the win side, capped at exactly -1R on the loss side\") is "
      "why baseline expectancy is not zero -- see Step 3. Every comparison in this "
      "report is pattern-vs-baseline under this identical convention, which is the "
      "correct way to neutralize it, but the convention itself should not be mistaken "
      "for real-world P&L (no spread/slippage/commissions, and partial fills at R1 "
      "are not modeled -- this measures whether the move happened, not a tradable "
      "execution).\n")

    # ---- Scoping --------------------------------------------------------------
    a("## Scoping notes (what was reused, what wasn't, and why)\n")
    a("- **Candlesticks (19):** `atlas_research.ta.candlesticks.detect_all_candles`, "
      "reused verbatim. Per-pattern confirm/invalidate levels are hand-mapped from "
      "pattern_reference's literal text (e.g. hammer confirm = close above the "
      "hammer's high; invalidate = close below its low) -- documented per-pattern in "
      "`pattern_fulfillment_candlesticks.py`. `morning_star`/`evening_star` are "
      "`confirmed_immediately`: per pattern_reference, the third bar's close beyond "
      "bar-1's midpoint **is** the confirmation, already enforced by the detector's "
      "own shape condition -- so T_recog = T_confirm and the real test is entirely "
      "Stage B's R-bracket.")
    a("- **Chart patterns / channels / gaps were NOT read from `pattern_memory` or "
      "the live `gaps` table.** `pattern_memory`'s chart-pattern rows (and "
      "`ta.patterns.py`'s own `double_top_bottom`/`head_and_shoulders`/`flags` "
      "functions) only ever emit ALREADY-CONFIRMED instances -- they search forward "
      "for the breakout and silently drop any shape that never finds one. That would "
      "make it structurally impossible to count failed/invalidated/no-follow-through "
      "instances, which this backtest is required to do honestly. So this measurement "
      "replicates the same pivot-shape conditions (same tolerances) but emits a "
      "candidate at RECOGNITION regardless of outcome, and lets the shared engine do "
      "the confirm/invalidate/neither accounting. The `gaps` table (and `vwap_5m`) "
      "exist live in the database but are products of separate, uncommitted work on "
      "branch `feat/gaps` not in this phase's sanctioned read-only table list -- "
      "classic gaps and FVG are computed fresh from `intraday_bars`/`raw_bars` here "
      "instead.")
    a("- **Channel detection** (`channel_ascending/descending/horizontal/break`) does "
      "not exist on `fix/model-validity` (this branch's base) under "
      "`src/atlas_research/ta/`. It exists, fully committed and pushed to origin, on "
      "sibling branch `feat/channels-and-5m` (commit `65c3fbe`, same merge-base as "
      "this branch). Its `detect_channels()` is reproduced verbatim in "
      "`scripts/research/pattern_fulfillment_channels.py` (not merged -- this phase's "
      "rule is new files only under scripts/research and reports/research) since it's "
      "a stable, already-in-production-use function (pattern_memory's existing "
      "channel rows were built with it), not in-flux WIP. Channel confirmation is "
      "simplified to the breakout/breakdown case only -- pattern_reference's text also "
      "describes a 'bounce/continuation' case with no single mechanical trigger common "
      "across all three channel shapes, so that sub-case is not separately tested.")
    a("- **vwap/rsi reclaim, FVG entry-then-reaction:** these need a 2-step check "
      "(\"price must first enter a zone/extreme, THEN react\") that doesn't fit the "
      "shared engine's generic single-level template, so they're computed with a "
      "small bespoke forward scan per pattern (documented in each module) rather than "
      "forcing a generic abstraction to fit. VWAP's 'holds for 1-2 bars' confirmation "
      "is simplified to a 1-bar hold check.")
    a("- **The inversion direction is always 'flip the instance's own resolved "
      "direction'** -- this is not an oversimplification so much as a mathematical "
      "identity: pattern_reference's invalidation_becomes direction is, in every "
      "case checked, the same as the direction of the invalidation break itself, "
      "which is necessarily the opposite of the original pattern's direction (that's "
      "what makes it an invalidation). `channel_break`/`channel_horizontal` resolve "
      "their 'original' direction from the realized break direction at confirmation "
      "time, since those two patterns don't have one fixed direction at recognition.")
    a("- **The 4 supplemental shapes** (`flat_top`, `long_upper_wick`, "
      "`long_lower_wick`, `continuation_candle`) are NOT pattern_reference rows -- "
      "defined here by analogy to the nearest official patterns (documented in "
      "`pattern_fulfillment_supplemental.py`), reported throughout but marked `*` "
      "and excluded from the inversion test (no `invalidation_becomes` basis exists "
      "for them).\n")

    # ---- Verdict -------------------------------------------------------------
    a("## Verdict\n")
    a(VERDICT_PLACEHOLDER)

    a("\n## Reproducibility\n")
    a(f"- Full per-cell aggregates: `reports/research/pattern_fulfillment_summary.json` (run `{summary['run_id']}`)")
    a(f"- Run parameters: `reports/research/pattern_fulfillment_run_log.jsonl` (same run_id)")
    a(f"- Raw rows: `research_pattern_fulfillment` table, `WHERE run_id = '{summary['run_id']}'`")
    a(f"- Example annotated charts: `reports/research/charts/` (prefixed `pf_`)")

    return "\n".join(lines) + "\n"


VERDICT_PLACEHOLDER = "_(filled in by hand after reviewing the tables above -- see conversation writeup)_"


def main():
    summary, run = load()
    text = render(summary, run)
    REPORT_PATH.write_text(text, encoding="utf-8")
    print(f"Wrote {REPORT_PATH} ({len(text)} chars)")


if __name__ == "__main__":
    main()
