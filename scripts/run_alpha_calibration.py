#!/usr/bin/env python
"""
run_alpha_calibration.py — Atlas Alpha signal calibration bridge.

Syncs resolved signal_snapshots from atlas_alpha DB into atlas_research,
then runs full calibration across score buckets, patterns, exhaustion flags,
smart-gate, direction, and component scores.

Usage:
    python scripts/run_alpha_calibration.py               # full sync + calibrate
    python scripts/run_alpha_calibration.py --sync-only   # only pull snapshots
    python scripts/run_alpha_calibration.py --report-only # only run calibration (no sync)
    python scripts/run_alpha_calibration.py --min-samples 20

Env vars required:
    DATABASE_URL       — atlas_research DB (postgresql://...)
    DATABASE_URL_ALPHA — atlas_alpha DB   (postgresql://...)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

import os
from atlas_research.calibration.engine import (
    sync_snapshots,
    run_calibration,
    write_calibration,
    print_report,
    MIN_N_REPORT,
)
from atlas_research.utils.logging import configure_logging, get_logger

configure_logging()
log = get_logger("run_alpha_calibration")


def main() -> None:
    parser = argparse.ArgumentParser(description="Atlas Alpha calibration bridge")
    parser.add_argument("--sync-only",   action="store_true", help="Only sync snapshots, skip calibration")
    parser.add_argument("--report-only", action="store_true", help="Only run calibration, skip sync")
    parser.add_argument("--no-db",       action="store_true", help="Don't write calibration to DB")
    parser.add_argument("--min-samples", type=int, default=MIN_N_REPORT,
                        help=f"Minimum signal count per group (default: {MIN_N_REPORT})")
    args = parser.parse_args()

    research_url = os.environ.get("DATABASE_URL")
    alpha_url    = os.environ.get("DATABASE_URL_ALPHA")

    if not research_url:
        print("[ERROR] DATABASE_URL not set (atlas_research)", file=sys.stderr)
        sys.exit(1)

    if not args.report_only and not alpha_url:
        print("[ERROR] DATABASE_URL_ALPHA not set (atlas_alpha)", file=sys.stderr)
        print("  Set: $env:DATABASE_URL_ALPHA=\"postgresql://postgres:Postnat74%3F@localhost:5432/atlas_alpha\"",
              file=sys.stderr)
        sys.exit(1)

    # ── Phase 1: Sync ────────────────────────────────────────────────────────
    if not args.report_only:
        print(f"\n[1/3] Syncing Atlas Alpha signal snapshots -> atlas_research...")
        try:
            n_synced = sync_snapshots(alpha_url, research_url)
            print(f"      Synced {n_synced} snapshots (including 1d/3d return enrichment from raw_bars)")
            log.info("sync.complete", n_synced=n_synced)
        except Exception as e:
            print(f"[ERROR] Sync failed: {e}", file=sys.stderr)
            log.error("sync.failed", error=str(e))
            sys.exit(1)

    if args.sync_only:
        print("\n[--sync-only] Done. Skipping calibration.\n")
        return

    # ── Phase 2: Calibrate ───────────────────────────────────────────────────
    print(f"\n[2/3] Running calibration (min_samples={args.min_samples}, permutation_iters=5000)...")
    try:
        cal_rows = run_calibration(research_url, min_samples=args.min_samples)
        print(f"      Computed {len(cal_rows)} calibration rows across all signal types")
        log.info("calibration.complete", n_rows=len(cal_rows))
    except Exception as e:
        print(f"[ERROR] Calibration failed: {e}", file=sys.stderr)
        log.error("calibration.failed", error=str(e))
        sys.exit(1)

    # ── Phase 3: Write to DB ─────────────────────────────────────────────────
    if not args.no_db:
        print(f"\n[3/3] Writing calibration results to atlas_research.alpha_signal_calibrations...")
        try:
            n_written = write_calibration(research_url, cal_rows)
            print(f"      Written {n_written} rows")
            log.info("write.complete", n_written=n_written)
        except Exception as e:
            print(f"[ERROR] DB write failed: {e}", file=sys.stderr)
            log.error("write.failed", error=str(e))
            sys.exit(1)
    else:
        print("\n[--no-db] Skipping DB write.")

    # ── Print report ─────────────────────────────────────────────────────────
    print_report(cal_rows)


if __name__ == "__main__":
    main()
