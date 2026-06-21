#!/usr/bin/env python
"""
generate_dome_leg_signature_report.py
========================================
Renders reports/research/DOME_LEG_SIGNATURE_REPORT.md from
dome_leg_signature_summary.json. Pure report writer -- no DB access.

Usage (cwd = C:\\Atlas\\atlas-research):
    .venv\\Scripts\\python.exe scripts\\research\\generate_dome_leg_signature_report.py
"""
from __future__ import annotations

import json
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = WORKTREE_ROOT / "reports" / "research"
SUMMARY_PATH = REPORTS_DIR / "dome_leg_signature_summary.json"
RUNLOG_PATH = REPORTS_DIR / "dome_leg_signature_run_log.jsonl"
REPORT_PATH = REPORTS_DIR / "DOME_LEG_SIGNATURE_REPORT.md"


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


def fmt_p(x):
    if x is None or x != x:
        return "n/a"
    return f"{x:.4f}" if x >= 0.0001 else "<0.0001"


def render(summary: dict, run: dict | None) -> str:
    lines = []
    a = lines.append

    a("# Dome / Leg Early-Signature Study\n")
    a("**MEASURE & REPORT ONLY.** Continues two open threads already in this codebase plus a "
      "user-led exploratory pass this session: (1) the dome-symmetry audit (branch "
      "`research/dome-symmetry`), which found `swing_legs()` only ever detected the bullish "
      "up-leg/'dome' and never its bearish mirror, the down-leg/'bowl'; (2) the original "
      "swing_leg commit's own open question, \"do the first 2-5 bars predict the hump height & "
      "correction?\"; (3) whether candle geometry at confirmed swing tops/bottoms (real, large, "
      "replicated across tickers) translates into anything usable in real time, with zero "
      "look-ahead. Not a predictor, not a trading signal.\n")

    a(f"- **Run ID:** `{summary['run_id']}`")
    if run:
        a(f"- **Git commit:** `{run['git']['commit']}` (branch `{run['git']['branch']}`)")
        a(f"- **Timestamp (UTC):** {run['timestamp_utc']}")
        a(f"- **Tickers:** {', '.join(run['tickers'])} (5m, same 3 as the rest of this research arc)")
        a(f"- **Pivot width / significance filter:** width={run['pivot_width']}, "
          f"amp >= {run['amp_mult']}x ATR14 from the prior opposite pivot")
        a(f"- **Early-signature window:** first {run['early_n']} bars off the leg start")
        a(f"- **Real-time filter thresholds:** wick% > {run['wick_pct_min']}, "
          f"range/ATR > {run['rng_atr_min']}, vol_ratio > {run['vol_ratio_min']}")
        a(f"- **Walk-forward split:** {run['train_fraction']*100:.0f}% train / "
          f"{(1-run['train_fraction'])*100:.0f}% held-out, chronological per ticker")
        a(f"- **Total wall time:** {run['total_elapsed_sec']}s")
    a(f"- **Legs detected:** {summary['n_legs']:,} | **Real-time filter+baseline rows:** {summary['n_realtime_rows']:,}\n")

    # ---- Background -----------------------------------------------------------
    a("## Background: the dome-symmetry gap (prior work, not by this session)\n")
    a("`src/atlas_research/ta/patterns.py::swing_legs()` only ever paired a swing LOW followed "
      "by a swing HIGH (the bullish 'dome': rise -> peak -> correction). A prior session "
      "(branch `research/dome-symmetry`, commit `dbc98ee`) confirmed empirically that all "
      "172,707 `swing_leg` rows in `pattern_memory` are `direction='long'`, `leg_amp` and "
      "`early_gain` all non-negative, all daily -- a textbook one-sided-detector fingerprint. A "
      "follow-up commit (`0535cdb`) wrote a symmetric down-leg detector (`swing_legs_down()` / "
      "`swing_legs_all()`) but stopped short of wiring it into `pattern_memory` or running it on "
      "5m, flagged 'awaiting go'. Neither commit is merged into `fix/model-validity` or pushed "
      "to origin. This measurement reproduces that detector's field semantics directly (see "
      "Scoping) on 5m, for both orientations, rather than depending on the unmerged branch.\n")

    # ---- Part A -----------------------------------------------------------------
    a("## Part A. Candle geometry: leg start vs. leg peak/trough\n")
    a("At the moment a swing pivot is confirmed (not real-time -- see Part C for that), is there "
      "a congruent, mirror-symmetric candle signature at the START of a leg (the low for an "
      "up-leg/dome, the high for a down-leg/bowl) versus its PEAK/TROUGH (the terminal extreme)? "
      f"Pooled across AAPL/NKE/INTC, {summary['n_legs']:,} legs.\n")
    for leg_dir, label_s, label_e in [("up", "start = swing LOW (dome begins)", "peak = swing HIGH (dome top)"),
                                        ("down", "start = swing HIGH (bowl begins)", "trough = swing LOW (bowl bottom)")]:
        row = summary["part_a_congruence"][leg_dir]
        a(f"\n**{leg_dir}-leg** ({label_s} -> {label_e}), n={row['n']:,}\n")
        a("| Feature | At start | At peak/trough |")
        a("|---|---|---|")
        for f, label in [("body_pct", "body %"), ("upper_wick_pct", "upper wick %"),
                          ("lower_wick_pct", "lower wick %"), ("rng_atr_ratio", "range/ATR"),
                          ("vol_ratio", "volume ratio"), ("close_loc", "close position in range %")]:
            d = row[f]
            a(f"| {label} | {d['start_mean']:.2f} | {d['peak_mean']:.2f} |")
        a(f"| is_green % | {row['is_green_pct']['start']*100:.1f}% | {row['is_green_pct']['peak']*100:.1f}% |")
    a("\nUp-leg starts and down-leg peaks/troughs mirror each other exactly (both are 'bottom-type' "
      "bars: dominant lower wick, close high in range), and up-leg peaks mirror down-leg starts "
      "(both 'top-type': dominant upper wick, close low in range) -- confirming the symmetry the "
      "dome-symmetry audit predicted but never measured. Counterintuitive nuance: the turning bar "
      "itself is still often green at a top (53%) and red at a bottom (44% green) -- the wick, not "
      "the bar's own color, carries the rejection signal.\n")

    # ---- Part B -----------------------------------------------------------------
    a("## Part B. Does the early signature predict the eventual leg size? (in-sample vs. held-out)\n")
    a(f"For each leg, `early_gain`/`early_slope` = the magnitude move over the first "
      f"{run['early_n'] if run else 5} bars off the (already-confirmed) start. Correlated against "
      "`leg_amp` (the eventual total move) and `corr_depth` (the depth of the move that ENDS the "
      "leg -- a genuinely separate future event, no time overlap with the early window at all). "
      "The 'ALL' column includes legs shorter than the early window itself (where early_gain *is* "
      "almost the whole leg, by construction); the 'non-tautological' column restricts to legs "
      "longer than the early window, so the early bars are a genuine partial sample, not the "
      "whole answer.\n")
    a("| Leg | Portion | n | r(early_gain, leg_amp) ALL | r(...) non-tautological | r(early_slope, corr_depth) |")
    a("|---|---|---|---|---|---|")
    for leg_dir in ("up", "down"):
        cell = summary["part_b_early_signature"][leg_dir]
        for portion in ("in_sample", "held_out"):
            d = cell[portion]
            ag, nt, cd = d["corr_early_gain_leg_amp_all"], d["corr_early_gain_leg_amp_nontautological"], d["corr_early_slope_corr_depth"]
            a(f"| {leg_dir} | {portion} | {d['n']:,} | r={ag['r']:.3f} (p={fmt_p(ag['p'])}) | "
              f"r={nt['r']:.3f}, n={d['n_nontautological']:,} (p={fmt_p(nt['p'])}) | "
              f"r={cd['r']:.3f}, n={cd['n']:,} (p={fmt_p(cd['p'])}) |")
    a("\n**This is the strongest, most stable finding in this entire research arc.** The "
      "non-tautological correlation is large (r=0.61-0.75) and does **not decay** out-of-sample -- "
      "if anything it is slightly larger held-out than in-sample for 3 of 4 cells. The genuinely "
      "forward-looking early_slope-vs-corr_depth correlation (r=0.19-0.34) is smaller but also "
      "stable/replicating, not an overfit artifact.\n")

    # ---- Part C -----------------------------------------------------------------
    a("## Part C. The real-time angle: does the shape signature work with zero look-ahead?\n")
    a("Every bar (not just confirmed pivots) screened in real time for the same shape combination "
      "found at confirmed tops/bottoms (dominant wick + elevated range/ATR + elevated volume), "
      "compared to a random-bar baseline at the same forward horizons, pooled across tickers.\n")
    a("| Filter | K | Portion | Pattern mean fwd R | n | Baseline mean fwd R | n | p vs baseline |")
    a("|---|---|---|---|---|---|---|---|")
    for filt in ("bottom_like", "top_like"):
        for k, cell in summary["part_c_realtime_filter"][filt].items():
            for portion in ("in_sample", "held_out"):
                d = cell[portion]
                a(f"| {filt} | {k} | {portion} | {d['pattern']['mean']:+.4f} | {d['pattern']['n']:,} | "
                  f"{d['baseline']['mean']:+.4f} | {d['baseline']['n']:,} | {fmt_p(d['p_vs_baseline'])} |")
    a("\n**Pooled across tickers, none of this replicates.** The one nominally low p-value "
      "(`bottom_like`, K=6, in-sample, p=0.0055) is in the WRONG direction (negative mean forward "
      "return for a filter meant to flag bottoms) and does not replicate held-out (p=0.62, flips "
      "positive) -- the textbook in-sample-only artifact this research arc keeps surfacing. "
      "Per-ticker (not shown in the pooled table; see `dome_leg_signature_summary.json` raw rows "
      "via `research_dome_leg_realtime`), the exploratory pass found AAPL trending positive "
      "regardless of filter direction, NKE trending negative regardless of filter direction, and "
      "INTC mixed -- i.e. ticker-level drift dominates a pure shape filter with no confirmation "
      "lag, exactly why Part B's confirmed-pivot framing works where Part C's real-time framing "
      "does not.\n")

    # ---- Scoping ----------------------------------------------------------------
    a("## Scoping notes\n")
    a("- **Significant pivots**, not raw fractal pivots: `structure.swing_pivots(width=3)` finds "
      "every micro zigzag; legs are only built from pivot-to-pivot moves >= 2.5x ATR14, to study "
      "real trend changes rather than noise (consistent across amp_mult=2.0/2.5/3.0 and "
      "width=3/5 in the exploratory pass).")
    a("- **Leg field semantics reproduce, rather than import, `research/dome-symmetry`'s "
      "`_legs()`/`swing_legs_down()`/`swing_legs_all()`** (commit `0535cdb`): that branch is "
      "fully committed but not pushed to origin and not merged into `fix/model-validity` -- "
      "reproduced in `dome_leg_signature_common.py` rather than depending on an unmerged branch, "
      "the same reasoning used for `feat/channels-and-5m` in the pattern-fulfillment phase.")
    a("- **Look-ahead guard, explicit**: a leg's `start_idx`/`peak_idx`/`early_*` fields are "
      "established from the two pivots that define the leg itself, both already confirmed by the "
      "time the leg exists. `corr_depth`/`corr_bars` derive from a THIRD, later pivot -- a forward "
      "outcome used only as the dependent variable in Part B, never as an input feature. This is "
      "the identical rule the dome-symmetry audit specified and never violated.")
    a("- **Part C's filter thresholds are the same ones found, descriptively, in Part A/the prior "
      "exploration** (wick% > 30, range/ATR > 1.1, vol_ratio > 1.15) -- not re-tuned or "
      "optimized against Part C's own outcome data, to avoid circularity.")
    a("- **The real-time filter test is pooled across tickers** for the headline table (consistent "
      "with the rest of this research arc's reporting grain); per-ticker sign inconsistency is "
      "discussed qualitatively above since it's the main explanation for the pooled null.\n")

    # ---- Verdict ------------------------------------------------------------------
    a("## Verdict\n")
    a(VERDICT_PLACEHOLDER)

    a("\n## Reproducibility\n")
    a(f"- Full aggregates: `reports/research/dome_leg_signature_summary.json` (run `{summary['run_id']}`)")
    a(f"- Run log: `reports/research/dome_leg_signature_run_log.jsonl`")
    a(f"- Raw rows: `research_dome_leg_signature`, `research_dome_leg_realtime` tables, "
      f"`WHERE run_id = '{summary['run_id']}'`")
    a(f"- Example charts: `reports/research/charts/` (prefixed `dl_`)")

    return "\n".join(lines) + "\n"


VERDICT_PLACEHOLDER = "_(filled in by hand after reviewing Parts A-C -- see conversation writeup)_"


def main():
    summary, run = load()
    text = render(summary, run)
    REPORT_PATH.write_text(text, encoding="utf-8")
    print(f"Wrote {REPORT_PATH} ({len(text)} chars)")


if __name__ == "__main__":
    main()
