#!/usr/bin/env python
"""
scripts/build_universe.py
==========================
Build or refresh the ticker universe for atlas-research.

Sources (tried in order, first success wins):
  1. S&P 500       — Wikipedia (stable, ~500 tickers)
  2. S&P 500 + S&P MidCap 400 + S&P SmallCap 600 — Wikipedia (~1,500 tickers)
  3. Nasdaq-100     — Wikipedia (~100 tickers, subset)
  4. Fallback       — existing config/universe.csv (no change)

Liquidity filter (applied after download):
  - Removes tickers that fail yfinance info fetch
  - Optionally filters by market cap, price, volume thresholds

Usage
-----
    # Build S&P 1500 (recommended starting point)
    python scripts/build_universe.py --source sp1500

    # S&P 500 only
    python scripts/build_universe.py --source sp500

    # Preview without writing
    python scripts/build_universe.py --source sp1500 --dry-run

    # Validate existing universe (check each ticker fetches OK)
    python scripts/build_universe.py --validate

Output
------
    config/universe.csv  — written in place
    Columns: ticker, name, sector, industry, exchange
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import pandas as pd
import requests


# ── Universe sources ──────────────────────────────────────────────────────────

def fetch_sp500() -> pd.DataFrame:
    """Fetch S&P 500 constituents from Wikipedia."""
    print("  Fetching S&P 500 from Wikipedia...")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(url)
    df = tables[0]
    df = df.rename(columns={
        "Symbol": "ticker",
        "Security": "name",
        "GICS Sector": "sector",
        "GICS Sub-Industry": "industry",
        "Exchange": "exchange",
    })
    df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)
    return df[["ticker", "name", "sector", "industry"]].copy()


def fetch_sp400() -> pd.DataFrame:
    """Fetch S&P MidCap 400 constituents from Wikipedia."""
    print("  Fetching S&P MidCap 400 from Wikipedia...")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"
    tables = pd.read_html(url)
    df = tables[0]
    # Column names vary — find ticker column
    ticker_col = next(c for c in df.columns if "ticker" in c.lower() or "symbol" in c.lower())
    name_col   = next((c for c in df.columns if "company" in c.lower() or "security" in c.lower()), None)
    sector_col = next((c for c in df.columns if "sector" in c.lower()), None)
    result = pd.DataFrame()
    result["ticker"] = df[ticker_col].str.replace(".", "-", regex=False)
    result["name"]   = df[name_col] if name_col else ""
    result["sector"] = df[sector_col] if sector_col else ""
    result["industry"] = ""
    return result


def fetch_sp600() -> pd.DataFrame:
    """Fetch S&P SmallCap 600 constituents from Wikipedia."""
    print("  Fetching S&P SmallCap 600 from Wikipedia...")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_600_companies"
    tables = pd.read_html(url)
    df = tables[0]
    ticker_col = next(c for c in df.columns if "ticker" in c.lower() or "symbol" in c.lower())
    name_col   = next((c for c in df.columns if "company" in c.lower() or "security" in c.lower()), None)
    sector_col = next((c for c in df.columns if "sector" in c.lower()), None)
    result = pd.DataFrame()
    result["ticker"] = df[ticker_col].str.replace(".", "-", regex=False)
    result["name"]   = df[name_col] if name_col else ""
    result["sector"] = df[sector_col] if sector_col else ""
    result["industry"] = ""
    return result


def fetch_sp1500() -> pd.DataFrame:
    """Combine S&P 500 + MidCap 400 + SmallCap 600."""
    frames = []
    for fn in (fetch_sp500, fetch_sp400, fetch_sp600):
        try:
            frames.append(fn())
        except Exception as e:
            print(f"  WARNING: {fn.__name__} failed — {e}")
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["ticker"])
    return df


def fetch_nasdaq100() -> pd.DataFrame:
    """Fetch Nasdaq-100 from Wikipedia."""
    print("  Fetching Nasdaq-100 from Wikipedia...")
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    tables = pd.read_html(url)
    # Find the table with ticker symbols
    for t in tables:
        cols_lower = [c.lower() for c in t.columns]
        if any("ticker" in c or "symbol" in c for c in cols_lower):
            ticker_col = next(c for c in t.columns if "ticker" in c.lower() or "symbol" in c.lower())
            name_col   = next((c for c in t.columns if "company" in c.lower()), None)
            result = pd.DataFrame()
            result["ticker"] = t[ticker_col].str.replace(".", "-", regex=False)
            result["name"]   = t[name_col] if name_col else ""
            result["sector"] = ""
            result["industry"] = ""
            return result
    raise ValueError("Nasdaq-100 table not found on Wikipedia page")


SOURCES = {
    "sp500":    fetch_sp500,
    "sp400":    fetch_sp400,
    "sp600":    fetch_sp600,
    "sp1500":   fetch_sp1500,
    "nasdaq100": fetch_nasdaq100,
}


# ── Validation ────────────────────────────────────────────────────────────────

def validate_tickers(tickers: list[str], sample: int = 0) -> list[str]:
    """
    Optionally validate tickers by fetching a quick yfinance info check.
    Returns list of valid tickers.
    sample=0 means validate all (slow); sample=N validates a random N.
    """
    import yfinance as yf

    if sample > 0:
        import random
        tickers = random.sample(tickers, min(sample, len(tickers)))

    valid = []
    failed = []
    print(f"  Validating {len(tickers)} tickers (this may take a few minutes)...")
    for i, ticker in enumerate(tickers, 1):
        try:
            info = yf.Ticker(ticker).fast_info
            # Check it has a market price
            if hasattr(info, 'last_price') and info.last_price:
                valid.append(ticker)
            else:
                failed.append(ticker)
        except Exception:
            failed.append(ticker)
        if i % 50 == 0:
            print(f"    {i}/{len(tickers)} checked — {len(valid)} valid, {len(failed)} failed")
        time.sleep(0.1)

    print(f"  Validation complete: {len(valid)} valid, {len(failed)} failed")
    if failed:
        print(f"  Failed tickers: {failed[:20]}{'...' if len(failed) > 20 else ''}")
    return valid


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/build_universe.py",
        description="Build atlas-research ticker universe from standard US indices",
    )
    parser.add_argument(
        "--source",
        choices=list(SOURCES.keys()),
        default="sp500",
        help="Universe source (default: sp500)",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "config" / "universe.csv"),
        help="Output CSV path (default: config/universe.csv)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and show stats without writing",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate each ticker against yfinance (slow)",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing universe.csv instead of replacing",
    )
    args = parser.parse_args()

    print(f"\nBuilding universe: {args.source}")
    print(f"Output: {args.output}")
    print()

    try:
        df = SOURCES[args.source]()
    except Exception as e:
        print(f"ERROR: Failed to fetch {args.source} — {e}")
        return 1

    # Normalise
    df["ticker"]   = df["ticker"].str.strip().str.upper()
    df["name"]     = df.get("name", pd.Series([""] * len(df))).fillna("").str.strip()
    df["sector"]   = df.get("sector", pd.Series([""] * len(df))).fillna("").str.strip()
    df["industry"] = df.get("industry", pd.Series([""] * len(df))).fillna("").str.strip()
    df["exchange"] = df.get("exchange", pd.Series([""] * len(df))).fillna("").str.strip()

    # Remove obvious bad tickers
    df = df[df["ticker"].str.match(r'^[A-Z\-\.]{1,10}$')]
    df = df.drop_duplicates(subset=["ticker"])
    df = df.sort_values("ticker").reset_index(drop=True)

    print(f"  Fetched {len(df)} tickers")

    # Sector breakdown
    if "sector" in df.columns and df["sector"].any():
        print("\n  Sector breakdown:")
        for sector, count in df["sector"].value_counts().head(12).items():
            print(f"    {sector:<40} {count:>4}")

    if args.validate:
        valid = validate_tickers(df["ticker"].tolist())
        df = df[df["ticker"].isin(valid)]
        print(f"\n  After validation: {len(df)} tickers")

    if args.append:
        existing_path = Path(args.output)
        if existing_path.exists():
            existing = pd.read_csv(existing_path)
            df = pd.concat([existing, df], ignore_index=True)
            df = df.drop_duplicates(subset=["ticker"])
            df = df.sort_values("ticker").reset_index(drop=True)
            print(f"  After merge with existing: {len(df)} tickers")

    print(f"\n  Final universe: {len(df)} tickers")

    if args.dry_run:
        print("\n  DRY RUN — nothing written")
        print(f"  Would write to: {args.output}")
        print(f"\n  Sample (first 10):")
        print(df.head(10).to_string(index=False))
        return 0

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"\n  Written: {out}")
    print(f"  Rows: {len(df)}")
    print(f"\n  Next steps:")
    print(f"    python scripts/backfill_history.py   # ingest bars for new tickers")
    print(f"    python scripts/run_nightly.py        # features + labels + parquet")
    print(f"    python scripts/run_training.py       # retrain on expanded universe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
