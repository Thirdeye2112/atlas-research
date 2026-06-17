#!/usr/bin/env python
"""
backfill_recent_labels.py — one-time repair of the label gap.

The label factory used to require the LONGEST horizon (return_60d, 60 trading
days) before writing ANY label row, so computable 5-day labels were withheld
for ~60 trading days after each snapshot.  That left the labels table (and
therefore the exported parquet) without label_return_5d / label_positive_5d
for every date newer than ~2026-03-18, starving the most recent walk-forward
folds.

label_factory now writes partial rows (shortest-horizon gate).  This script
backfills the already-missing window efficiently: it loads each ticker's bars
once and bulk-upserts the recomputed labels for [--start, --end].

Usage:
    python scripts/backfill_recent_labels.py
    python scripts/backfill_recent_labels.py --start 2026-03-19 --end 2026-06-12
    python scripts/backfill_recent_labels.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from sqlalchemy import text

from atlas_research.db import connection, repository
from atlas_research.labels.label_factory import _compute_label_row
from atlas_research.utils.logging import configure_logging, get_logger

configure_logging()
log = get_logger("backfill_recent_labels")

_UPSERT = text("""
    INSERT INTO labels
        (ticker, date, return_1d, return_5d, return_10d, return_20d,
         return_60d, max_runup_20d, max_drawdown_20d, positive_5d, positive_20d)
    VALUES
        (:ticker, :date, :return_1d, :return_5d, :return_10d, :return_20d,
         :return_60d, :max_runup_20d, :max_drawdown_20d, :positive_5d, :positive_20d)
    ON CONFLICT (ticker, date) DO UPDATE SET
        return_1d        = EXCLUDED.return_1d,
        return_5d        = EXCLUDED.return_5d,
        return_10d       = EXCLUDED.return_10d,
        return_20d       = EXCLUDED.return_20d,
        return_60d       = EXCLUDED.return_60d,
        max_runup_20d    = EXCLUDED.max_runup_20d,
        max_drawdown_20d = EXCLUDED.max_drawdown_20d,
        positive_5d      = EXCLUDED.positive_5d,
        positive_20d     = EXCLUDED.positive_20d
""")


def _flush(batch: list[dict]) -> int:
    if not batch:
        return 0
    with connection.get_connection() as conn:
        conn.execute(_UPSERT, batch)
    return len(batch)


def main() -> None:
    p = argparse.ArgumentParser(description="Backfill missing recent labels")
    p.add_argument("--start", default="2026-03-19", help="First snap date to backfill")
    p.add_argument("--end",   default=None, help="Last snap date (default: max raw_bars date)")
    p.add_argument("--batch", type=int, default=5000)
    p.add_argument("--dry-run", action="store_true", help="Compute but do not write")
    args = p.parse_args()

    start = datetime.strptime(args.start, "%Y-%m-%d").date()
    with connection.get_connection() as conn:
        max_bar = conn.execute(text("SELECT MAX(date) FROM raw_bars")).scalar()
    end = datetime.strptime(args.end, "%Y-%m-%d").date() if args.end else max_bar

    # Only tickers that actually trade in the window need processing.
    with connection.get_connection() as conn:
        tickers = [r[0] for r in conn.execute(
            text("SELECT DISTINCT ticker FROM raw_bars WHERE date >= :s ORDER BY ticker"),
            {"s": start},
        ).fetchall()]

    print(f"Backfilling labels {start} -> {end} for {len(tickers):,} tickers "
          f"({'DRY RUN' if args.dry_run else 'writing'})")

    batch: list[dict] = []
    total = with_r5 = processed = 0
    for ti, ticker in enumerate(tickers):
        bars = repository.get_bars(ticker)
        if bars.empty or len(bars) < 2:
            continue
        bars = bars.sort_values("date").reset_index(drop=True)
        prices = bars["adjusted_close"].values
        highs  = bars["high"].values
        lows   = bars["low"].values
        dates  = bars["date"].tolist()
        n = len(bars)
        for i, snap in enumerate(dates):
            if snap < start or snap > end:
                continue
            if i + 1 >= n:          # need at least one forward bar
                continue
            row = _compute_label_row(ticker, snap, i, prices, highs, lows, dates)
            if row is None:
                continue
            total += 1
            if row.get("return_5d") is not None:
                with_r5 += 1
            batch.append(row)
            if not args.dry_run and len(batch) >= args.batch:
                processed += _flush(batch)
                batch = []
        if (ti + 1) % 1000 == 0:
            print(f"  ...{ti+1:,}/{len(tickers):,} tickers, {total:,} rows computed")

    if not args.dry_run:
        processed += _flush(batch)

    print(f"\nDone. rows computed={total:,}  with return_5d={with_r5:,}  "
          f"upserted={'(dry-run)' if args.dry_run else f'{processed:,}'}")
    log.info("backfill_recent_labels.done", start=str(start), end=str(end),
             rows=total, with_r5=with_r5, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
