"""
Run Atlas Confluence Engine for a given date.

Usage:
    python scripts/run_confluence.py                      # today's parquet
    python scripts/run_confluence.py --date 2026-06-14   # specific date
    python scripts/run_confluence.py --ticker AAPL MSFT  # subset
    python scripts/run_confluence.py --top 20            # print top N
    python scripts/run_confluence.py --direction bullish  # filter output

Output:
    Scores are written to confluence_score_snapshots + confluence_score_components.
    Top results are printed to stdout.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from atlas_research.confluence.engine import run_confluence
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)


def main() -> int:
    ap = argparse.ArgumentParser(description="Atlas Confluence Engine")
    ap.add_argument("--date",      default=None, help="YYYY-MM-DD (default: today)")
    ap.add_argument("--parquet",   default=None, help="Path to parquet directory")
    ap.add_argument("--ticker",    nargs="+",    help="Restrict to these tickers")
    ap.add_argument("--top",       type=int, default=25, help="Print top N results")
    ap.add_argument("--direction", choices=["bullish", "bearish", "neutral"],
                    default=None, help="Filter printed output by direction")
    args = ap.parse_args()

    snap_date = (
        datetime.strptime(args.date, "%Y-%m-%d").date()
        if args.date else date.today()
    )

    import os
    parquet_dir = Path(
        args.parquet or os.environ.get("PARQUET_DIR", "data/features")
    )

    print(f"\nAtlas Confluence Engine v1")
    print(f"Date       : {snap_date}")
    print(f"Parquet    : {parquet_dir}")
    print(f"Tickers    : {args.ticker or 'all'}")
    print("-" * 50)

    results = run_confluence(
        snap_date=snap_date,
        parquet_dir=parquet_dir,
        tickers=args.ticker,
    )

    if results.empty:
        print("No results — check parquet path or date.")
        return 1

    display = results.copy()
    if args.direction:
        display = display[display["confluence_direction"] == args.direction]

    display = display.head(args.top)

    print(f"\nTop {len(display)} results:")
    print(f"{'Ticker':<8}  {'Score':>6}  {'Direction':<9}  {'Aligned':>7}  {'Conflict':>8}")
    print("-" * 50)
    for _, r in display.iterrows():
        print(
            f"{r['ticker']:<8}  {r['confluence_score']:>6.1f}  "
            f"{r['confluence_direction']:<9}  {r['aligned_signals']:>7}  "
            f"{r['conflicting_signals']:>8}"
        )

    print(f"\nTotal scored: {len(results)}")
    print(f"Bullish: {(results['confluence_direction']=='bullish').sum()}")
    print(f"Bearish: {(results['confluence_direction']=='bearish').sum()}")
    print(f"Neutral: {(results['confluence_direction']=='neutral').sum()}")
    print(f"Mean score: {results['confluence_score'].mean():.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
