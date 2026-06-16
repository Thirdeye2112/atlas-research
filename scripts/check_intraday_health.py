"""
Atlas Intraday Learning Engine -- Health Check
==============================================
Reports data coverage, setup counts, candidate status, and data gaps.

Usage:
    python scripts/check_intraday_health.py
    python scripts/check_intraday_health.py --verbose
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]

# Thresholds for "enough data" status
BARS_PER_DAY_PER_TICKER = 77   # ~77 5-min bars in 6.5h trading day
MIN_DAYS_FOR_CANDIDATE  = 30
MIN_DAYS_FOR_PROMOTION  = 90
STALE_TICKER_DAYS       = 3    # flag ticker if no bars in last N calendar days


def _q(engine, sql: str, **params) -> list[dict]:
    with engine.connect() as conn:
        result = conn.execute(text(sql), params)
        cols   = list(result.keys())
        return [dict(zip(cols, row)) for row in result.fetchall()]


def check_bars(engine) -> dict:
    rows = _q(engine, """
        SELECT
            ticker,
            COUNT(*)                   AS bar_count,
            MIN(ts)                    AS earliest_ts,
            MAX(ts)                    AS latest_ts,
            COUNT(DISTINCT ts::date)   AS trading_days
        FROM intraday_bars
        WHERE timeframe = '5m'
        GROUP BY ticker
        ORDER BY ticker
    """)

    total_bars    = sum(r["bar_count"] for r in rows)
    tickers       = [r["ticker"] for r in rows]
    now           = datetime.now(timezone.utc)
    stale         = []
    missing_today = []

    for r in rows:
        latest = r["latest_ts"]
        if latest is not None:
            if hasattr(latest, "tzinfo") and latest.tzinfo is None:
                import pytz
                latest = pytz.utc.localize(latest)
            age_days = (now - latest).days
            if age_days >= STALE_TICKER_DAYS:
                stale.append(r["ticker"])
            # Check if we have bars from today or yesterday (market may be closed)
            latest_date = latest.date() if hasattr(latest, "date") else latest
            if (date.today() - latest_date).days > 1:
                missing_today.append(r["ticker"])

    return {
        "tickers":     tickers,
        "ticker_count": len(tickers),
        "total_bars":  total_bars,
        "stale":       stale,
        "missing_recent": missing_today,
        "per_ticker":  rows,
    }


def check_setups(engine) -> dict:
    rows = _q(engine, """
        SELECT
            setup_type,
            direction,
            COUNT(*)     AS setup_count,
            MIN(ts)      AS earliest_ts,
            MAX(ts)      AS latest_ts
        FROM intraday_setups
        GROUP BY setup_type, direction
        ORDER BY setup_count DESC
    """)

    total_setups = _q(engine, "SELECT COUNT(*) AS n FROM intraday_setups")[0]["n"]
    total_types  = len(rows)

    tickers_with_ctx = _q(engine, """
        SELECT COUNT(DISTINCT ticker) AS n
        FROM intraday_setups
        WHERE daily_conviction IS NOT NULL
    """)[0]["n"]

    return {
        "total_setups":    total_setups,
        "setup_types":     total_types,
        "with_daily_ctx":  tickers_with_ctx,
        "by_type":         rows,
    }


def check_outcomes(engine) -> dict:
    total = _q(engine, "SELECT COUNT(*) AS n FROM intraday_outcomes")[0]["n"]
    horizon_counts = _q(engine, """
        SELECT horizon_bars, COUNT(*) AS n
        FROM intraday_outcomes
        GROUP BY horizon_bars
        ORDER BY horizon_bars
    """)
    return {
        "total_outcomes": total,
        "by_horizon":     horizon_counts,
    }


def check_candidates(engine) -> dict:
    try:
        latest_date = _q(engine, """
            SELECT MAX(as_of_date) AS latest_date FROM intraday_candidate_setups
        """)[0].get("latest_date")

        if latest_date is None:
            return {"available": False}

        by_status = _q(engine, """
            SELECT status, COUNT(*) AS n
            FROM intraday_candidate_setups
            WHERE as_of_date = (SELECT MAX(as_of_date) FROM intraday_candidate_setups)
            GROUP BY status
            ORDER BY status
        """)

        top_candidates = _q(engine, """
            SELECT setup_type, direction, sample_size, win_rate, expectancy,
                   profit_factor, oos_sample_size, oos_win_rate, oos_expectancy,
                   oos_profit_factor, best_context_label, best_context_exp,
                   days_collected, status, notes
            FROM intraday_candidate_setups
            WHERE as_of_date = (SELECT MAX(as_of_date) FROM intraday_candidate_setups)
              AND status IN ('candidate', 'promoted')
            ORDER BY oos_expectancy DESC NULLS LAST
            LIMIT 10
        """)

        return {
            "available":      True,
            "as_of":          str(latest_date),
            "by_status":      by_status,
            "top_candidates": top_candidates,
        }
    except Exception as e:
        return {"available": False, "error": str(e)}


def check_promoted(engine) -> dict:
    try:
        rows = _q(engine, """
            SELECT setup_type, direction, walk_forward_passed, promoted, scored_date
            FROM intraday_promoted_setups
            ORDER BY scored_date DESC
            LIMIT 50
        """)
        n_promoted = sum(1 for r in rows if r.get("promoted"))
        return {"rows": rows, "promoted_count": n_promoted}
    except Exception:
        return {"rows": [], "promoted_count": 0}


def estimate_days_to_promotion(bars_info: dict) -> dict:
    """Estimate how many more trading days are needed for first promotion eligibility."""
    if not bars_info["per_ticker"]:
        return {"days_collected": 0, "days_needed": MIN_DAYS_FOR_PROMOTION, "pct": 0}

    avg_days = sum(r["trading_days"] for r in bars_info["per_ticker"]) / len(bars_info["per_ticker"])
    days_needed = max(0, MIN_DAYS_FOR_PROMOTION - avg_days)
    pct = min(100, avg_days / MIN_DAYS_FOR_PROMOTION * 100)
    return {
        "days_collected": int(avg_days),
        "days_needed":    int(days_needed),
        "pct":            round(pct, 1),
        "est_ready_date": str(date.today() + timedelta(days=int(days_needed * 1.4))),  # ~1.4 calendar:trading ratio
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    engine = create_engine(DATABASE_URL)

    print("=== Atlas Intraday Learning Engine -- Health Check ===")
    print(f"As-of: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

    # Bars
    print("[1/5] Bar coverage...")
    bars = check_bars(engine)
    print(f"  Tickers tracked:   {bars['ticker_count']}")
    print(f"  Total 5-min bars:  {bars['total_bars']:,}")
    if bars["per_ticker"]:
        earliest = min(r["earliest_ts"] for r in bars["per_ticker"] if r["earliest_ts"])
        latest   = max(r["latest_ts"]   for r in bars["per_ticker"] if r["latest_ts"])
        print(f"  Date range:        {earliest} -> {latest}")
    if bars["stale"]:
        print(f"  STALE tickers (no data in {STALE_TICKER_DAYS}+ days): {bars['stale']}")
    if bars["missing_recent"]:
        print(f"  Missing recent bars: {bars['missing_recent']}")
    else:
        print(f"  All tickers have recent data")

    if args.verbose and bars["per_ticker"]:
        print()
        print(f"  {'Ticker':<8} {'Bars':>7} {'Trading Days':>13} {'Latest':>20}")
        for r in sorted(bars["per_ticker"], key=lambda x: x["ticker"]):
            print(f"  {r['ticker']:<8} {r['bar_count']:>7,} {r['trading_days']:>13} "
                  f"  {str(r['latest_ts'])[:19]:>20}")

    # Setups
    print()
    print("[2/5] Setup detection...")
    setups = check_setups(engine)
    print(f"  Total setups:      {setups['total_setups']:,}")
    print(f"  Setup types:       {setups['setup_types']}")
    print(f"  With daily ctx:    {setups['with_daily_ctx']} tickers")

    if args.verbose and setups["by_type"]:
        print()
        print(f"  {'Setup Type':<28} {'Dir':<6} {'Count':>7} {'Oldest':>12} {'Latest':>12}")
        for r in setups["by_type"]:
            oldest = str(r["earliest_ts"])[:10] if r["earliest_ts"] else "n/a"
            newest = str(r["latest_ts"])[:10]   if r["latest_ts"]   else "n/a"
            print(f"  {r['setup_type']:<28} {r['direction']:<6} "
                  f"{r['setup_count']:>7,} {oldest:>12} {newest:>12}")

    # Outcomes
    print()
    print("[3/5] Outcomes...")
    outcomes = check_outcomes(engine)
    print(f"  Total outcomes:    {outcomes['total_outcomes']:,}")
    for h in outcomes["by_horizon"]:
        mins = h["horizon_bars"] * 5
        print(f"  Horizon {h['horizon_bars']:>2} bars ({mins:>3}m): {h['n']:,}")

    # Candidates
    print()
    print("[4/5] Candidate watchlist...")
    cands = check_candidates(engine)
    if not cands.get("available"):
        print("  Not yet available -- run update_intraday_candidates.py first")
    else:
        print(f"  As-of: {cands['as_of']}")
        for row in cands["by_status"]:
            print(f"  {row['status'].upper():<12} {row['n']:>3} setups")
        if cands["top_candidates"]:
            print()
            print("  Top candidates (candidate/promoted by OOS expectancy):")
            print(f"  {'Setup':<28} {'Dir':<6} {'IS Exp':>7} {'OOS Exp':>8} {'OOS PF':>7} {'n':>5} {'Status':<12} Best Context")
            for r in cands["top_candidates"]:
                ctx = r.get("best_context_label") or ""
                ctx_exp = r.get("best_context_exp")
                ctx_str = f"{ctx} ({ctx_exp:+.2f}%)" if ctx and ctx_exp is not None else ""
                print(f"  {r['setup_type']:<28} {r['direction']:<6} "
                      f"{r.get('expectancy', 0):>+7.3f}% "
                      f"{r.get('oos_expectancy', 0):>+8.3f}% "
                      f"{r.get('oos_profit_factor', 0):>7.2f} "
                      f"{r.get('sample_size', 0):>5} "
                      f"{r['status']:<12} {ctx_str}")

    # Promoted
    print()
    print("[5/5] Promoted setups...")
    promoted = check_promoted(engine)
    if promoted["promoted_count"] == 0:
        print("  No promoted setups yet -- still collecting data")
    else:
        print(f"  PROMOTED: {promoted['promoted_count']} setup(s)")
        for r in [x for x in promoted["rows"] if x.get("promoted")]:
            print(f"    {r['setup_type']} ({r['direction']}) as of {r['scored_date']}")

    # Progress estimate
    print()
    est = estimate_days_to_promotion(bars)
    print("=== Collection Progress ===")
    bar_chars = int(est["pct"] / 5)
    bar_str   = "#" * bar_chars + "-" * (20 - bar_chars)
    print(f"  [{bar_str}] {est['pct']:.0f}%")
    print(f"  Days collected:  {est['days_collected']} trading days")
    if est["days_needed"] > 0:
        print(f"  Days remaining:  ~{est['days_needed']} more trading days to meet sample threshold")
        print(f"  Est. ready:      ~{est['est_ready_date']} (rough estimate)")
    else:
        print(f"  Sample threshold met -- re-run walk-forward to check promotions")

    print()
    if bars["stale"] or bars["missing_recent"]:
        print("ACTION NEEDED: Fix stale/missing tickers above, then re-run ingestion.")
    elif est["days_needed"] > 0:
        print("STATUS: Collecting. Run ingest_intraday_5m.py daily to accumulate data.")
    else:
        print("STATUS: Data sufficient. Run run_intraday_walkforward.py to check promotions.")

    print()
    print("Done.")


if __name__ == "__main__":
    main()
