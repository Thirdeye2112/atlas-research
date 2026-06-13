#!/usr/bin/env python
"""
scripts/run_ipo_tests.py
=========================
IPO outcome engine CLI.

Examples
--------
    # Build events + run all studies (full pipeline)
    python scripts/run_ipo_tests.py --all

    # Show one IPO's event summary
    python scripts/run_ipo_tests.py --ticker CRCL
    python scripts/run_ipo_tests.py --ticker BNTX

    # Only build ipo_events (skip study aggregation)
    python scripts/run_ipo_tests.py --build

    # Only run studies (assumes ipo_events already built)
    python scripts/run_ipo_tests.py --studies

    # Skip DB write
    python scripts/run_ipo_tests.py --all --no-save

    # Show which buckets a ticker would fall into
    python scripts/run_ipo_tests.py --ticker RIVN

Probability questions answered
-------------------------------
    --all prints:
      1. What % of IPOs revisit opening price?
      2. What % revisit offer price?
      3. How many close Day 1 within 20% of opening?
      4. After a +X% Day-1 expansion, what % revisit open?
      5. After Week 1 gain >20%, what is median future drawdown?
      6. After Month 1 momentum, what is eventual retracement?
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from atlas_research.probability.ipo import (
    build_all_events,
    get_event,
    load_all_events,
    run_all_studies,
    print_event_summary,
    print_all_studies,
)


def cmd_all(save: bool) -> None:
    print("\n[1/2] Building ipo_events...")
    n = build_all_events(verbose=True)
    print(f"  Done — {n} events computed.")

    print("\n[2/2] Running studies...")
    events = load_all_events()
    results = run_all_studies(events, save=save)
    print(f"  Done — {sum(len(v) for v in results.values())} study rows computed.")

    print()
    print_all_studies(results)

    if save:
        print("  Results saved to ipo_outcomes table.")


def cmd_build(save: bool) -> None:
    print("Building ipo_events...")
    n = build_all_events(verbose=True)
    print(f"Done — {n} events computed.")
    if not save:
        print("  (--no-save: DB not updated)")


def cmd_studies(save: bool) -> None:
    events = load_all_events()
    if not events:
        print("ERROR: no rows in ipo_events — run --build first", file=sys.stderr)
        sys.exit(1)
    print(f"Running studies on {len(events)} events...")
    results = run_all_studies(events, save=save)
    print_all_studies(results)
    if save:
        print("  Results saved to ipo_outcomes table.")


def cmd_ticker(ticker: str) -> None:
    ev = get_event(ticker)
    if ev is None:
        print(f"\n  {ticker} not found in ipo_events.")
        print("  Run --build first, or check if ticker is in ipo_registry.")
        sys.exit(1)
    print_event_summary(ev)

    # Also show which study buckets this ticker falls into
    print("  Study buckets:")
    print(f"    open_vs_offer:  {ev.get('bucket_open_vs_offer', 'N/A')}  "
          f"({ev.get('open_vs_offer', 'N/A')}%)")
    print(f"    peak_vs_open:   {ev.get('bucket_peak_vs_open', 'N/A')}  "
          f"({ev.get('peak_vs_open', 'N/A')}%)")
    print(f"    retracement:    {ev.get('bucket_retracement', 'N/A')}  "
          f"({ev.get('retracement_from_peak', 'N/A')}%)")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/run_ipo_tests.py",
        description="Atlas IPO outcome engine — Phase 4C",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--all",      action="store_true",
                        help="Build events + run all studies + print reports")
    parser.add_argument("--build",    action="store_true",
                        help="Build ipo_events from raw_bars + ipo_registry")
    parser.add_argument("--studies",  action="store_true",
                        help="Run aggregate studies (requires ipo_events already built)")
    parser.add_argument("--ticker",   metavar="TICKER",
                        help="Print event summary for one IPO ticker")
    parser.add_argument("--no-save",  action="store_true",
                        help="Compute but do not write results to DB")

    args = parser.parse_args()
    save = not args.no_save

    if args.ticker:
        cmd_ticker(args.ticker.upper())
        return 0

    if args.all:
        cmd_all(save=save)
        return 0

    if args.build:
        cmd_build(save=save)
        return 0

    if args.studies:
        cmd_studies(save=save)
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
