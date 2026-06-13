#!/usr/bin/env python
"""
scripts/run_parameter_search.py
================================
Research automation layer: parameter grid search, robustness evaluation,
follow-up generation, and signal promotion.

Examples
--------
    # Run SPY down-streak grid (N=2..6) and gap grid (threshold=0.5-3%)
    python scripts/run_parameter_search.py --default

    # Run a specific condition grid
    python scripts/run_parameter_search.py --ticker SPY --condition down_streak

    # Run a single parameter set with follow-ups
    python scripts/run_parameter_search.py --ticker SPY --condition down_streak --n 4

    # Run gap searches
    python scripts/run_parameter_search.py --ticker SPY --condition gap_down

    # Up streaks
    python scripts/run_parameter_search.py --ticker SPY --condition up_streak

    # Skip DB persistence (dry-run)
    python scripts/run_parameter_search.py --default --no-save

    # Parse a text block for hypotheses
    python scripts/run_parameter_search.py --ingest-text "S&P rarely drops 4 days straight."

    # Show what would be promoted from existing runs (no re-run)
    python scripts/run_parameter_search.py --review-only

Output
------
    Table of parameter sets ranked by 5d edge score.
    Robustness verdict per row (pass/fail with reason).
    Promotion verdicts (PROMOTED / REJECTED).
    Auto-generated follow-ups for best parameter.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from atlas_research.probability.parameter_search import (
    run_parameter_search,
    print_search_table,
    PARAM_GRIDS,
)
from atlas_research.probability.promotion import (
    evaluate_promotion,
    promote_spec,
    print_promotion_result,
)
from atlas_research.probability.followups import (
    generate_followup_results,
    print_followup_results,
)
from atlas_research.probability.engine import load_bars, detect_condition


# ── Helpers ───────────────────────────────────────────────────────────────────

def _condition_label(condition_type: str, params: dict) -> str:
    if "streak" in condition_type:
        return f"{condition_type} N={params.get('n', '?')}"
    if "gap" in condition_type:
        return f"{condition_type} {params.get('threshold_pct', '?')}%"
    return condition_type


def _run_grid(
    ticker: str,
    condition_type: str,
    param_grid: list[dict],
    save: bool,
    run_followups: bool,
) -> list[dict]:
    """Run grid search, print table, print promotions, print follow-ups."""

    print(f"\nRunning {condition_type} grid for {ticker}...")
    results = run_parameter_search(ticker, condition_type, param_grid, save=save)

    print_search_table(ticker, condition_type, results)

    # ── Promotion evaluation ───────────────────────────────────────────────
    print("  Promotion verdicts:")
    promoted_results = []
    for r in sorted(results, key=lambda x: list(x["params"].values())[0]):
        if r["error"]:
            continue
        promoted, score, reasons = evaluate_promotion(
            [],
            r["stats"],
            r["robustness"],
            n_override=r["n_events"],
        )
        label = f"{ticker} {_condition_label(condition_type, r['params'])}"
        print_promotion_result(label, promoted, score, reasons)

        if promoted and save and r["spec_id"]:
            promote_spec(
                spec_id=r["spec_id"],
                ticker=ticker,
                score=score,
                reasons=reasons,
                recent_signal_date=None,
            )
            promoted_results.append(r)

    # ── Follow-up for best robust/promoted result ─────────────────────────
    if run_followups and results:
        # Prefer best-scoring result that passed robustness; fall back to top overall
        robust_results = [r for r in results
                          if r["robustness"] and r["robustness"].passed and r["score"] > 0]
        best = robust_results[0] if robust_results else results[0]
        if best["score"] > 0 and not best["error"]:
            print()
            df = load_bars(ticker)
            followups = generate_followup_results(
                ticker, condition_type, best["params"], df=df,
            )
            base_label = f"{ticker} {_condition_label(condition_type, best['params'])}"
            print_followup_results(base_label, followups)

    return results


def cmd_default(save: bool) -> None:
    """Run SPY down-streak and gap-down grids (the default optimization suite)."""
    _run_grid("SPY", "down_streak", PARAM_GRIDS["down_streak"], save, run_followups=True)
    _run_grid("SPY", "gap_down",    PARAM_GRIDS["gap_down"],    save, run_followups=True)


def cmd_grid(ticker: str, condition_type: str, save: bool) -> None:
    """Run the full default grid for a given condition type."""
    grid = PARAM_GRIDS.get(condition_type)
    if grid is None:
        print(f"ERROR: No default grid for {condition_type!r}. "
              f"Available: {sorted(PARAM_GRIDS)}", file=sys.stderr)
        sys.exit(1)
    _run_grid(ticker, condition_type, grid, save, run_followups=True)


def cmd_single(ticker: str, condition_type: str, params: dict, save: bool) -> None:
    """Run a single parameter set and generate follow-ups."""
    _run_grid(ticker, condition_type, [params], save, run_followups=True)


def cmd_review(ticker: str) -> None:
    """
    Review existing DB backtest_runs for a ticker and print promotion verdicts
    without re-running any backtests.
    """
    from sqlalchemy import text
    from atlas_research.db.connection import get_connection

    with get_connection() as conn:
        rows = conn.execute(text("""
            SELECT ts.id as spec_id, ts.ticker, ts.condition_type, ts.params,
                   br.id as run_id, br.n_events, br.promoted,
                   br.robustness_passed, br.robustness_notes,
                   bres5.hit_rate  AS hr5,  bres5.avg_return  AS avg5,
                   bres20.hit_rate AS hr20, bres20.avg_return AS avg20
            FROM test_specifications ts
            JOIN LATERAL (
                SELECT * FROM backtest_runs
                WHERE spec_id = ts.id ORDER BY run_date DESC, id DESC LIMIT 1
            ) br ON TRUE
            LEFT JOIN backtest_results bres5
                ON bres5.run_id = br.id AND bres5.horizon_days = 5
            LEFT JOIN backtest_results bres20
                ON bres20.run_id = br.id AND bres20.horizon_days = 20
            WHERE ts.ticker = :t
            ORDER BY ts.condition_type, ts.params
        """), {"t": ticker.upper()}).fetchall()

    if not rows:
        print(f"  No runs found for {ticker}.")
        return

    print(f"\n  Reviewing {len(rows)} spec(s) for {ticker}:")
    for row in rows:
        import json
        params = json.loads(row[3])
        ctype  = row[2]
        n      = row[4]
        hr5    = (row[9]  or 0) * 100
        avg5   = row[10]  or 0
        hr20   = (row[11] or 0) * 100
        avg20  = row[12] or 0
        promo  = "PROMOTED" if row[6] else "       -"

        label = f"{ticker} {_condition_label(ctype, params)}"
        print(
            f"  {promo}  {label:<38}  n={n:>4}  "
            f"5d: {hr5:.0f}%/{avg5:+.2f}%  "
            f"20d: {hr20:.0f}%/{avg20:+.2f}%"
        )


def cmd_ingest(text: str, save: bool) -> None:
    """Parse text for research hypotheses and optionally save to DB."""
    from atlas_research.transcripts.hypothesis_pipeline import ingest_text, print_extracted
    hypotheses = ingest_text(text, save=save)
    print_extracted(hypotheses)
    if save and hypotheses:
        print(f"\n  {len(hypotheses)} hypothesis(es) saved to research_hypotheses.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/run_parameter_search.py",
        description="Atlas research automation — parameter search and signal promotion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--default", action="store_true",
        help="Run SPY down-streak + gap-down optimization suite",
    )
    parser.add_argument("--ticker",     metavar="TICKER", default="SPY")
    parser.add_argument(
        "--condition", metavar="CONDITION",
        choices=["down_streak", "up_streak", "gap_down", "gap_up"],
        help="Condition type (runs full default grid for that condition)",
    )
    parser.add_argument("--n",         type=int,   help="Streak length (for single-param run)")
    parser.add_argument("--threshold", type=float, help="Gap threshold %% (for single-param run)")
    parser.add_argument(
        "--review-only", action="store_true",
        help="Print promotion verdicts for existing DB runs without re-running",
    )
    parser.add_argument(
        "--ingest-text", metavar="TEXT",
        help="Extract research hypotheses from a text string",
    )
    parser.add_argument(
        "--no-save", action="store_true",
        help="Compute but do not write results to DB",
    )

    args = parser.parse_args()
    save = not args.no_save

    if args.ingest_text:
        cmd_ingest(args.ingest_text, save=save)
        return 0

    if args.review_only:
        cmd_review(args.ticker)
        return 0

    if args.default:
        cmd_default(save=save)
        return 0

    if args.condition:
        # Single param overrides full grid
        if args.n is not None:
            params = {"n": args.n}
            cmd_single(args.ticker, args.condition, params, save=save)
        elif args.threshold is not None:
            params = {"threshold_pct": args.threshold}
            cmd_single(args.ticker, args.condition, params, save=save)
        else:
            cmd_grid(args.ticker, args.condition, save=save)
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
