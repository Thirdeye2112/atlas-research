#!/usr/bin/env python
"""
scripts/run_pattern_scan.py
============================
Run the daily candlestick pattern scan across the full universe.

Usage
-----
    python scripts/run_pattern_scan.py
    python scripts/run_pattern_scan.py --date 2026-06-05
    python scripts/run_pattern_scan.py --ticker AAPL MSFT NVDA
    python scripts/run_pattern_scan.py --backfill-days 30
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/run_pattern_scan.py",
        description="Run daily candlestick pattern scan",
    )
    parser.add_argument("--date",    help="Scan date (YYYY-MM-DD, default: today)")
    parser.add_argument("--ticker",  nargs="+", help="Limit to specific tickers")
    parser.add_argument("--backfill-days", type=int, default=0,
                        help="Backfill N days of pattern scans (e.g. 30 for past month)")
    args = parser.parse_args()

    from atlas_research.patterns.scanner import PatternScanner
    scanner = PatternScanner()

    if args.backfill_days > 0:
        print(f"Backfilling pattern scan for {args.backfill_days} days...")
        today = date.today()
        for i in range(args.backfill_days, -1, -1):
            scan_date = today - timedelta(days=i)
            # Skip weekends
            if scan_date.weekday() >= 5:
                continue
            print(f"  Scanning {scan_date}...")
            stats = scanner.run(scan_date=scan_date, tickers=args.ticker)
            print(f"    {stats['signals_found']} signals, {stats['outcomes_resolved']} outcomes resolved")
        return 0

    scan_date = date.fromisoformat(args.date) if args.date else date.today()
    print(f"Running pattern scan for {scan_date}...")
    stats = scanner.run(scan_date=scan_date, tickers=args.ticker)

    print(f"\n{'─'*50}")
    print(f"  Date:             {stats['scan_date']}")
    print(f"  Tickers scanned:  {stats['tickers_scanned']}")
    print(f"  Signals found:    {stats['signals_found']}")
    print(f"  Signals written:  {stats['signals_written']}")
    print(f"  Outcomes resolved:{stats['outcomes_resolved']}")
    print(f"  Errors:           {stats['errors']}")
    print(f"{'─'*50}")
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
