#!/usr/bin/env python
"""
backfill_history.py — download full OHLCV history, compute features,
generate labels, and export daily parquet matrices.

This is the cold-start script. Run once after init_db.py.
Nightly runs (run_nightly.py) are incremental from then on.

PERFORMANCE DESIGN
------------------
Features are computed ticker-by-ticker (all dates for one ticker at once),
not date-by-date. This reduces DB round-trips from O(dates × tickers) to
O(tickers), which matters enormously for 15 years × 185 tickers:

  Old approach:  3,750 dates × 185 tickers = 693,750 get_bars() calls
  New approach:  185 tickers × 1 call each = 185 get_bars() calls

After computing all features and writing them to feature_snapshots,
a single parquet export pass reads each date's EAV rows, pivots wide,
and writes a parquet file. One DB read per trading date (~3,750 reads).

TOTAL EXPECTED RUNTIME (185 tickers, 15 years, reasonable hardware)
----------------------------------------------------------------------
  OHLCV download:     30–60 min   (Yahoo Finance rate-limited in batches)
  Feature compute:    10–20 min   (pure numpy, 185 tickers × full history)
  Label compute:      2–5 min
  Parquet export:     5–10 min    (3,750 pivot operations)
  Total:              ~1–1.5 hr

Usage:
    python scripts/backfill_history.py
    python scripts/backfill_history.py --start 2015-01-01 --end 2024-12-31
    python scripts/backfill_history.py --skip-ingest
    python scripts/backfill_history.py --skip-features
    python scripts/backfill_history.py --skip-labels
    python scripts/backfill_history.py --skip-parquet
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from config import settings
from atlas_research.db import repository
from atlas_research.db.connection import check_connection, get_connection
from atlas_research.exports.parquet_export import run_parquet_export
from atlas_research.features.feature_factory import build_features
from atlas_research.ingest.validate import validate_bars, summary as val_summary
from atlas_research.ingest.yahoo_ingest import download_universe
from atlas_research.labels.label_factory import build_labels_for_universe
from atlas_research.utils.logging import configure_logging, get_logger
from sqlalchemy import text

configure_logging(level=settings.LOG_LEVEL, fmt=settings.LOG_FORMAT)
log = get_logger("backfill")


def run_backfill(
    start_date: date,
    end_date: date,
    *,
    skip_ingest: bool = False,
    skip_features: bool = False,
    skip_labels: bool = False,
    skip_parquet: bool = False,
    force_parquet: bool = False,
) -> None:
    if not check_connection():
        log.error("backfill.db_unreachable")
        sys.exit(1)

    tickers = repository.get_active_tickers()
    if not tickers:
        log.error("backfill.no_tickers", hint="Run scripts/init_db.py first")
        sys.exit(1)

    log.info(
        "backfill.start",
        tickers=len(tickers),
        start=str(start_date),
        end=str(end_date),
    )

    # ── Step 1: Ingest OHLCV ─────────────────────────────────
    if not skip_ingest:
        log.info("backfill.ingest_start")
        bars_written, failed = download_universe(
            tickers,
            start_date=start_date,
            end_date=end_date,
            batch_size=settings.DOWNLOAD_BATCH_SIZE,
            batch_delay=settings.DOWNLOAD_BATCH_DELAY_S,
        )
        log.info("backfill.ingest_done",
                 bars=bars_written, failed=len(failed))
        if failed:
            log.warning("backfill.failed_tickers",
                        sample=[t for t, _ in failed[:10]])
    else:
        log.info("backfill.ingest_skipped")

    # ── Step 2: Compute features (ticker-by-ticker) ───────────
    if not skip_features:
        _run_features_ticker_loop(tickers, start_date, end_date)
    else:
        log.info("backfill.features_skipped")

    # ── Step 3: Compute labels ────────────────────────────────
    if not skip_labels:
        log.info("backfill.labels_start")
        total = build_labels_for_universe(tickers, as_of=end_date)
        log.info("backfill.labels_done", rows=total)
    else:
        log.info("backfill.labels_skipped")

    # ── Step 4: Export daily parquet matrices ─────────────────
    if not skip_parquet:
        _run_parquet_export_loop(start_date, end_date, force=force_parquet)
    else:
        log.info("backfill.parquet_skipped")

    log.info("backfill.complete")
    print("\n✓ Backfill complete.")
    print("  Next:")
    print("    python scripts/run_training.py --baseline   # sanity check")
    print("    python scripts/run_training.py              # full walk-forward")


def _run_features_ticker_loop(
    tickers: list[str],
    start_date: date,
    end_date: date,
) -> None:
    """
    Compute features for every ticker across all dates in [start_date, end_date].

    KEY: loads each ticker's full bar history ONCE, then computes features
    for every date in that history. This is O(tickers) DB queries, not
    O(dates × tickers).

    For each date, we slice the bars to [start:snap_date] and compute
    features using the trailing window — point-in-time correct.
    """
    log.info("backfill.features_start", tickers=len(tickers))

    # Load SPY once — reused for all tickers' RS and regime features
    spy_full = repository.get_bars("SPY", start=start_date, end=end_date)

    # Get the set of trading dates we need to cover
    with get_connection() as conn:
        date_rows = conn.execute(text("""
            SELECT DISTINCT date FROM raw_bars
            WHERE date BETWEEN :s AND :e
            ORDER BY date
        """), {"s": start_date, "e": end_date}).fetchall()
    all_dates = [r[0] for r in date_rows]

    log.info("backfill.features_dates", count=len(all_dates))

    total_eav_rows = 0
    snap_ver = f"backfill_{start_date.isoformat()}_{end_date.isoformat()}"

    for ticker_idx, ticker in enumerate(tickers):
        # Load full bar history for this ticker once
        ticker_bars = repository.get_bars(ticker, start=start_date, end=end_date)
        if ticker_bars.empty:
            log.debug("backfill.ticker_no_bars", ticker=ticker)
            continue

        rows_for_ticker = 0
        for snap_date in all_dates:
            try:
                # Point-in-time slice: only bars up to snap_date
                bars_at_date = ticker_bars[
                    ticker_bars["date"].dt.date <= snap_date
                    if hasattr(ticker_bars["date"].iloc[0], "date")
                    else ticker_bars["date"] <= snap_date
                ].tail(300).reset_index(drop=True)

                if bars_at_date.empty:
                    continue

                # Validate before computing
                vr = validate_bars(ticker, bars_at_date, snap_date)
                if not vr.ok:
                    continue

                # SPY slice for RS/regime
                if not spy_full.empty:
                    spy_at_date = spy_full[
                        spy_full["date"].dt.date <= snap_date
                        if hasattr(spy_full["date"].iloc[0], "date")
                        else spy_full["date"] <= snap_date
                    ].tail(300).reset_index(drop=True)
                else:
                    spy_at_date = None

                fv = build_features(ticker, bars_at_date, spy_at_date)
                if fv is None:
                    continue

                n = repository.upsert_features(
                    ticker, snap_date, fv,
                    version=settings.FEATURE_VERSION,
                    snapshot_version=snap_ver,
                )
                rows_for_ticker += n

            except Exception as exc:
                log.warning("backfill.feature_error",
                            ticker=ticker, date=str(snap_date), error=str(exc))

        total_eav_rows += rows_for_ticker

        if (ticker_idx + 1) % 25 == 0:
            log.info("backfill.features_progress",
                     done=ticker_idx + 1, of=len(tickers),
                     eav_rows_so_far=total_eav_rows)

    log.info("backfill.features_done", total_eav_rows=total_eav_rows)


def _run_parquet_export_loop(start_date: date, end_date: date, force: bool = False) -> None:
    """
    Export one parquet file per trading date across the full backfill range.

    Reads from feature_snapshots (EAV) via repository, pivots wide,
    joins labels where available, writes parquet.

    This is the step that makes training data available to run_training.py.
    """
    log.info("backfill.parquet_start",
             start=str(start_date), end=str(end_date))

    with get_connection() as conn:
        date_rows = conn.execute(text("""
            SELECT DISTINCT date FROM feature_snapshots
            WHERE date BETWEEN :s AND :e
            ORDER BY date
        """), {"s": start_date, "e": end_date}).fetchall()
    dates = [r[0] for r in date_rows]

    log.info("backfill.parquet_dates", count=len(dates))
    written = 0
    skipped = 0

    for d in dates:
        # Normalise to date object
        snap_date = d if isinstance(d, date) else d.date() if hasattr(d, "date") else d

        fpath = settings.PARQUET_OUTPUT_DIR / f"feature_matrix_{snap_date.isoformat()}.parquet"
        if fpath.exists() and not force:
            skipped += 1
            continue

        try:
            path = run_parquet_export(
                snap_date,
                feature_version=settings.FEATURE_VERSION,
                feature_names=settings.ALL_FEATURES,
            )
            if path:
                written += 1
        except Exception as exc:
            log.warning("backfill.parquet_error",
                        date=str(snap_date), error=str(exc))

    log.info("backfill.parquet_done",
             written=written, skipped_existing=skipped)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill OHLCV + features + labels + parquet"
    )
    parser.add_argument("--start",          default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--end",            default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--skip-ingest",    action="store_true")
    parser.add_argument("--skip-features",  action="store_true")
    parser.add_argument("--skip-labels",    action="store_true")
    parser.add_argument("--skip-parquet",   action="store_true")
    parser.add_argument("--force-parquet",  action="store_true",
                        help="Overwrite existing parquet files (e.g. after adding features)")
    args = parser.parse_args()

    end_date = (
        datetime.strptime(args.end, "%Y-%m-%d").date()
        if args.end else date.today()
    )
    start_date = (
        datetime.strptime(args.start, "%Y-%m-%d").date()
        if args.start else end_date - timedelta(days=365 * settings.BACKFILL_YEARS)
    )

    run_backfill(
        start_date, end_date,
        skip_ingest=args.skip_ingest,
        skip_features=args.skip_features,
        skip_labels=args.skip_labels,
        skip_parquet=args.skip_parquet,
        force_parquet=args.force_parquet,
    )


if __name__ == "__main__":
    main()
