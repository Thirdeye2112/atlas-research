#!/usr/bin/env python
"""
scripts/run_probability_tests.py
=================================
Historical base-rate probability engine CLI.

Examples
--------
    # SPY 4-consecutive-down-day study
    python scripts/run_probability_tests.py --ticker SPY --condition down_streak --n 4

    # Up streaks
    python scripts/run_probability_tests.py --ticker SPY --condition up_streak --n 3

    # Gap down study (default threshold 0.5%)
    python scripts/run_probability_tests.py --ticker SPY --condition gap_down

    # Gap down with custom threshold
    python scripts/run_probability_tests.py --ticker QQQ --condition gap_down --threshold 1.0

    # Gap up
    python scripts/run_probability_tests.py --ticker SPY --condition gap_up --threshold 0.5

    # Candlestick patterns
    python scripts/run_probability_tests.py --ticker SPY --condition candle --pattern hammer
    python scripts/run_probability_tests.py --ticker SPY --condition candle --pattern bullish_engulfing
    python scripts/run_probability_tests.py --ticker SPY --condition candle --pattern inside_day

    # Date range filter
    python scripts/run_probability_tests.py --ticker SPY --condition down_streak --n 4 --start 2020-01-01

    # Run all built-in SPY tests (down 2-5, up 2-5, gap down/up)
    python scripts/run_probability_tests.py --run-all

    # List built-in tests
    python scripts/run_probability_tests.py --list

    # Seed DB registry (upsert questions + specs)
    python scripts/run_probability_tests.py --seed

    # Skip DB write
    python scripts/run_probability_tests.py --ticker SPY --condition down_streak --n 4 --no-save
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

from atlas_research.probability import (
    run_backtest,
    seed_registry,
    get_or_create_spec,
    print_report,
    print_comparison,
)
from atlas_research.probability.registry import BUILTIN_SPECS


# ── Param builders ────────────────────────────────────────────────────────────

def _build_params(args: argparse.Namespace, condition_type: str) -> dict:
    if condition_type in ("down_streak", "up_streak"):
        return {"n": args.n if args.n is not None else 3}
    if condition_type in ("gap_up", "gap_down"):
        return {"threshold_pct": args.threshold if args.threshold is not None else 0.5}
    if condition_type == "candle":
        if not args.pattern:
            print("ERROR: --pattern required for --condition candle", file=sys.stderr)
            sys.exit(1)
        return {"pattern": args.pattern}
    return {}


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_run_one(args: argparse.Namespace, save: bool) -> None:
    condition_type = args.condition
    params         = _build_params(args, condition_type)

    spec_id: int | None = None
    if save:
        spec_id = get_or_create_spec(args.ticker, condition_type, params)

    result = run_backtest(
        ticker=args.ticker,
        condition_type=condition_type,
        params=params,
        start_date=args.start,
        end_date=args.end,
        spec_id=spec_id,
        save=save,
    )

    print_report(result)

    if save and result.get("run_id"):
        print(f"  Saved → run_id={result['run_id']}  spec_id={spec_id}")
    elif save:
        print("  (results not saved — no spec_id)")


def cmd_run_all(args: argparse.Namespace, save: bool) -> None:
    if save:
        seed_registry()

    results = []
    for entry in BUILTIN_SPECS:
        ticker         = entry["ticker"]
        condition_type = entry["condition_type"]
        params         = entry["params"]

        spec_id: int | None = None
        if save:
            spec_id = get_or_create_spec(ticker, condition_type, params)

        result = run_backtest(
            ticker=ticker,
            condition_type=condition_type,
            params=params,
            spec_id=spec_id,
            save=save,
        )
        print_report(result)
        results.append(result)

    print_comparison(results)


def cmd_list() -> None:
    print()
    print("  Built-in tests:")
    print("  " + "-" * 52)
    for i, entry in enumerate(BUILTIN_SPECS, 1):
        pstr = "  ".join(f"{k}={v}" for k, v in entry["params"].items())
        print(f"  {i:>2}. {entry['ticker']:<6}  {entry['condition_type']:<15}  {pstr}")
    print()


def cmd_seed() -> None:
    q_ids = seed_registry()
    print(f"  Seeded {len(q_ids)} question(s) and {len(BUILTIN_SPECS)} spec(s).")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/run_probability_tests.py",
        description="Atlas probability engine — historical base-rate analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--ticker",     default="SPY",
                        help="Ticker symbol (default: SPY)")
    parser.add_argument("--condition",
                        help="Condition: down_streak, up_streak, gap_up, gap_down, candle")
    parser.add_argument("--n",          type=int,
                        help="Streak length for down_streak / up_streak")
    parser.add_argument("--threshold",  type=float,
                        help="Gap threshold %% for gap_up / gap_down (default 0.5)")
    parser.add_argument("--pattern",
                        help="Candle pattern name for --condition candle")
    parser.add_argument("--start",
                        help="Data start date YYYY-MM-DD")
    parser.add_argument("--end",
                        help="Data end date YYYY-MM-DD")
    parser.add_argument("--run-all",    action="store_true",
                        help="Run all built-in tests")
    parser.add_argument("--list",       action="store_true",
                        help="List built-in tests")
    parser.add_argument("--seed",       action="store_true",
                        help="Seed registry tables in DB and exit")
    parser.add_argument("--no-save",    action="store_true",
                        help="Skip saving results to DB")

    args = parser.parse_args()
    save = not args.no_save

    if args.list:
        cmd_list()
        return 0

    if args.seed:
        cmd_seed()
        return 0

    if args.run_all:
        cmd_run_all(args, save=save)
        return 0

    if not args.condition:
        parser.print_help()
        return 2

    cmd_run_one(args, save=save)
    return 0


if __name__ == "__main__":
    sys.exit(main())
