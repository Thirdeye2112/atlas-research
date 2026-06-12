"""
build_ipo_registry.py
---------------------
Infers IPO dates from first appearance in raw_bars.
Tickers whose first bar is before 2015-01-01 are skipped (pre-window, not true IPOs).

Usage:
    python scripts/build_ipo_registry.py [--min-year 2015] [--dry-run]
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from sqlalchemy import create_engine, text
import os

engine = create_engine(os.environ["DATABASE_URL"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-year", type=int, default=2015)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cutoff = date(args.min_year, 1, 1)

    with engine.connect() as c:
        # Get first appearance date for every ticker in raw_bars
        rows = c.execute(text("""
            SELECT ticker, MIN(date)::date AS first_date,
                   (SELECT close FROM raw_bars rb2
                    WHERE rb2.ticker = rb.ticker ORDER BY date ASC LIMIT 1) AS ipo_price
            FROM raw_bars rb
            GROUP BY ticker
            HAVING MIN(date)::date >= :cutoff
            ORDER BY first_date
        """), {"cutoff": cutoff}).fetchall()

        print(f"Found {len(rows)} tickers with first bar >= {cutoff}")

        # Get already-registered tickers
        existing = {r[0] for r in c.execute(text("SELECT ticker FROM ipo_registry")).fetchall()}

        new_entries = [(r.ticker, r.first_date, r.ipo_price) for r in rows if r.ticker not in existing]
        print(f"New entries to insert: {len(new_entries)}")

        if args.dry_run:
            print("\n[DRY RUN] Would insert:")
            for ticker, first_date, ipo_price in new_entries[:20]:
                print(f"  {ticker:<8} {first_date}  ${ipo_price:.2f}")
            if len(new_entries) > 20:
                print(f"  ... and {len(new_entries)-20} more")
            return

        inserted = 0
        for ticker, first_date, ipo_price in new_entries:
            c.execute(text("""
                INSERT INTO ipo_registry (ticker, ipo_date, ipo_price, source)
                VALUES (:ticker, :ipo_date, :ipo_price, 'inferred')
                ON CONFLICT (ticker) DO NOTHING
            """), {"ticker": ticker, "ipo_date": first_date, "ipo_price": ipo_price})
            inserted += 1

        c.commit()
        print(f"Inserted {inserted} IPO records.")

        # Print sample
        sample = c.execute(text("""
            SELECT ticker, ipo_date, ipo_price FROM ipo_registry ORDER BY ipo_date DESC LIMIT 10
        """)).fetchall()
        print("\nMost recent IPOs in registry:")
        print(f"  {'Ticker':<8} {'IPO Date':<12} {'Price':>8}")
        print("  " + "-" * 32)
        for r in sample:
            print(f"  {r.ticker:<8} {r.ipo_date!s:<12} ${float(r.ipo_price):>7.2f}")


if __name__ == "__main__":
    main()
