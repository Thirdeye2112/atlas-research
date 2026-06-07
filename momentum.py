#!/usr/bin/env python
"""
run_nightly.py — nightly pipeline entry point.

Called by cron, systemd, or manually.  Runs the full nightly pipeline
for today's date (or a specified date).

Usage:
    python scripts/run_nightly.py
    python scripts/run_nightly.py --date 2026-06-06
    python scripts/run_nightly.py --skip-ingest
    python scripts/run_nightly.py --skip-features
    python scripts/run_nightly.py --force-full    # re-download full history

Cron example (02:00 ET weekdays):
    0 2 * * 1-5 cd /app && python scripts/run_nightly.py >> logs/nightly.log 2>&1
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from config import settings
from atlas_research.db.connection import check_connection
from atlas_research.pipelines.nightly_pipeline import run_nightly
from atlas_research.utils.logging import configure_logging, get_logger

configure_logging(level=settings.LOG_LEVEL, fmt=settings.LOG_FORMAT)
log = get_logger("run_nightly")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the nightly atlas-research pipeline")
    parser.add_argument("--date",          default=None,  help="Date YYYY-MM-DD (default: today)")
    parser.add_argument("--force-full",    action="store_true", help="Re-download full history")
    parser.add_argument("--skip-ingest",   action="store_true")
    parser.add_argument("--skip-features", action="store_true")
    parser.add_argument("--skip-labels",   action="store_true")
    parser.add_argument("--skip-export",   action="store_true")
    args = parser.parse_args()

    run_date = (
        datetime.strptime(args.date, "%Y-%m-%d").date()
        if args.date else date.today()
    )

    if not check_connection():
        log.error("run_nightly.db_unreachable")
        sys.exit(1)

    result = run_nightly(
        run_date,
        force_full_ingest=args.force_full,
        skip_ingest=args.skip_ingest,
        skip_features=args.skip_features,
        skip_labels=args.skip_labels,
        skip_export=args.skip_export,
        triggered_by="cli",
    )

    status = result["status"]
    print(f"\nRun {result['run_id']} — {status}")
    print(f"  Date:     {result['date']}")
    print(f"  Tickers:  {result['tickers_processed']}")
    print(f"  Bars:     {result['bars_inserted']}")
    print(f"  Features: {result['features_generated']}")
    print(f"  Labels:   {result['labels_generated']}")

    sys.exit(0 if status == "complete" else 1)


if __name__ == "__main__":
    main()
