"""
backfill_wide_table.py — Backfill feature_snapshots_wide from EAV history.

Pivots all dates in feature_snapshots into the wide table.
Run once after feature_snapshots_wide is created.
Nightly refresh (single date) is handled by the nightly pipeline.

Usage
-----
    python scripts/backfill_wide_table.py
    python scripts/backfill_wide_table.py --from 2024-01-01   # backfill from date
    python scripts/backfill_wide_table.py --workers 4         # parallel (spawn)
    python scripts/backfill_wide_table.py --dry-run           # count dates, no write
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import psycopg2

from atlas_research.exports.wide_export import refresh_wide
from atlas_research.utils.logging import configure_logging, get_logger

configure_logging()
log = get_logger("backfill_wide_table")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill feature_snapshots_wide from EAV")
    parser.add_argument("--from", dest="from_date", default=None,
                        help="Start date YYYY-MM-DD (default: earliest in EAV)")
    parser.add_argument("--to", dest="to_date", default=None,
                        help="End date YYYY-MM-DD (default: latest in EAV)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Count dates and rows without writing")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("[ERROR] DATABASE_URL not set")

    # Load distinct dates from EAV
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            conds = []
            params = []
            if args.from_date:
                conds.append("date >= %s")
                params.append(datetime.strptime(args.from_date, "%Y-%m-%d").date())
            if args.to_date:
                conds.append("date <= %s")
                params.append(datetime.strptime(args.to_date, "%Y-%m-%d").date())
            where = ("WHERE " + " AND ".join(conds)) if conds else ""
            cur.execute(
                f"SELECT DISTINCT date FROM feature_snapshots {where} ORDER BY date",
                params
            )
            all_dates = [r[0] for r in cur.fetchall()]

    print(f"\nBackfill feature_snapshots_wide")
    print(f"  Dates to process: {len(all_dates)}")
    if all_dates:
        print(f"  Range: {all_dates[0]} to {all_dates[-1]}")

    if args.dry_run:
        print("  [--dry-run] No writes performed.")
        return

    if not all_dates:
        print("  No dates found. Run nightly pipeline first to populate feature_snapshots.")
        return

    t0 = time.monotonic()
    total_rows = 0
    errors = 0

    for i, d in enumerate(all_dates, 1):
        try:
            n = refresh_wide(d, db_url)
            total_rows += n
            if i % 50 == 0 or i == len(all_dates):
                elapsed = time.monotonic() - t0
                rate = i / elapsed if elapsed > 0 else 0
                eta = (len(all_dates) - i) / rate if rate > 0 else 0
                print(f"  [{i:>4}/{len(all_dates)}] {d}  {n:>4} rows  "
                      f"{elapsed:.0f}s elapsed  ETA {eta:.0f}s")
        except Exception as exc:
            errors += 1
            log.warning("backfill.date_failed", date=str(d), error=str(exc))

    elapsed = time.monotonic() - t0
    print(f"\n  Done: {total_rows:,} rows across {len(all_dates)} dates in {elapsed:.0f}s")
    if errors:
        print(f"  Errors: {errors} dates failed (check logs)")


if __name__ == "__main__":
    main()
