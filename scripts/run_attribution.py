"""
Atlas Prediction Error Attribution Pipeline
============================================
Runs the full attribution loop:
  1. Compute matured outcomes (fill actual_return, hit_or_miss)
  2. Classify failures (write prediction_error_attribution rows)
  3. Compute signal reliability scores (rolling 30/90/180d)
  4. Generate adaptive weight recommendations
  5. Write PREDICTION_ERROR_ATTRIBUTION_REPORT.md

Usage:
    python scripts/run_attribution.py
    python scripts/run_attribution.py --as-of 2026-06-01 --horizon 5 --lookback 180
    python scripts/run_attribution.py --backfill --backfill-date 2026-01-01
    python scripts/run_attribution.py --report-only

Schema migration (first run):
    psql $DATABASE_URL -f db/schema_attribution.sql
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from atlas_research.attribution.outcomes import compute_matured_outcomes
from atlas_research.attribution.classifier import attribute_errors
from atlas_research.attribution.reliability import compute_signal_reliability
from atlas_research.attribution.recommendations import generate_recommendations
from atlas_research.attribution.report import write_attribution_report
from atlas_research.attribution.tracker import record_predictions_from_snapshots
from atlas_research.utils.logging import get_logger

log = get_logger("run_attribution")


def main() -> int:
    parser = argparse.ArgumentParser(description="Atlas attribution pipeline")
    parser.add_argument("--as-of", default=None,
                        help="Run as of this date (YYYY-MM-DD). Defaults to today.")
    parser.add_argument("--horizon", type=int, default=5,
                        help="Primary horizon to report on (default 5)")
    parser.add_argument("--lookback", type=int, default=180,
                        help="Days of history for the report (default 180)")
    parser.add_argument("--backfill", action="store_true",
                        help="Backfill predictions from existing confluence_score_snapshots")
    parser.add_argument("--backfill-date", default=None,
                        help="Backfill predictions for this specific date (YYYY-MM-DD)")
    parser.add_argument("--report-only", action="store_true",
                        help="Skip computation; only regenerate the report")
    parser.add_argument("--no-report", action="store_true",
                        help="Run computation but skip report generation")
    parser.add_argument("--out", default="reports/PREDICTION_ERROR_ATTRIBUTION_REPORT.md",
                        help="Report output path")
    args = parser.parse_args()

    as_of = date.fromisoformat(args.as_of) if args.as_of else date.today()
    print(f"\nAtlas Attribution Pipeline")
    print(f"As-of date : {as_of}")
    print(f"Horizon    : {args.horizon}d")
    print("-" * 50)

    # ── Optional backfill ─────────────────────────────────────────────────────
    if args.backfill or args.backfill_date:
        backfill_date = date.fromisoformat(args.backfill_date) if args.backfill_date else as_of
        print(f"\nBackfilling predictions from snapshots for {backfill_date}...")
        n_backfill = record_predictions_from_snapshots(backfill_date)
        print(f"  Backfilled {n_backfill} prediction records")

    if args.report_only:
        print("\nReport-only mode: skipping computation.")
    else:
        # ── Step 1: Compute matured outcomes ──────────────────────────────────
        print(f"\nStep 1: Computing matured outcomes (horizon={args.horizon}d)...")
        totals = compute_matured_outcomes(as_of=as_of, horizons=[5, 10, 20])
        for horizon_label, n in totals.items():
            print(f"  {horizon_label}: {n} outcomes computed")

        # ── Step 2: Classify failures ─────────────────────────────────────────
        print("\nStep 2: Classifying prediction errors...")
        n_classified = attribute_errors()
        print(f"  {n_classified} attributions written")

        # ── Step 3: Signal reliability ────────────────────────────────────────
        print("\nStep 3: Computing signal reliability (30/90/180d windows)...")
        rel_totals = compute_signal_reliability(as_of=as_of)
        for comp, n in rel_totals.items():
            if n > 0:
                print(f"  {comp}: {n} reliability rows written")

        # ── Step 4: Adaptive recommendations ─────────────────────────────────
        print("\nStep 4: Generating adaptive weight recommendations...")
        n_recs = generate_recommendations(as_of=as_of)
        print(f"  {n_recs} recommendations generated")

    # ── Step 5: Report ────────────────────────────────────────────────────────
    if not args.no_report:
        print("\nStep 5: Writing attribution report...")
        out_path = _ROOT / args.out
        report_path = write_attribution_report(
            end_date=as_of,
            lookback_days=args.lookback,
            horizon_days=args.horizon,
            out_path=out_path,
        )
        print(f"  Report written: {report_path}")

    print("\nAttribution pipeline complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
