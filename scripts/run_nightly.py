#!/usr/bin/env python
"""
run_nightly.py — Nightly pipeline entry point.

Usage:
    python scripts/run_nightly.py
    python scripts/run_nightly.py --skip-ingest
    python scripts/run_nightly.py --skip-ingest --skip-labels
    python scripts/run_nightly.py --date 2026-06-01
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
log = get_logger("run_nightly_cli")


def main() -> None:
    parser = argparse.ArgumentParser(description="Atlas Research -- nightly pipeline")
    parser.add_argument("--date",          default=None,  help="Run date YYYY-MM-DD (default: today)")
    parser.add_argument("--skip-ingest",   action="store_true")
    parser.add_argument("--skip-features", action="store_true")
    parser.add_argument("--skip-labels",   action="store_true")
    parser.add_argument("--skip-parquet",  action="store_true")
    parser.add_argument("--force-ingest",  action="store_true")
    args = parser.parse_args()

    run_date = (
        datetime.strptime(args.date, "%Y-%m-%d").date()
        if args.date else date.today()
    )

    if not check_connection():
        log.error("nightly.db_unreachable")
        sys.exit(1)

    result = run_nightly(
        run_date=run_date,
        force_full_ingest=args.force_ingest,
        skip_ingest=args.skip_ingest,
        skip_features=args.skip_features,
        skip_labels=args.skip_labels,
        skip_parquet=args.skip_parquet,
        triggered_by="cli",
    )

    status = result.get("status", "unknown")
    run_id = result.get("run_id", "?")

    print(f"\nRun {run_id} -- {status}")
    print(f"  Date:     {result.get('date', run_date)}")
    print(f"  Tickers:  {result.get('tickers_processed', '?')}")
    print(f"  Bars:     {result.get('bars_inserted', '?')}")
    print(f"  Features: {result.get('features_generated', '?')}")
    print(f"  Labels:   {result.get('labels_generated', '?')}")


if __name__ == "__main__":
    main()
