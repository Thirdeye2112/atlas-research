#!/usr/bin/env python3
"""
backfill_full_universe.py
--------------------------
Downloads 5 years of daily OHLCV for every active security that has
< 100 bars in raw_bars.  Uses the existing yahoo_ingest module so
upserts, retries, and rate-limiting are handled consistently.

Batches of 50 tickers, 2-second pause between batches.
Expected runtime: 4-6 hours for ~4,000 tickers.

Run in background after fetch_full_us_universe.py + init_db.py:
    python scripts/backfill_full_universe.py
    python scripts/backfill_full_universe.py --min-bars 500  # stricter threshold
    python scripts/backfill_full_universe.py --dry-run       # list tickers, don't download
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text

from atlas_research.db.connection import get_raw_engine, check_connection
from atlas_research.ingest.yahoo_ingest import download_universe
from atlas_research.utils.logging import configure_logging, get_logger

configure_logging()
log = get_logger("backfill_full_universe")


def get_tickers_needing_backfill(engine, min_bars: int) -> list[str]:
    """Return active tickers with fewer than min_bars rows in raw_bars."""
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT s.ticker
            FROM securities s
            LEFT JOIN (
                SELECT ticker, COUNT(*) AS bar_count
                FROM raw_bars
                GROUP BY ticker
            ) rb ON rb.ticker = s.ticker
            WHERE s.active = true
              AND COALESCE(rb.bar_count, 0) < :min_bars
            ORDER BY s.ticker
        """), {"min_bars": min_bars}).fetchall()
    return [r[0] for r in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill OHLCV for new tickers")
    parser.add_argument(
        "--min-bars", type=int, default=100,
        help="Backfill tickers with fewer than this many bars (default: 100)"
    )
    parser.add_argument(
        "--years", type=int, default=5,
        help="Years of history to download (default: 5)"
    )
    parser.add_argument(
        "--batch-size", type=int, default=50,
        help="Tickers per yfinance batch (default: 50)"
    )
    parser.add_argument(
        "--batch-delay", type=float, default=2.0,
        help="Seconds between batches (default: 2.0)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print tickers that need backfill without downloading"
    )
    args = parser.parse_args()

    if not check_connection():
        log.error("backfill.db_unreachable")
        sys.exit(1)

    engine = get_raw_engine()
    tickers = get_tickers_needing_backfill(engine, args.min_bars)

    if not tickers:
        print(f"No tickers with < {args.min_bars} bars. Nothing to do.")
        return

    end_date   = date.today()
    start_date = end_date - timedelta(days=365 * args.years)
    n_batches  = (len(tickers) + args.batch_size - 1) // args.batch_size
    # Rough ETA: each batch of 50 takes ~6s download + 2s pause
    eta_min    = round(n_batches * 8 / 60, 1)

    print(f"\nBackfill plan:")
    print(f"  Tickers needing backfill:  {len(tickers)}")
    print(f"  Date range:               {start_date} → {end_date} ({args.years} years)")
    print(f"  Batch size:               {args.batch_size}")
    print(f"  Batches:                  {n_batches}")
    print(f"  Estimated time:           ~{eta_min} min ({eta_min/60:.1f} hrs)")
    print()

    if args.dry_run:
        print("DRY RUN — tickers that would be backfilled:")
        for i, t in enumerate(tickers, 1):
            print(f"  {i:4d}. {t}")
        return

    log.info(
        "backfill_full.start",
        tickers=len(tickers),
        start=str(start_date),
        end=str(end_date),
        batches=n_batches,
    )

    t0 = time.time()
    total_bars, failed = download_universe(
        tickers,
        start_date,
        end_date,
        batch_size=args.batch_size,
        batch_delay=args.batch_delay,
    )
    elapsed = time.time() - t0

    # Final count
    with engine.connect() as conn:
        securities_count = conn.execute(
            text("SELECT COUNT(*) FROM securities WHERE active=true")
        ).scalar()
        bars_tickers = conn.execute(
            text("SELECT COUNT(DISTINCT ticker) FROM raw_bars")
        ).scalar()

    print(f"\nBackfill complete.")
    print(f"  Bars inserted:      {total_bars:,}")
    print(f"  Failed tickers:     {len(failed)}")
    print(f"  Elapsed:            {elapsed/60:.1f} min")
    print(f"  Active securities:  {securities_count}")
    print(f"  raw_bars tickers:   {bars_tickers}")

    if failed:
        print(f"\nFailed tickers ({len(failed)}):")
        for ticker, err in failed[:20]:
            print(f"  {ticker}: {err}")
        if len(failed) > 20:
            print(f"  ... and {len(failed) - 20} more")

    log.info(
        "backfill_full.done",
        bars=total_bars,
        failed=len(failed),
        elapsed_min=round(elapsed / 60, 1),
        securities=securities_count,
        raw_bars_tickers=bars_tickers,
    )


if __name__ == "__main__":
    main()
