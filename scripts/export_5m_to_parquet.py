"""
Export intraday_bars (5-minute OHLCV) to per-ticker parquet files.

Output layout:
    data/intraday_5m/by_ticker/<TICKER>.parquet

Each file: ticker | ts (UTC) | timeframe | open | high | low | close | volume | source
Sorted by ts ascending.

Usage:
    python scripts/export_5m_to_parquet.py              # all tickers
    python scripts/export_5m_to_parquet.py --info       # row counts only, no export
    python scripts/export_5m_to_parquet.py --tickers SPY QQQ AAPL
    python scripts/export_5m_to_parquet.py --timeframe 5m   # default
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

import os
import pandas as pd
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ["DATABASE_URL"]

OUT_DIR = ROOT / "data" / "intraday_5m" / "by_ticker"
SAMPLE_DIR = ROOT / "data" / "samples"


def main():
    parser = argparse.ArgumentParser(description="Export intraday_bars to parquet")
    parser.add_argument("--info", action="store_true", help="Print row counts and exit")
    parser.add_argument("--tickers", nargs="+", help="Subset of tickers to export")
    parser.add_argument("--timeframe", default="5m", help="Timeframe filter (default: 5m)")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Summary stats
        row = conn.execute(text(
            "SELECT COUNT(*) AS n, COUNT(DISTINCT ticker) AS tickers, "
            "MIN(ts) AS earliest, MAX(ts) AS latest "
            "FROM intraday_bars WHERE timeframe = :tf"
        ), {"tf": args.timeframe}).mappings().one()
        print(f"intraday_bars ({args.timeframe}): {row['n']:,} rows, "
              f"{row['tickers']} tickers, "
              f"{row['earliest'].date() if row['earliest'] else 'N/A'} to "
              f"{row['latest'].date() if row['latest'] else 'N/A'}")

        if row["n"] == 0:
            print("No rows found — nothing to export.")
            return

        if args.info:
            # Per-ticker breakdown
            rows = conn.execute(text(
                "SELECT ticker, COUNT(*) AS n, MIN(ts)::date AS first, MAX(ts)::date AS last "
                "FROM intraday_bars WHERE timeframe = :tf "
                "GROUP BY ticker ORDER BY ticker"
            ), {"tf": args.timeframe}).mappings().all()
            print(f"\n{'Ticker':<10} {'Rows':>10} {'First':>12} {'Last':>12}")
            print("-" * 48)
            for r in rows:
                print(f"{r['ticker']:<10} {r['n']:>10,} {str(r['first']):>12} {str(r['last']):>12}")
            return

        # Determine tickers to export
        if args.tickers:
            tickers = args.tickers
        else:
            tickers = [r["ticker"] for r in conn.execute(text(
                "SELECT DISTINCT ticker FROM intraday_bars WHERE timeframe = :tf ORDER BY ticker"
            ), {"tf": args.timeframe}).mappings().all()]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nExporting {len(tickers)} ticker(s) → {OUT_DIR}")

    for i, ticker in enumerate(tickers, 1):
        out_path = OUT_DIR / f"{ticker}.parquet"
        with engine.connect() as conn:
            df = pd.read_sql(
                text(
                    "SELECT ticker, ts, timeframe, open, high, low, close, volume, source "
                    "FROM intraday_bars "
                    "WHERE ticker = :t AND timeframe = :tf "
                    "ORDER BY ts"
                ),
                conn,
                params={"t": ticker, "tf": args.timeframe},
            )
        if df.empty:
            print(f"  [{i}/{len(tickers)}] {ticker} — no data, skipped")
            continue
        df.to_parquet(out_path, index=False, compression="snappy")
        size_kb = out_path.stat().st_size // 1024
        print(f"  [{i}/{len(tickers)}] {ticker} — {len(df):,} rows → {out_path.name} ({size_kb:,} KB)")

    print(f"\nDone. Files in: {OUT_DIR}")
    total_mb = sum(f.stat().st_size for f in OUT_DIR.glob("*.parquet")) / (1024 * 1024)
    print(f"Total size: {total_mb:.1f} MB")


if __name__ == "__main__":
    main()
