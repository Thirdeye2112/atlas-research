"""
run_score_variants.py — Compute all 4 experimental score variants from raw features.

Reads feature_snapshots_wide (populated by backfill_wide_table.py),
computes v1/v2/v3/v4 scores for every ticker-date, writes to
experimental_score_snapshots.

Usage
-----
    python scripts/run_score_variants.py
    python scripts/run_score_variants.py --from 2023-01-01
    python scripts/run_score_variants.py --no-db   # dry run
    python scripts/run_score_variants.py --batch 5000  # rows per batch
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
from psycopg2.extras import execute_batch
import pandas as pd

from atlas_research.scoring.experimental import compute_all_scores, SCORE_VERSIONS
from atlas_research.utils.logging import configure_logging, get_logger

configure_logging()
log = get_logger("run_score_variants")

BATCH_SIZE = 5_000


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute experimental score variants")
    parser.add_argument("--from", dest="from_date", default=None,
                        help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", default=None,
                        help="End date YYYY-MM-DD")
    parser.add_argument("--no-db", action="store_true",
                        help="Dry run — don't write to DB")
    parser.add_argument("--batch", type=int, default=BATCH_SIZE,
                        help=f"Rows per batch (default {BATCH_SIZE})")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("[ERROR] DATABASE_URL not set")

    # ── Build query ──────────────────────────────────────────────────────
    conds = []
    params: list = []
    if args.from_date:
        conds.append("date >= %s")
        params.append(datetime.strptime(args.from_date, "%Y-%m-%d").date())
    if args.to_date:
        conds.append("date <= %s")
        params.append(datetime.strptime(args.to_date, "%Y-%m-%d").date())
    where = ("WHERE " + " AND ".join(conds)) if conds else ""

    # Count first
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT COUNT(*) FROM feature_snapshots_wide {where}",
                params or None
            )
            total = cur.fetchone()[0]

    print(f"\nCompute experimental score variants")
    print(f"  Rows in feature_snapshots_wide: {total:,}")
    print(f"  Scores: {SCORE_VERSIONS}")
    print(f"  Write to DB: {'no (--no-db)' if args.no_db else 'yes'}")

    if total == 0:
        print("\n[ERROR] No rows in feature_snapshots_wide.")
        print("  Run: python scripts/backfill_wide_table.py --from 2022-01-01")
        return

    # ── Load and compute in batches ──────────────────────────────────────
    t0 = time.monotonic()
    processed = 0
    n_written  = 0

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM feature_snapshots_wide {where} ORDER BY date, ticker",
                params or None
            )
            colnames = [d[0] for d in cur.description]

            while True:
                batch_rows = cur.fetchmany(args.batch)
                if not batch_rows:
                    break

                df = pd.DataFrame(batch_rows, columns=colnames)
                df_scored = compute_all_scores(df)

                if not args.no_db:
                    records = []
                    for _, row in df_scored.iterrows():
                        records.append((
                            row["ticker"], row["date"],
                            row.get("score_v1_current"),
                            row.get("score_v2_mean_reversion"),
                            row.get("score_v3_hybrid"),
                            row.get("score_v4_tier_adjusted"),
                            row.get("bucket_v1_current"),
                            row.get("bucket_v2_mean_reversion"),
                            row.get("bucket_v3_hybrid"),
                            row.get("bucket_v4_tier_adjusted"),
                        ))

                    with psycopg2.connect(db_url) as wconn:
                        with wconn.cursor() as wcur:
                            execute_batch(wcur, """
                                INSERT INTO experimental_score_snapshots
                                    (ticker, date,
                                     score_v1_current, score_v2_mean_reversion,
                                     score_v3_hybrid, score_v4_tier_adjusted,
                                     bucket_v1, bucket_v2, bucket_v3, bucket_v4)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                ON CONFLICT (ticker, date) DO UPDATE SET
                                    score_v1_current        = EXCLUDED.score_v1_current,
                                    score_v2_mean_reversion = EXCLUDED.score_v2_mean_reversion,
                                    score_v3_hybrid         = EXCLUDED.score_v3_hybrid,
                                    score_v4_tier_adjusted  = EXCLUDED.score_v4_tier_adjusted,
                                    bucket_v1 = EXCLUDED.bucket_v1,
                                    bucket_v2 = EXCLUDED.bucket_v2,
                                    bucket_v3 = EXCLUDED.bucket_v3,
                                    bucket_v4 = EXCLUDED.bucket_v4,
                                    computed_at = now()
                            """, records, page_size=500)
                        wconn.commit()
                    n_written += len(records)

                processed += len(batch_rows)
                elapsed = time.monotonic() - t0
                pct = processed / total * 100
                print(f"  {pct:5.1f}%  {processed:>8,}/{total:,}  {elapsed:.0f}s", end="\r")

    elapsed = time.monotonic() - t0
    print(f"\n  Done: {processed:,} rows scored in {elapsed:.1f}s")
    if not args.no_db:
        print(f"  Written: {n_written:,} rows to experimental_score_snapshots")
    log.info("score_variants.done",
             processed=processed, n_written=n_written, elapsed_s=round(elapsed, 1))


if __name__ == "__main__":
    main()
