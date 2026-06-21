#!/usr/bin/env python
"""
generate_setup_formation_v2_report.py
========================================
Renders reports/research/SETUP_FORMATION_V2_REPORT.md from the aggregates
already computed by run_setup_formation_v2_measurement.py
(reports/research/setup_formation_v2_summary.json). Pure report writer -- no
DB access, no new measurement.

Usage (cwd = C:\\Atlas\\atlas-research):
    .venv\\Scripts\\python.exe scripts\\research\\generate_setup_formation_v2_report.py
"""
from __future__ import annotations

import json
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = WORKTREE_ROOT / "reports" / "research"
SUMMARY_PATH = REPORTS_DIR / "setup_formation_v2_summary.json"
REPORT_PATH = REPORTS_DIR / "SETUP_FORMATION_V2_REPORT.md"

MIN_N = 30


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


CONFLUENCE_BUCKETS = ["0", "1", "2", "3", "4", "5plus", "ALL"]


def render(run: dict, summaries: dict) -> str:
    lines = []
    a = lines.append

    a("# Setup-Formation Measurement Report v2 -- Full Tool-State Snapshot\n")
    a("**MEASURE & REPORT ONLY.** This is a foundation measurement of the full "
      "point-in-time multi-tool state (volume, MACD, EMA stack, RSI, VWAP, ATR/vol, "
      "swing structure, opening-range breakout, candle/pattern) on 5-minute bars, and "
      "whether richer confluence (more active tools, or specific tool combinations) "
      "changes the forward base rate found in v1. It is **not a predictor and not a "
      "trading signal**. Single-timeframe (5m) only; N=2 only this round; daily "
      "zoom-out is a deliberately deferred later phase. A null result is reported "
      "honestly where that's what the data shows.\n")

    a(f"- **Run ID:** `{run['run_id']}`")
    a(f"- **Git commit:** `{run['git']['commit']}` (branch `{run['git']['branch']}`)")
    a(f"- **Timestamp (UTC):** {run['timestamp_utc']}")
    a(f"- **Tickers:** {', '.join(run['tickers'])} (same 3 as v1, for comparability)")
    a(f"- **N (formation window):** {run['n_window']} (fixed)")
    a(f"- **K (forward horizons, bars):** {run['k_values']}")
    a(f"- **Tools snapshotted:** {', '.join(run['tool_names'])}")
    a(f"- **Tool combinations tested:** {', '.join(run['combos_tested'])}")
    a(f"- **Total wall time:** {run['total_elapsed_sec']}s\n")

    # ---- Step 0 ------------------------------------------------------------
    a("## Step 0. Audit of v1's feature set (read before building v2)\n")
    a("v1 (commit `076bc86`, branch `research/setup-formation`) used a thin feature "
      "set: candle geometry (`candle_rng`, `body_pct`, `is_green/red`, "
      "`consec_green/red`), `atr14`, `vol_ratio`, 19 candlestick patterns "
      "(`detect_all_candles`, `eq_tol=0.0008`), `prior_trend`, and daily-layer context "
      "(`trend`, `market_trend`, `dist_support`, `dist_resistance` from "
      "`pattern_memory`; `sma_stacked` was loaded but never actually used). Forward "
      "target: `forward_return` (pct to close at T+k, k=1..5), `forward_direction` "
      "(up/down/flat via a +-0.02% epsilon band), `hit_target` (+-1x ATR14[T] reached "
      "in the row's classified direction within (T, T+k]). v1's verdict was an honest "
      "null: SETUP_FORMING did not separate from the unconditional baseline at any N "
      "or K, and there was no N-dependence (N=2 looked the same as N=5).\n")
    a("**What v2 adds:** every other PIT-computable 5m indicator that v1 ignored -- "
      "VWAP, EMA9/20/50 stack, RSI14, MACD, ATR expansion/compression, opening-range "
      "breakout, and swing-pivot trend structure -- recorded as an explicit per-tool "
      "state + \"active\" (notable event/extreme at T) flag, rolled up into a "
      "`confluence_count` (0-9) and a small set of pre-specified tool-pair "
      "combinations. The question: does the FULL picture change v1's null?\n")

    # ---- Step 1 ------------------------------------------------------------
    a("## Step 1. Tool inventory: present vs. missing on 5m\n")
    a("**Present on 5m, PIT-verified, used this run:**\n")
    a("- `compute_features()` (`src/atlas_research/intraday/features.py`) already "
      "computes, point-in-time, on 5m bars: **VWAP** (cumulative-from-open, "
      "+dist/above/cross), **EMA9/20/50** (+slopes, price-vs-ema9, ema9-vs-ema20), "
      "**RSI14** (+overbought/oversold, +reclaim events), **MACD** (+signal/hist, "
      "+bull/bear cross), **ATR14** (+20-bar avg, +compression flag), **volume "
      "ratio** (+high/very-high flags), **opening-range breakout** signals, and basic "
      "candle geometry. v1 used only a handful of these columns; v2 reads nearly all "
      "of them. One PIT subtlety found and worked around (not a bug in features.py "
      "itself): `or_high`/`or_low` reflect the *completed* opening range even for bars "
      "still inside it, which would leak if read directly during `in_or` bars -- v2's "
      "ORB tool reports an honest `in_opening_range` state for those bars instead of "
      "reading above/below-OR state from them.")
    a("- **Candlestick patterns** (`ta.candlesticks.detect_all_candles`, "
      "`eq_tol=0.0008`) and **swing-pivot trend structure** (`ta.structure."
      "swing_pivots` + `classify_trend`, pure numpy, timeframe-agnostic) -- both "
      "reused verbatim. Swing pivots were *expected* to be \"likely missing on 5m\" "
      "per the original brief; they are in fact present and usable, with one PIT "
      "subtlety handled explicitly: a pivot at bar index i is only \"known\" once bar "
      "i+3 (fractal width) has been observed, so it is folded into the trend state "
      "only from i+3 onward, never earlier.\n")
    a("**Genuinely missing everywhere (not a scoping choice):**\n")
    a("- **Channel detection** -- no module, no DB table, anywhere in the codebase "
      "(daily or 5m).")
    a("- **Stochastic oscillator** -- not implemented (an OSCAR oscillator exists in "
      "`atlas_research.features.omni_proxy`, but it's a different, daily-only "
      "formula).")
    a("- **OMNI-82 (EMA-of-lows)** -- exists (`atlas_research.features.omni_proxy`) "
      "but is daily-only in practice; never wired to 5m bars.\n")
    a("**Excluded by explicit decision, despite now having real data:**\n")
    a("- A `gaps` table (classic gap + FVG, migration `0048_gaps.sql`) and a "
      "`vwap_5m` table (migration `0047_vwap_5m.sql`) were both applied to the live "
      "database *during this session*, by separate, concurrent work on branch "
      "`feat/gaps` -- not on `fix/model-validity`, which this branch is built from. "
      "`gaps` turned out to have substantial real 5m data for all 3 target tickers "
      "(AAPL 18,589 / NKE 40,635 / INTC 31,104 rows) -- more mature than the "
      "\"uncommitted, no data yet\" framing first given when this was flagged. "
      "`vwap_5m`, by contrast, is genuinely mid-backfill: it is missing AAPL "
      "entirely. Per explicit user decision (asked mid-session once the branch "
      "discrepancy was discovered), both are excluded from this run -- v2 uses "
      "`compute_features()`'s own in-memory VWAP instead, which is complete for all "
      "3 tickers and already verified PIT-safe. Flagged as a v3 candidate once the "
      "`feat/gaps` work is merged and stable.")
    a("- Full dome/swing-leg \"early signature\" metrics (`early_gain`/`early_slope`/"
      "`leg_amp`/`corr_depth` in `ta.patterns.swing_legs`) -- a deeper, separate "
      "research thread (branch `research/dome-symmetry`). Used the lighter "
      "swing_pivots+classify_trend trend-state instead, to keep the tool count (and "
      "therefore the Step-3 combination-testing space) bounded.\n")

    # ---- Confluence distribution --------------------------------------------
    a("## 2. Confluence distribution & tool activity rates\n")
    a("`confluence_count` = number of the 9 tools with a notable event/extreme at "
      "decision point T (k=1 rows only -- one row per decision point).\n")
    a("| Ticker | Portion | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8+ |")
    a("|---|---|---|---|---|---|---|---|---|---|---|")
    for ticker in run["tickers"]:
        s = summaries.get(ticker, {})
        dist = s.get("confluence_dist", {})
        for portion in ("in_sample", "held_out"):
            d = dist.get(portion, {})
            counts = [d.get(str(i), 0) for i in range(8)]
            counts.append(sum(v for k, v in d.items() if int(k) >= 8))
            tot = sum(counts) or 1
            row = " | ".join(f"{c:,} ({c/tot*100:.0f}%)" for c in counts)
            a(f"| {ticker} | {portion} | {row} |")
    a("")
    a("Per-tool active rate (share of all decision points, in-sample):\n")
    a("| Ticker | " + " | ".join(run["tool_names"]) + " |")
    a("|---|" + "---|" * len(run["tool_names"]))
    for ticker in run["tickers"]:
        s = summaries.get(ticker, {})
        rates = s.get("tool_active_rate", {})
        row = " | ".join(fmt_rate(rates.get(t)) for t in run["tool_names"])
        a(f"| {ticker} | {row} |")
    a("")

    # ---- Setup-type composition --------------------------------------------
    a("## 3. Candle-tool composition (when active_candle fires)\n")
    a("Same trigger v1 used at N=2 (named candlestick pattern with span<=2, OR a "
      "2-candle directional-thrust geometry signal), now reported as one tool among "
      "nine rather than the sole classifier.\n")
    for ticker in run["tickers"]:
        s = summaries.get(ticker, {})
        counts = s.get("candle_setup_type_counts", {})
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:6]
        top_str = ", ".join(f"{k} ({v})" for k, v in top)
        a(f"- **{ticker}:** {top_str}")
    a("")

    # ---- Forward curves by confluence --------------------------------------
    a("## 4. Forward base-rate curves by confluence count\n")
    a("Mean forward return and ATR-hit rate over K=1..5, bucketed by `confluence_count` "
      "(5+ collapsed into one bucket for sample size), vs. the unconditional ALL "
      "baseline. This is the Step-3(i) question: does forward outcome separate from "
      "baseline as confluence rises?\n")
    for ticker in run["tickers"]:
        s = summaries.get(ticker, {})
        a(f"\n### {ticker}\n")
        a("| Confluence | K | Portion | n | Mean fwd return | 95% CI | Hit rate | Hit n | %Up |")
        a("|---|---|---|---|---|---|---|---|---|")
        curves = s.get("curves_by_confluence", {})
        for bucket in CONFLUENCE_BUCKETS:
            ck = curves.get(bucket, {})
            for k in sorted(ck.keys(), key=int):
                row = ck[k]
                for portion in ("in_sample", "held_out"):
                    r = row[portion]
                    ci = f"[{fmt_pct(r['ci_lo'])}, {fmt_pct(r['ci_hi'])}]"
                    a(f"| {bucket} | {k} | {portion} | {r['n']:,} | "
                      f"{fmt_pct(r['mean_return'])} | {ci} | {fmt_rate(r['hit_rate'])} | "
                      f"{r['hit_n']:,} | {fmt_rate(r['pct_up'])} |")
    a("")

    # ---- Tool-combination curves --------------------------------------------
    a("## 5. Forward base-rate by tool combination (K=5, headline horizon)\n")
    a(f"Pre-specified pairwise combinations only ({len(run['combos_tested'])} tested, "
      "NOT an exhaustive 2^9 search across all possible tool subsets -- that would be "
      "an uncontrolled multiple-testing fishing expedition). \"Both active\" means "
      "`active_X & active_Y` regardless of what else fires. Cells with n < "
      f"{MIN_N} in either portion are flagged LOW-N.\n")
    for ticker in run["tickers"]:
        s = summaries.get(ticker, {})
        a(f"\n### {ticker}\n")
        a("| Combo | Portion | n | Mean fwd5 return | 95% CI | Hit rate | Hit n | Flag |")
        a("|---|---|---|---|---|---|---|---|")
        combos = s.get("combo_curves_k5", {})
        for combo_name, row in combos.items():
            for portion in ("in_sample", "held_out"):
                r = row[portion]
                ci = f"[{fmt_pct(r['ci_lo'])}, {fmt_pct(r['ci_hi'])}]"
                flag = "LOW-N" if r["n"] < MIN_N else ""
                a(f"| {combo_name} | {portion} | {r['n']:,} | {fmt_pct(r['mean_return'])} | "
                  f"{ci} | {fmt_rate(r['hit_rate'])} | {r['hit_n']:,} | {flag} |")
    a("")

    # ---- Stability -----------------------------------------------------------
    a("## 6. In-sample vs. held-out stability (the honesty check)\n")
    a("Per (ticker, confluence bucket, K): does the held-out mean-return 95% CI "
      "overlap the in-sample CI?\n")
    a("| Ticker | Confluence | K | In-sample n | Held-out n | Stability |")
    a("|---|---|---|---|---|---|")
    for ticker in run["tickers"]:
        s = summaries.get(ticker, {})
        curves = s.get("curves_by_confluence", {})
        for bucket in CONFLUENCE_BUCKETS:
            ck = curves.get(bucket, {})
            for k in sorted(ck.keys(), key=int):
                row = ck[k]
                isr, hor = row["in_sample"], row["held_out"]
                flag = stability_flag(isr["n"], isr["ci_lo"], isr["ci_hi"],
                                       hor["n"], hor["ci_lo"], hor["ci_hi"], MIN_N)
                a(f"| {ticker} | {bucket} | {k} | {isr['n']:,} | {hor['n']:,} | {flag} |")
    a("")

    # ---- Multiple testing -----------------------------------------------------
    a("## 7. Multiple-testing & honesty caveats\n")
    a("- This report computes **3 tickers x 7 confluence buckets x 5 K-horizons x 2 "
      "portions = 210 cells** for the confluence curves, plus **3 tickers x 11 "
      "combos x 2 portions = 66 cells** for the combo curves (K=5 only). At a 95% CI, "
      "~5% of cells will show a 'significant' departure from zero by chance alone "
      "even with no real effect anywhere. A cell whose CI excludes zero in only ONE "
      "portion, or only at one ticker, is not a discovery -- look for replication "
      "across tickers AND across the in-sample/held-out split (Section 6) before "
      "reading anything here as real.")
    a("- The combo curves shrink fast: several cells (e.g. `volume+macd`, `macd+ema`) "
      "have held-out n in the 4-30 range -- explicitly flagged LOW-N in Section 5's "
      "table. A dramatic-looking point estimate on 4-15 observations is noise, not "
      "signal, regardless of how large the number looks.")
    a("- `direction_candle` (the candle/pattern tool) is the **only** source of a "
      "directional thesis in this snapshot -- `hit_target` is computed against it "
      "specifically, not against some multi-tool consensus direction. Rows where "
      "`active_candle` is False have `hit_target = NULL` regardless of confluence "
      "from the other 8 tools. This means high-confluence rows driven mainly by "
      "non-candle tools contribute to the mean-return columns but not the hit-rate "
      "columns -- read `hit_n` next to `hit_rate` before comparing across buckets.")
    a("- Same execution-cost caveat as v1: mean 5m returns this close to zero are "
      "easily swamped by spread/slippage, which is not modeled here at all.\n")

    # ---- Scoping --------------------------------------------------------------
    a("## 8. Scoping notes\n")
    a("- **ATR \"expanding\" threshold** (`ATR_EXPAND_MULT = 1/0.75 ~= 1.333`): the "
      "codebase only defines the compressed side (`vol_compressed`, "
      "`atr14 < atr14_ma*0.75`, in `features.py`). No existing precedent for the "
      "opposite side, so this mirrors it symmetrically rather than inventing an "
      "unrelated number.")
    a("- **Confluence-bucket \"5plus\"**: buckets 5 through 8 (8 was the observed max; "
      "9/9 never occurred) are collapsed into one bucket for sample size -- see "
      "Section 2's distribution table for the raw split.")
    a("- **N=2 only, this round** -- per the brief. The candle tool's pattern-fit "
      "logic and geometry-thrust trigger are otherwise identical to v1's N=2 case; no "
      "N-sweep was attempted for the other 8 tools.")
    a("- **No daily context attached** -- single-timeframe (5m) only, by explicit "
      "design; daily zoom-out is a deliberately deferred later phase, not an "
      "oversight.\n")

    # ---- Verdict ----------------------------------------------------------------
    a("## 9. Verdict\n")
    a(VERDICT_PLACEHOLDER)

    a("\n## 10. Reproducibility\n")
    a(f"- Full per-cell aggregates: `reports/research/setup_formation_v2_summary.json` "
      f"(run `{run['run_id']}`)")
    a(f"- Run parameters/thresholds: `reports/research/setup_formation_v2_run_log.jsonl` "
      f"(same `run_id`)")
    a(f"- Raw rows: `research_setup_formation_v2` table, `WHERE run_id = '{run['run_id']}'`")
    a(f"- Example annotated charts: `reports/research/charts/` (v2 examples prefixed `v2_`)")
    a("- Thresholds used this run:")
    for k, v in run["thresholds"].items():
        a(f"  - `{k}` = {v}")

    return "\n".join(lines) + "\n"


VERDICT_PLACEHOLDER = "_(filled in by hand after reviewing Sections 2-6 -- see conversation writeup)_"


def main():
    run, summaries = load()
    text = render(run, summaries)
    REPORT_PATH.write_text(text, encoding="utf-8")
    print(f"Wrote {REPORT_PATH} ({len(text)} chars)")


if __name__ == "__main__":
    main()
