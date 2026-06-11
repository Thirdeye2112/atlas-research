#!/usr/bin/env python3
"""
seed_market_calendar.py -- Populate market_calendar with key dates

Covers 2019–2027:
  - FOMC meeting dates
  - Options expiration (3rd Friday of every month)
  - Quarter-end dates (Mar 31, Jun 30, Sep 30, Dec 31)
  - Triple witching (3rd Friday of Mar, Jun, Sep, Dec)
  - Half-year end (Jun 30, Dec 31)

Usage:
    python scripts/seed_market_calendar.py
    python scripts/seed_market_calendar.py --dry-run
    python scripts/seed_market_calendar.py --force  # overwrite existing
"""

from __future__ import annotations

import argparse
import calendar
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text

from atlas_research.db.connection import get_raw_engine
from atlas_research.utils.logging import configure_logging, get_logger
from config import settings

configure_logging(level=settings.LOG_LEVEL, fmt=settings.LOG_FORMAT)
log = get_logger("market_calendar")


# ─── FOMC meeting dates 2019-2027 (announcement / decision day) ──────────────
# Source: Federal Reserve press releases + projected schedule
FOMC_DATES: list[str] = [
    # 2019
    "2019-01-30", "2019-03-20", "2019-05-01", "2019-06-19",
    "2019-07-31", "2019-09-18", "2019-10-30", "2019-12-11",
    # 2020
    "2020-01-29", "2020-03-03", "2020-03-15",  # emergency
    "2020-04-29", "2020-06-10", "2020-07-29",
    "2020-09-16", "2020-11-05", "2020-12-16",
    # 2021
    "2021-01-27", "2021-03-17", "2021-04-28", "2021-06-16",
    "2021-07-28", "2021-09-22", "2021-11-03", "2021-12-15",
    # 2022
    "2022-01-26", "2022-03-16", "2022-05-04", "2022-06-15",
    "2022-07-27", "2022-09-21", "2022-11-02", "2022-12-14",
    # 2023
    "2023-02-01", "2023-03-22", "2023-05-03", "2023-06-14",
    "2023-07-26", "2023-09-20", "2023-11-01", "2023-12-13",
    # 2024
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12",
    "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    # 2025
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    # 2026
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
    # 2027
    "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-16",
    "2027-07-28", "2027-09-15", "2027-10-27", "2027-12-08",
]


def nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """Return the Nth occurrence of weekday (0=Mon … 4=Fri) in year/month."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    target = first + timedelta(days=offset + 7 * (n - 1))
    return target


def options_expiry_dates(start_year: int = 2019, end_year: int = 2027) -> list[date]:
    """3rd Friday of every month."""
    result = []
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            result.append(nth_weekday_of_month(year, month, 4, 3))  # Friday=4
    return result


def triple_witching_dates(start_year: int = 2019, end_year: int = 2027) -> list[date]:
    """3rd Friday of Mar, Jun, Sep, Dec (months 3, 6, 9, 12)."""
    result = []
    for year in range(start_year, end_year + 1):
        for month in [3, 6, 9, 12]:
            result.append(nth_weekday_of_month(year, month, 4, 3))
    return result


def quarter_end_dates(start_year: int = 2019, end_year: int = 2027) -> list[date]:
    """Mar 31, Jun 30, Sep 30, Dec 31 for each year."""
    result = []
    for year in range(start_year, end_year + 1):
        result.extend([
            date(year, 3, 31),
            date(year, 6, 30),
            date(year, 9, 30),
            date(year, 12, 31),
        ])
    return result


def half_year_end_dates(start_year: int = 2019, end_year: int = 2027) -> list[date]:
    """Jun 30, Dec 31."""
    result = []
    for year in range(start_year, end_year + 1):
        result.extend([date(year, 6, 30), date(year, 12, 31)])
    return result


def build_rows() -> list[dict]:
    rows = []

    # FOMC dates
    for ds in FOMC_DATES:
        d = date.fromisoformat(ds)
        rows.append({
            "date": d,
            "event_type": "fomc_meeting",
            "description": f"FOMC rate decision {d.strftime('%b %Y')}",
            "is_trading_day": True,
            "metadata": json.dumps({"source": "fed_reserve"}),
        })

    # Options expiry (3rd Friday monthly)
    triple = set(triple_witching_dates())
    for d in options_expiry_dates():
        rows.append({
            "date": d,
            "event_type": "options_expiry",
            "description": f"Monthly options expiration {d.strftime('%b %Y')}",
            "is_trading_day": True,
            "metadata": json.dumps({"is_triple_witching": d in triple}),
        })

    # Triple witching (3rd Friday of Mar/Jun/Sep/Dec)
    for d in triple:
        rows.append({
            "date": d,
            "event_type": "triple_witching",
            "description": f"Triple witching {d.strftime('%b %Y')}",
            "is_trading_day": True,
            "metadata": json.dumps({}),
        })

    # Quarter-end dates
    for d in quarter_end_dates():
        rows.append({
            "date": d,
            "event_type": "quarter_end",
            "description": f"Quarter end Q{((d.month - 1) // 3) + 1} {d.year}",
            "is_trading_day": d.weekday() < 5,
            "metadata": json.dumps({}),
        })

    # Half-year end
    for d in half_year_end_dates():
        rows.append({
            "date": d,
            "event_type": "half_year_end",
            "description": f"Half-year end {d.strftime('%b %Y')}",
            "is_trading_day": d.weekday() < 5,
            "metadata": json.dumps({}),
        })

    return rows


def seed(dry_run: bool = False, force: bool = False) -> int:
    rows = build_rows()
    log.info("Seeding %d calendar events (%s)", len(rows), "DRY RUN" if dry_run else "live")

    if dry_run:
        by_type: dict[str, int] = {}
        for r in rows:
            by_type[r["event_type"]] = by_type.get(r["event_type"], 0) + 1
        for et, cnt in sorted(by_type.items()):
            print(f"  {et:25s}  {cnt:4d} rows")
        print(f"  {'TOTAL':25s}  {len(rows):4d} rows")
        return len(rows)

    engine = get_raw_engine()
    inserted = 0
    with engine.begin() as conn:
        for row in rows:
            if force:
                result = conn.execute(text("""
                    INSERT INTO market_calendar
                        (date, event_type, description, is_trading_day, metadata)
                    VALUES
                        (:date, :event_type, :description, :is_trading_day, CAST(:metadata AS jsonb))
                    ON CONFLICT (date, event_type) DO UPDATE SET
                        description    = EXCLUDED.description,
                        is_trading_day = EXCLUDED.is_trading_day,
                        metadata       = EXCLUDED.metadata
                """), row)
            else:
                result = conn.execute(text("""
                    INSERT INTO market_calendar
                        (date, event_type, description, is_trading_day, metadata)
                    VALUES
                        (:date, :event_type, :description, :is_trading_day, CAST(:metadata AS jsonb))
                    ON CONFLICT (date, event_type) DO NOTHING
                """), row)
            inserted += result.rowcount

    log.info("market_calendar: %d rows inserted/updated.", inserted)
    return inserted


def show_summary():
    engine = get_raw_engine()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT event_type, COUNT(*) as n,
                   MIN(date) as earliest, MAX(date) as latest
            FROM market_calendar
            GROUP BY event_type
            ORDER BY n DESC
        """)).fetchall()

    if not result:
        print("market_calendar is empty.")
        return

    print(f"\n{'Event Type':25s} {'Count':>7} {'Earliest':>12} {'Latest':>12}")
    print("-" * 62)
    total = 0
    for r in result:
        print(f"{r.event_type:25s} {r.n:>7d} {str(r.earliest):>12} {str(r.latest):>12}")
        total += r.n
    print("-" * 62)
    print(f"{'TOTAL':25s} {total:>7d}")


def main():
    parser = argparse.ArgumentParser(description="Seed market_calendar table")
    parser.add_argument("--dry-run", action="store_true", help="Print counts without inserting")
    parser.add_argument("--force", action="store_true", help="Upsert (overwrite existing rows)")
    parser.add_argument("--show-only", action="store_true", help="Show current DB summary only")
    args = parser.parse_args()

    if args.show_only:
        show_summary()
        return

    n = seed(dry_run=args.dry_run, force=args.force)
    if not args.dry_run:
        print(f"\nInserted/updated {n} rows.")
        show_summary()


if __name__ == "__main__":
    main()
