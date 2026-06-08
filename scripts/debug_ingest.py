#!/usr/bin/env python
"""
debug_ingest.py — standalone ingest diagnostic.

Run this before backfill to confirm the full write path works end-to-end
for a single ticker. Prints every intermediate state so the failure point
is unambiguous.

Usage:
    python scripts/debug_ingest.py
    python scripts/debug_ingest.py --ticker MSFT --days 10
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
import yfinance as yf

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="AAPL")
    parser.add_argument("--days",   type=int, default=30)
    args = parser.parse_args()

    ticker = args.ticker.upper()
    end   = date.today()
    start = end - timedelta(days=args.days)

    print(f"\n{'='*60}")
    print(f"  debug_ingest.py — {ticker}  {start} → {end}")
    print(f"{'='*60}\n")

    # ── Step 1: raw yfinance download ─────────────────────────
    print("STEP 1: raw yfinance.download (single ticker)")
    df_single = yf.download(
        ticker, start=str(start), end=str(end + timedelta(days=1)),
        auto_adjust=False, progress=False, actions=False,
    )
    print(f"  shape:       {df_single.shape}")
    print(f"  col type:    {type(df_single.columns).__name__}")
    print(f"  columns:     {list(df_single.columns)}")
    if not df_single.empty:
        print(f"  first row:   {dict(df_single.iloc[0])}")
        print(f"  index type:  {type(df_single.index[0])}")

    # ── Step 2: batch download (group_by='ticker') ─────────────
    print(f"\nSTEP 2: yfinance.download with group_by='ticker' (batch mode)")
    df_batch = yf.download(
        [ticker, "SPY"], start=str(start), end=str(end + timedelta(days=1)),
        auto_adjust=False, progress=False, actions=False,
        group_by="ticker", threads=False,
    )
    print(f"  shape:          {df_batch.shape}")
    print(f"  col type:       {type(df_batch.columns).__name__}")
    if isinstance(df_batch.columns, pd.MultiIndex):
        print(f"  level names:    {df_batch.columns.names}")
        print(f"  level 0 vals:   {sorted(set(df_batch.columns.get_level_values(0)))}")
        print(f"  level 1 vals:   {sorted(set(df_batch.columns.get_level_values(1)))}")
    else:
        print(f"  columns:        {list(df_batch.columns)}")

    # ── Step 3: probe xs extraction ───────────────────────────
    print(f"\nSTEP 3: xs() extraction for {ticker}")
    if isinstance(df_batch.columns, pd.MultiIndex):
        for level in (0, 1):
            try:
                candidate = df_batch.xs(ticker, axis=1, level=level)
                print(f"  xs(level={level}) SUCCESS  shape={candidate.shape}  cols={list(candidate.columns)}")
                if not candidate.empty:
                    if isinstance(candidate.columns, pd.MultiIndex):
                        candidate.columns = candidate.columns.get_level_values(0)
                    candidate.columns = [str(c).lower() for c in candidate.columns]
                    print(f"  after lower:    {list(candidate.columns)}")
                    print(f"  first row:      {dict(candidate.iloc[0])}")
            except KeyError as e:
                print(f"  xs(level={level}) FAILED:  {e}")
    else:
        print(f"  flat columns — no xs() needed")
        df_batch.columns = [str(c).lower() for c in df_batch.columns]
        print(f"  after lower: {list(df_batch.columns)}")

    # ── Step 4: _extract_ticker_rows ──────────────────────────
    print(f"\nSTEP 4: _extract_ticker_rows({ticker})")
    from atlas_research.ingest.yahoo_ingest import _extract_ticker_rows
    rows = _extract_ticker_rows(ticker, df_batch)
    print(f"  rows extracted: {len(rows)}")
    if rows:
        print(f"  first row:      {rows[0]}")
        print(f"  last row:       {rows[-1]}")
        missing_adj = sum(1 for r in rows if r['adjusted_close'] is None)
        if missing_adj:
            print(f"  WARNING: {missing_adj}/{len(rows)} rows have adjusted_close=None")
    else:
        print("  *** ZERO ROWS — extraction failed ***")
        print("  Trying single-ticker df as fallback:")
        rows2 = _extract_ticker_rows(ticker, df_single)
        print(f"  rows from single-ticker df: {len(rows2)}")
        if rows2:
            print(f"  first row: {rows2[0]}")

    # ── Step 5: DB connectivity ───────────────────────────────
    print(f"\nSTEP 5: DB connection + upsert_bars")
    try:
        from atlas_research.db.connection import check_connection, get_connection
        from atlas_research.db.repository import upsert_bars
        from sqlalchemy import text

        if not check_connection():
            print("  *** DB UNREACHABLE — check DATABASE_URL_RESEARCH ***")
            return

        print("  DB: connected")

        if rows:
            test_row = [rows[0]]
            n = upsert_bars(test_row)
            print(f"  upsert_bars([1 row]) returned: {n}")

            with get_connection() as conn:
                result = conn.execute(
                    text("SELECT COUNT(*) FROM raw_bars WHERE ticker = :t"),
                    {"t": ticker}
                ).scalar()
            print(f"  raw_bars count for {ticker}: {result}")

            if result == 0:
                print("  *** INSERT RETURNED NO ERROR BUT ROW NOT IN TABLE ***")
                print("  Check: transaction commit, table name, schema search_path")
            else:
                print(f"  SUCCESS: {result} rows in raw_bars for {ticker}")

            n2 = upsert_bars(rows)
            with get_connection() as conn:
                total = conn.execute(
                    text("SELECT COUNT(*) FROM raw_bars WHERE ticker = :t"),
                    {"t": ticker}
                ).scalar()
            print(f"  After full upsert: {total} rows in raw_bars for {ticker}")

        else:
            print("  Skipping upsert (no rows extracted)")

    except Exception as exc:
        import traceback
        print(f"  *** DB ERROR: {exc} ***")
        traceback.print_exc()

    print(f"\n{'='*60}")
    print("  Diagnostic complete.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()