#!/usr/bin/env python3
"""
compute_sector_rs.py -- Sector Relative Strength vs SPY

For every trading date in raw_bars, computes 5d/20d/60d returns for each
SPDR sector ETF, relative return vs SPY, ranks 1-11, and marks top-3
(leading) and bottom-3 (lagging). Writes to sector_relative_strength table.

Usage:
    python scripts/compute_sector_rs.py
    python scripts/compute_sector_rs.py --start 2020-01-01
    python scripts/compute_sector_rs.py --force   # overwrite existing rows
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

import numpy as np
import pandas as pd
from sqlalchemy import text

from atlas_research.db.connection import get_connection, get_raw_engine
from atlas_research.utils.logging import configure_logging, get_logger
from config import settings

configure_logging(level=settings.LOG_LEVEL, fmt=settings.LOG_FORMAT)
log = get_logger("sector_rs")

SECTOR_TICKERS = ["XLK", "XLF", "XLE", "XLV", "XLI", "XLP", "XLU", "XLY", "XLB", "XLRE", "XLC"]
SECTOR_NAMES = {
    "XLK": "Technology", "XLF": "Financials", "XLE": "Energy",
    "XLV": "Health Care", "XLI": "Industrials", "XLP": "Consumer Staples",
    "XLU": "Utilities", "XLY": "Consumer Discretionary", "XLB": "Materials",
    "XLRE": "Real Estate", "XLC": "Communication Services",
}


def load_closes(tickers: list[str], start_date: date | None = None) -> pd.DataFrame:
    """Load daily close prices for all tickers. Returns wide DataFrame indexed by date."""
    engine = get_raw_engine()
    ticker_list = ", ".join(f"'{t}'" for t in tickers)
    query = f"""
        SELECT date, ticker, close
        FROM raw_bars
        WHERE ticker IN ({ticker_list})
        {f"AND date >= '{start_date}'" if start_date else ""}
        ORDER BY date, ticker
    """
    with engine.connect() as conn:
        df = pd.read_sql(query, conn, parse_dates=["date"])

    if df.empty:
        log.warning("No bar data found for sector tickers.")
        return pd.DataFrame()

    # Pivot to wide: rows=date, cols=ticker
    wide = df.pivot(index="date", columns="ticker", values="close")
    wide.index = pd.to_datetime(wide.index).normalize()
    wide.sort_index(inplace=True)
    return wide


def compute_returns(prices: pd.Series, window: int) -> pd.Series:
    """Rolling N-day return: (price[t] / price[t-N]) - 1"""
    return prices.pct_change(window)


def run_compute(start_date: date | None = None, force: bool = False) -> int:
    all_tickers = SECTOR_TICKERS + ["SPY"]

    log.info("Loading closes for %d tickers...", len(all_tickers))
    wide = load_closes(all_tickers, start_date)
    if wide.empty:
        log.error("No data -- run backfill_history.py first to ingest raw_bars.")
        return 0

    log.info("Loaded %d trading dates, %d tickers.", len(wide), len(wide.columns))

    # Compute returns for all columns
    ret5  = wide.pct_change(5)
    ret20 = wide.pct_change(20)
    ret60 = wide.pct_change(60)

    engine = get_raw_engine()
    rows_written = 0

    # Process date by date (skip dates without SPY data)
    for dt in wide.index:
        if pd.isna(wide.loc[dt, "SPY"] if "SPY" in wide.columns else np.nan):
            continue

        spy_r5  = ret5.loc[dt, "SPY"]  if "SPY" in ret5.columns  else np.nan
        spy_r20 = ret20.loc[dt, "SPY"] if "SPY" in ret20.columns else np.nan
        spy_r60 = ret60.loc[dt, "SPY"] if "SPY" in ret60.columns else np.nan

        sector_rows = []
        for ticker in SECTOR_TICKERS:
            if ticker not in wide.columns:
                continue
            if pd.isna(wide.loc[dt, ticker]):
                continue

            r5  = ret5.loc[dt, ticker]  if ticker in ret5.columns  else np.nan
            r20 = ret20.loc[dt, ticker] if ticker in ret20.columns else np.nan
            r60 = ret60.loc[dt, ticker] if ticker in ret60.columns else np.nan

            rs5  = (r5  - spy_r5)  if not (np.isnan(r5)  or np.isnan(spy_r5))  else None
            rs20 = (r20 - spy_r20) if not (np.isnan(r20) or np.isnan(spy_r20)) else None
            rs60 = (r60 - spy_r60) if not (np.isnan(r60) or np.isnan(spy_r60)) else None

            sector_rows.append({
                "date": dt.date(),
                "sector_ticker": ticker,
                "sector_name": SECTOR_NAMES.get(ticker, ""),
                "return_5d":   None if np.isnan(r5)  else round(float(r5), 6),
                "return_20d":  None if np.isnan(r20) else round(float(r20), 6),
                "return_60d":  None if np.isnan(r60) else round(float(r60), 6),
                "rs_vs_spy_5d":  round(float(rs5), 6)  if rs5  is not None else None,
                "rs_vs_spy_20d": round(float(rs20), 6) if rs20 is not None else None,
                "rs_vs_spy_60d": round(float(rs60), 6) if rs60 is not None else None,
            })

        if not sector_rows:
            continue

        # Rank by rs_vs_spy_20d (handle None: put at end)
        ranked = sorted(sector_rows,
                        key=lambda x: x["rs_vs_spy_20d"] if x["rs_vs_spy_20d"] is not None else -999,
                        reverse=True)
        for i, row in enumerate(ranked):
            row["rank_among_sectors"] = i + 1
            row["is_leading"] = (i + 1) <= 3
            row["is_lagging"] = (i + 1) >= (len(ranked) - 2)

        # Bulk upsert
        with engine.begin() as conn:
            for row in sector_rows:
                if force:
                    conn.execute(text("""
                        INSERT INTO sector_relative_strength
                            (date, sector_ticker, sector_name,
                             return_5d, return_20d, return_60d,
                             rs_vs_spy_5d, rs_vs_spy_20d, rs_vs_spy_60d,
                             rank_among_sectors, is_leading, is_lagging)
                        VALUES
                            (:date, :sector_ticker, :sector_name,
                             :return_5d, :return_20d, :return_60d,
                             :rs_vs_spy_5d, :rs_vs_spy_20d, :rs_vs_spy_60d,
                             :rank_among_sectors, :is_leading, :is_lagging)
                        ON CONFLICT (date, sector_ticker) DO UPDATE SET
                            return_5d        = EXCLUDED.return_5d,
                            return_20d       = EXCLUDED.return_20d,
                            return_60d       = EXCLUDED.return_60d,
                            rs_vs_spy_5d     = EXCLUDED.rs_vs_spy_5d,
                            rs_vs_spy_20d    = EXCLUDED.rs_vs_spy_20d,
                            rs_vs_spy_60d    = EXCLUDED.rs_vs_spy_60d,
                            rank_among_sectors = EXCLUDED.rank_among_sectors,
                            is_leading       = EXCLUDED.is_leading,
                            is_lagging       = EXCLUDED.is_lagging,
                            computed_at      = now()
                    """), row)
                else:
                    conn.execute(text("""
                        INSERT INTO sector_relative_strength
                            (date, sector_ticker, sector_name,
                             return_5d, return_20d, return_60d,
                             rs_vs_spy_5d, rs_vs_spy_20d, rs_vs_spy_60d,
                             rank_among_sectors, is_leading, is_lagging)
                        VALUES
                            (:date, :sector_ticker, :sector_name,
                             :return_5d, :return_20d, :return_60d,
                             :rs_vs_spy_5d, :rs_vs_spy_20d, :rs_vs_spy_60d,
                             :rank_among_sectors, :is_leading, :is_lagging)
                        ON CONFLICT (date, sector_ticker) DO NOTHING
                    """), row)
                rows_written += 1

    log.info("sector_relative_strength: %d rows written.", rows_written)
    return rows_written


def show_latest(n: int = 20):
    with get_connection() as conn:
        rows = conn.execute(text("""
            SELECT date, sector_ticker, rs_vs_spy_20d, rank_among_sectors,
                   is_leading, is_lagging
            FROM sector_relative_strength
            ORDER BY date DESC, rank_among_sectors ASC
            LIMIT :n
        """), {"n": n}).fetchall()

    if not rows:
        print("No rows in sector_relative_strength yet.")
        return

    print(f"\n{'Date':12} {'Ticker':8} {'RS 20d':>10} {'Rank':>6} {'Leading':>8} {'Lagging':>8}")
    print("-" * 58)
    for r in rows:
        rs = f"{r.rs_vs_spy_20d*100:+.2f}%" if r.rs_vs_spy_20d is not None else "   —"
        lead = "  YES" if r.is_leading else ""
        lag  = "  YES" if r.is_lagging else ""
        print(f"{str(r.date):12} {r.sector_ticker:8} {rs:>10} {r.rank_among_sectors:>6} {lead:>8} {lag:>8}")


def main():
    parser = argparse.ArgumentParser(description="Compute sector relative strength vs SPY")
    parser.add_argument("--start", default=None, help="Start date YYYY-MM-DD (default: all history)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing rows (upsert)")
    parser.add_argument("--show-only", action="store_true", help="Only show latest rows, no compute")
    args = parser.parse_args()

    if args.show_only:
        show_latest()
        return

    start = datetime.strptime(args.start, "%Y-%m-%d").date() if args.start else None
    n = run_compute(start_date=start, force=args.force)
    print(f"\nWrote {n} rows to sector_relative_strength.")
    show_latest()


if __name__ == "__main__":
    main()
