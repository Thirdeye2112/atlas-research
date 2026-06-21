#!/usr/bin/env python
"""
generate_setup_formation_report.py
=====================================
Renders reports/research/SETUP_FORMATION_REPORT.md from the aggregates
already computed by run_setup_formation_measurement.py
(reports/research/setup_formation_summary.json) and the matching run-log
entry (reports/research/setup_formation_run_log.jsonl, last line for that
run_id). Pure report writer -- no DB access, no new measurement.

Usage (cwd = C:\\Atlas\\atlas-research):
    .venv\\Scripts\\python.exe scripts\\research\\generate_setup_formation_report.py
"""
from __future__ import annotations

import json
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = WORKTREE_ROOT / "reports" / "research"
SUMMARY_PATH = REPORTS_DIR / "setup_formation_summary.json"
REPORT_PATH = REPORTS_DIR / "SETUP_FORMATION_REPORT.md"

# Stock-selection rationale (from the quantitative scan that preceded this
# measurement -- 20-day rolling Kaufman Efficiency Ratio on daily closes
# derived from 5m bars, averaged over full history, plus daily return std%,
# computed across 30 liquid candidates). Not re-derived here; recorded for
# the report's "why these 3" section. ER closer to 1.0 = cleaner/more
# persistent trend; closer to 0 = choppier/more whipsaw-prone.
SELECTION_NOTES = {
    "AAPL": {
        "role": "liquid megacap",
        "er": 0.262, "ret_std_pct": 1.60,
        "why": "Highest efficiency ratio (tied) of 30 scanned candidates, with the "
               "lowest daily return std% of all 30 -- calm, efficient, highly liquid megacap.",
    },
    "NKE": {
        "role": "cleaner mid/large-cap trender",
        "er": 0.247, "ret_std_pct": 2.22,
        "why": "Top-quartile efficiency ratio among non-megacap names, below-median "
               "volatility -- trends with comparatively low noise; different sector "
               "(consumer/apparel) from the megacap tech pick.",
    },
    "INTC": {
        "role": "choppy / volatile",
        "er": 0.223, "ret_std_pct": 3.25,
        "why": "4th-lowest efficiency ratio (weak trend persistence) combined with "
               "4th-highest volatility of 30 candidates -- large swings that don't "
               "resolve into clean sustained trends. TSLA was rejected for this slot "
               "despite higher raw volatility (4.14%) because its ER (0.252) was "
               "actually above median -- its big moves DO resolve into real trends, "
               "the opposite of the 'choppy/non-resolving' character this slot needs.",
    },
}


def load():
    with open(SUMMARY_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["run"], data["summaries"]


def fmt_pct(x):
    return "n/a" if x is None or x != x else f"{x:.3f}%"


def fmt_rate(x):
    return "n/a" if x is None or x != x else f"{x*100:.1f}%"


def stability_flag(in_n, in_lo, in_hi, ho_n, ho_lo, ho_hi, min_n):
    if in_n < min_n or ho_n < min_n:
        return "LOW-N"
    if in_lo != in_lo or ho_lo != ho_lo:
        return "n/a"
    overlap = not (ho_hi < in_lo or ho_lo > in_hi)
    return "stable (CIs overlap)" if overlap else "SHIFTED (CIs do not overlap)"


def render(run: dict, summaries: dict) -> str:
    lines = []
    a = lines.append

    a("# Setup-Formation Measurement Report\n")
    a("**MEASURE & REPORT ONLY.** This is a foundation measurement of how often a "
      "recognizable N-candle structure is *forming* on 5-minute bars, and what its "
      "historical forward base rate looks like. It is **not a predictor and not a "
      "trading signal** -- no projection or signal-generation logic has been built "
      "on top of these numbers. A null/neutral result (no setup forming, or a flat "
      "base rate) is reported honestly where that's what the data shows.\n")

    a(f"- **Run ID:** `{run['run_id']}`")
    a(f"- **Git commit:** `{run['git']['commit']}` (branch `{run['git']['branch']}`)")
    a(f"- **Timestamp (UTC):** {run['timestamp_utc']}")
    a(f"- **Tickers:** {', '.join(run['tickers'])}")
    a(f"- **N (formation window sizes):** {run['n_values']}")
    a(f"- **K (forward horizons, bars):** {run['k_values']}")
    a(f"- **Total wall time:** {run['total_elapsed_sec']}s\n")

    # ---- Stock selection -----------------------------------------------
    a("## 1. Stock selection\n")
    a("Picked from tickers with sufficient 5m history in `intraday_bars`, using a "
      "20-day rolling Kaufman Efficiency Ratio (ER) on daily closes derived from 5m "
      "bars (averaged over full history) plus daily return std% as the volatility "
      "axis -- a 'trend cleanliness vs. choppiness' ranking, not narrative/reputation "
      "picking.\n")
    a("| Ticker | Role | ER (trend cleanliness) | Daily ret std% | Bars (5m) | Date range |")
    a("|---|---|---|---|---|---|")
    for ticker in run["tickers"]:
        meta = run["per_ticker_meta"].get(ticker, {})
        note = SELECTION_NOTES.get(ticker, {})
        a(f"| {ticker} | {note.get('role','?')} | {note.get('er','?')} | "
          f"{note.get('ret_std_pct','?')}% | {meta.get('n_bars','?'):,} | "
          f"{meta.get('date_min','?')} .. {meta.get('date_max','?')} |")
    a("")
    for ticker in run["tickers"]:
        note = SELECTION_NOTES.get(ticker, {})
        a(f"- **{ticker}** ({note.get('role','')}): {note.get('why','')}")
    a("")

    # ---- Per-N summary ---------------------------------------------------
    a("## 2. How often is a setup forming? (per N, per ticker)\n")
    a("State frequency at each decision point (k=1 row only -- one row per decision "
      "point), split by walk-forward portion (`in_sample` = first 70% chronologically "
      "per ticker, `held_out` = last 30%).\n")
    a("| Ticker | N | Portion | Total decision points | SETUP_FORMING | NEUTRAL | FLAT |")
    a("|---|---|---|---|---|---|---|")
    for ticker in run["tickers"]:
        s = summaries.get(ticker, {})
        for n_window, body in sorted(s.get("by_n", {}).items(), key=lambda x: int(x[0])):
            sc = body["state_counts"]
            for portion in ("in_sample", "held_out"):
                c = sc[portion]
                tot = c["total"] or 1
                a(f"| {ticker} | {n_window} | {portion} | {c['total']:,} | "
                  f"{c['SETUP_FORMING']:,} ({c['SETUP_FORMING']/tot*100:.1f}%) | "
                  f"{c['NEUTRAL']:,} ({c['NEUTRAL']/tot*100:.1f}%) | "
                  f"{c['FLAT']:,} ({c['FLAT']/tot*100:.1f}%) |")
    a("")

    # ---- Setup-type composition ------------------------------------------
    a("## 3. What's actually firing (setup-type composition)\n")
    a("Counts of `setup_type` among SETUP_FORMING decision points (in-sample), per "
      "ticker at N=2 and N=5 (the shortest and longest window -- composition is "
      "nearly identical across N=3,4,5 since the candlestick detector's max pattern "
      "span is 3 bars, so once N>=3 every pattern fits regardless of N).\n")
    for ticker in run["tickers"]:
        s = summaries.get(ticker, {})
        for n_window in (2, 5):
            body = s.get("by_n", {}).get(str(n_window)) or s.get("by_n", {}).get(n_window)
            if not body:
                continue
            counts = body["setup_type_counts"]
            top = sorted(counts.items(), key=lambda kv: -kv[1])[:6]
            top_str = ", ".join(f"{k} ({v})" for k, v in top)
            a(f"- **{ticker} N={n_window}:** {top_str}")
    a("\n**Caveat:** tweezer_top/tweezer_bottom (high/low match within 0.08%, the "
      "same tolerance `build_candle_memory.py` already uses for its own 5m "
      "candlestick layer) account for roughly a third to half of all SETUP_FORMING "
      "calls across tickers. This is a real property of the existing detector applied "
      "at 5m resolution, not a bug introduced here -- but it means a large share of "
      "'forming' classifications are driven by an equal-extremes geometry check rather "
      "than the more complex multi-bar reversal shapes. Worth knowing before reading "
      "too much into the aggregate forming-rate.\n")

    # ---- Forward base-rate curves -----------------------------------------
    a("## 4. Forward base-rate curves (by N and K)\n")
    a("For each ticker/N: mean forward return and ATR-hit rate over K=1..5 bars, for "
      "SETUP_FORMING decision points vs. the unconditional ALL baseline (every "
      "decision point regardless of state) -- this is the comparison that tells you "
      "whether 'forming' actually differs from doing nothing. 95% CIs shown; "
      "`hit_target` is null (excluded from the hit-rate calc) for decision points "
      "with no directional thesis.\n")

    for ticker in run["tickers"]:
        s = summaries.get(ticker, {})
        a(f"\n### {ticker}\n")
        a("| N | K | State | Portion | n | Mean fwd return | 95% CI | Hit rate (±1 ATR) | Hit n |")
        a("|---|---|---|---|---|---|---|---|---|")
        for n_window, body in sorted(s.get("by_n", {}).items(), key=lambda x: int(x[0])):
            curves = body["curves"]
            for state_label in ("SETUP_FORMING", "ALL"):
                ck = curves.get(state_label, {})
                for k in sorted(ck.keys(), key=int):
                    row = ck[str(k)] if str(k) in ck else ck[k]
                    for portion in ("in_sample", "held_out"):
                        r = row[portion]
                        ci = f"[{fmt_pct(r['ci_lo'])}, {fmt_pct(r['ci_hi'])}]"
                        a(f"| {n_window} | {k} | {state_label} | {portion} | {r['n']:,} | "
                          f"{fmt_pct(r['mean_return'])} | {ci} | {fmt_rate(r['hit_rate'])} | {r['hit_n']:,} |")
    a("")

    # ---- Daily-context breakdown -------------------------------------------
    a("## 4b. Forward base-rate by daily context (N=5, K=5, SETUP_FORMING only)\n")
    a("`daily_context` = `{daily_trend}/{daily_loc}/mkt_{daily_market_trend}` from "
      f"`pattern_memory`'s daily layer, strictly prior-day. Top cells by |mean return| "
      f"with at least {30} decision points (in-sample); cells below that are noise, "
      "not shown. Full per-cell data (all N, all K) is in `setup_formation_summary.json`.\n")
    a("| Ticker | Daily context | In-sample n | Mean fwd5 return | 95% CI | Held-out n | Held-out mean | Held-out CI |")
    a("|---|---|---|---|---|---|---|---|")
    for ticker in run["tickers"]:
        s = summaries.get(ticker, {})
        body = s.get("by_n", {}).get("5") or s.get("by_n", {}).get(5)
        if not body:
            continue
        cells = body.get("context_cells", {})
        scored = []
        for ctx, byk in cells.items():
            row = byk.get("5") or byk.get(5)
            if not row:
                continue
            isr = row["in_sample"]
            if isr["n"] < 30 or isr["mean_return"] != isr["mean_return"]:
                continue
            scored.append((ctx, row))
        scored.sort(key=lambda cr: -abs(cr[1]["in_sample"]["mean_return"]))
        for ctx, row in scored[:8]:
            isr, hor = row["in_sample"], row["held_out"]
            ci = f"[{fmt_pct(isr['ci_lo'])}, {fmt_pct(isr['ci_hi'])}]"
            ho_ci = f"[{fmt_pct(hor['ci_lo'])}, {fmt_pct(hor['ci_hi'])}]" if hor["n"] else "n/a"
            a(f"| {ticker} | {ctx} | {isr['n']:,} | {fmt_pct(isr['mean_return'])} | {ci} | "
              f"{hor['n']:,} | {fmt_pct(hor['mean_return'])} | {ho_ci} |")
    a("")

    # ---- In-sample vs held-out stability -----------------------------------
    a("## 5. In-sample vs. held-out stability (the honesty check)\n")
    a("Per (ticker, N, K) for SETUP_FORMING: does the held-out mean-return 95% CI "
      "overlap the in-sample CI? This is the test of whether the base rate is stable "
      "out-of-sample, not whether it merely exists in-sample. `LOW-N` cells "
      f"(n < {30}) are flagged as too small to draw conclusions from rather than "
      "scored.\n")
    a("| Ticker | N | K | In-sample n | Held-out n | Stability |")
    a("|---|---|---|---|---|---|")
    for ticker in run["tickers"]:
        s = summaries.get(ticker, {})
        for n_window, body in sorted(s.get("by_n", {}).items(), key=lambda x: int(x[0])):
            ck = body["curves"].get("SETUP_FORMING", {})
            for k in sorted(ck.keys(), key=int):
                row = ck[str(k)] if str(k) in ck else ck[k]
                isr, hor = row["in_sample"], row["held_out"]
                flag = stability_flag(isr["n"], isr["ci_lo"], isr["ci_hi"],
                                       hor["n"], hor["ci_lo"], hor["ci_hi"], 30)
                a(f"| {ticker} | {n_window} | {k} | {isr['n']:,} | {hor['n']:,} | {flag} |")
    a("")

    # ---- Multiple testing / honesty caveats --------------------------------
    a("## 6. Multiple-testing & honesty caveats\n")
    a("- This report computes **3 tickers x 4 N-values x 5 K-horizons x 2 states "
      "(SETUP_FORMING/ALL) x 2 portions = 240 cells** for the main curves alone, plus "
      "per-daily-context-bucket cells on top of that. At a 95% CI, ~5% of cells will "
      "show a 'significant' departure from zero by chance alone even if there is no "
      "real effect anywhere. Do not treat any single cell's CI excluding zero as a "
      "discovery -- look for a pattern that **replicates across N, across tickers, "
      "and survives the held-out split** (Section 5) before treating anything here as "
      "a real effect, and even then, this is a measurement, not a model.")
    a("- Sample sizes shrink fast once you condition on daily-context bucket *and* "
      "setup_type *and* direction simultaneously. Cells below the n=30 threshold are "
      "noise, not signal -- flagged as `LOW-N` in Section 5 and in the context-cell "
      "data (`setup_formation_summary.json`), and should not be read as a finding "
      "even if the point estimate looks dramatic.")
    a("- `hit_target` and `forward_return` are measured the same way for SETUP_FORMING "
      "and ALL, so a small gap between the two is more informative than either number "
      "in isolation -- but with mean 5m returns this close to zero, real differences "
      "this small are easily swamped by execution costs (spread, slippage) not modeled "
      "here at all.")
    a("- Daily context (`daily_trend`/`daily_loc`/`daily_market_trend`) comes from "
      "`pattern_memory`'s daily layer as of the strictly-prior trading day's close "
      "(point-in-time via `merge_asof(..., allow_exact_matches=False)`) -- it cannot "
      "leak same-day information, but it also means the very first trading day(s) of "
      "a ticker's daily history have no prior-day row to attach (rare here since daily "
      "pattern_memory predates the 5m history for all 3 tickers by ~9 years).\n")

    # ---- Scoping notes ------------------------------------------------------
    a("## 7. Scoping notes (what was reused, what wasn't, and why)\n")
    a("- **Candlestick detection:** `atlas_research.ta.candlesticks.detect_all_candles()` "
      "run directly against `intraday_bars` OHLC, with `eq_tol=0.0008` (the same "
      "tightened intraday tolerance `scripts/build_candle_memory.py` already uses for "
      "its own 5m candlestick layer, vs. the daily-tuned default of 0.003) and "
      "`skip_neutral=True`. No new pattern logic was written.")
    a("- **Why not query `pattern_memory`'s 5m layer directly:** it has no per-bar "
      "timestamp column for intraday rows (only `confirm_date`, a `date`), and carries "
      "40-70+ pattern rows per ticker per single day at 5m -- there is no way to "
      "recover which specific 5-minute bar a 5m `pattern_memory` row corresponds to. "
      "This is a genuine data-model limitation, not something fixable from this "
      "script. The workaround was to recompute the *same* detector function directly "
      "from `intraday_bars`, which is PIT-safe and faithful to 'reuse what exists' at "
      "the function level, just not at the materialized-table level.")
    a("- **Chart patterns excluded:** `ta/patterns.py` (flags, head & shoulders, double "
      "top/bottom) and `structure.swing_pivots` require several confirmed swing pivots "
      "(3 for flags, 5 for H&S) which structurally cannot exist inside a 2-5 bar "
      "window. Using them here would have meant inventing new shrunk-down pattern "
      "logic, which the task brief explicitly forbids.")
    a("- **Daily context source:** `pattern_memory` (`timeframe='daily'`) directly, "
      "matching the task's literal instruction, rather than `prediction_outcomes`. "
      "It has dense coverage (~3,000 rows per ticker, full history) with the directly "
      "relevant fields (`trend`, `market_trend`, `dist_support`, `dist_resistance`).")
    a("- **Forward outcome target:** ±1x ATR(14) move within [T+1, T+K], in the row's "
      "classified `direction`. `hit_target` is `NULL` (excluded from hit-rate stats) "
      "for NEUTRAL/FLAT rows and any SETUP_FORMING row with no directional thesis "
      "(doesn't currently occur -- every SETUP_FORMING path assigns a direction -- but "
      "left as a safety case).\n")

    # ---- Verdict -------------------------------------------------------------
    a("## 8. Verdict\n")
    a(VERDICT_PLACEHOLDER)

    a("\n## 9. Reproducibility\n")
    a(f"- Full per-cell aggregates: `reports/research/setup_formation_summary.json` "
      f"(run `{run['run_id']}`)")
    a(f"- Run parameters/thresholds: `reports/research/setup_formation_run_log.jsonl` "
      f"(same `run_id`)")
    a(f"- Raw rows: `research_setup_formation` table, `WHERE run_id = '{run['run_id']}'`")
    a(f"- Example annotated charts: `reports/research/charts/`")
    a("- Thresholds used this run:")
    for k, v in run["thresholds"].items():
        a(f"  - `{k}` = {v}")

    return "\n".join(lines) + "\n"


VERDICT_PLACEHOLDER = "_(filled in by hand after reviewing Sections 2-5 -- see conversation writeup)_"


def main():
    run, summaries = load()
    text = render(run, summaries)
    REPORT_PATH.write_text(text, encoding="utf-8")
    print(f"Wrote {REPORT_PATH} ({len(text)} chars)")


if __name__ == "__main__":
    main()
