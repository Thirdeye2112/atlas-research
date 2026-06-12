"""
run_ipo_backtest.py
-------------------
Computes forward returns at standard horizons for each IPO in ipo_registry.
Benchmarks against SPY over the same window.

Usage:
    python scripts/run_ipo_backtest.py [--dry-run]
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from sqlalchemy import create_engine, text
import os

engine = create_engine(os.environ["DATABASE_URL"])

HORIZONS = [1, 5, 10, 20, 30, 60, 90, 120, 180, 252]


def get_return(c, ticker, start_date, days):
    """Return log return from IPO date to ~days trading days later."""
    rows = c.execute(text("""
        SELECT close::float FROM raw_bars
        WHERE ticker = :ticker AND date >= :start
        ORDER BY date ASC LIMIT :days
    """), {"ticker": ticker, "start": start_date, "days": days + 1}).fetchall()
    if len(rows) < 2:
        return None
    return (rows[-1][0] - rows[0][0]) / rows[0][0] * 100


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with engine.connect() as c:
        ipos = c.execute(text("""
            SELECT ticker, ipo_date, ipo_price FROM ipo_registry ORDER BY ipo_date
        """)).fetchall()

        if not ipos:
            print("No IPOs in registry. Run build_ipo_registry.py first.")
            sys.exit(1)

        print(f"Computing returns for {len(ipos)} IPOs across {len(HORIZONS)} horizons...")

        results = []
        skipped = 0
        for ipo in ipos:
            ticker = ipo.ticker
            ipo_date = ipo.ipo_date

            # Get day-1 close (first bar after IPO date) and IPO open price
            day1 = c.execute(text("""
                SELECT open::float, close::float FROM raw_bars
                WHERE ticker = :ticker AND date >= :date ORDER BY date ASC LIMIT 1
            """), {"ticker": ticker, "date": ipo_date}).fetchone()

            if not day1:
                skipped += 1
                continue

            day1_pop = (day1[1] - day1[0]) / day1[0] * 100 if day1[0] else None

            for h in HORIZONS:
                ret = get_return(c, ticker, ipo_date, h)
                spy_ret = get_return(c, "SPY", ipo_date, h)
                if ret is None:
                    continue
                vs_spy = (ret - spy_ret) if spy_ret is not None else None
                results.append({
                    "ticker": ticker,
                    "horizon_days": h,
                    "return_pct": round(ret, 4),
                    "vs_spy_pct": round(vs_spy, 4) if vs_spy is not None else None,
                    "day1_pop_pct": round(day1_pop, 4) if day1_pop is not None else None,
                })

        if args.dry_run:
            print(f"\n[DRY RUN] Would insert {len(results)} result rows.")
            print(f"Skipped {skipped} tickers (no bar data).")
            # Print summary stats
            by_horizon = {}
            for r in results:
                h = r["horizon_days"]
                if h not in by_horizon:
                    by_horizon[h] = []
                by_horizon[h].append(r["return_pct"])
            print("\nAvg return by horizon:")
            for h in HORIZONS:
                vals = by_horizon.get(h, [])
                if vals:
                    print(f"  {h:>4}d: avg={sum(vals)/len(vals):+.1f}%  n={len(vals)}")
            return

        # Insert results
        for r in results:
            c.execute(text("""
                INSERT INTO ipo_backtest_results (ticker, horizon_days, return_pct, vs_spy_pct, day1_pop_pct)
                VALUES (:ticker, :horizon_days, :return_pct, :vs_spy_pct, :day1_pop_pct)
                ON CONFLICT (ticker, horizon_days) DO UPDATE
                  SET return_pct=EXCLUDED.return_pct, vs_spy_pct=EXCLUDED.vs_spy_pct,
                      day1_pop_pct=EXCLUDED.day1_pop_pct, computed_at=NOW()
            """), r)
        c.commit()

        print(f"Inserted/updated {len(results)} result rows. Skipped {skipped}.")

        # Summary report
        print("\n--- IPO BACKTEST SUMMARY ---")
        print(f"{'Horizon':>8} {'N':>5} {'Avg Ret%':>10} {'vs SPY%':>10} {'Hit%':>7}")
        print("-" * 46)
        for h in HORIZONS:
            row = c.execute(text("""
                SELECT COUNT(*), AVG(return_pct), AVG(vs_spy_pct),
                       SUM(CASE WHEN return_pct > 0 THEN 1 ELSE 0 END)::float / COUNT(*) * 100
                FROM ipo_backtest_results WHERE horizon_days = :h
            """), {"h": h}).fetchone()
            if row and row[0]:
                print(f"  {h:>6}d {int(row[0]):>5} {float(row[1] or 0):>+10.2f} {float(row[2] or 0):>+10.2f} {float(row[3] or 0):>6.1f}%")

        # Best entry and exit windows
        print("\n--- BEST ENTRY WINDOW (max avg 30d forward return) ---")
        best = c.execute(text("""
            SELECT horizon_days, AVG(return_pct) AS avg_ret
            FROM ipo_backtest_results
            WHERE horizon_days <= 30
            GROUP BY horizon_days ORDER BY avg_ret DESC LIMIT 1
        """)).fetchone()
        if best:
            print(f"  Buy at day {best[0]}, avg {float(best[1]):+.2f}% over next 30d")

        print("\n--- LOCKUP EFFECT (days 150-170 vs 180-210) ---")
        pre = c.execute(text("""
            SELECT AVG(return_pct) FROM ipo_backtest_results WHERE horizon_days BETWEEN 120 AND 180
        """)).fetchone()
        post = c.execute(text("""
            SELECT AVG(return_pct) FROM ipo_backtest_results WHERE horizon_days = 252
        """)).fetchone()
        if pre and post and pre[0] and post[0]:
            delta = float(post[0]) - float(pre[0])
            print(f"  Pre-lockup avg: {float(pre[0]):+.2f}%  Post (252d): {float(post[0]):+.2f}%  Delta: {delta:+.2f}%")


if __name__ == "__main__":
    main()
