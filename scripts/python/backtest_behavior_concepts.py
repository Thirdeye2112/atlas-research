"""
Atlas Behavior Analysis - Step 3: Backtest Behavior Concepts
=============================================================
Computes forward return statistics for each detected behavior.
Joins detected_behaviors with raw_bars to compute forward returns
at 1d, 5d, and 10d horizons. Uses tabulate for a clean terminal report.

Usage:
    python scripts/python/backtest_behavior_concepts.py
    python scripts/python/backtest_behavior_concepts.py --min-samples 20
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from tabulate import tabulate

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_detections(engine) -> pd.DataFrame:
    """Load all detected behaviors."""
    df = pd.read_sql(
        text("""
            SELECT db.ticker, db.detection_date, db.behavior_id, db.intensity,
                   bd.category, bd.direction
            FROM detected_behaviors db
            JOIN behavior_definitions bd USING (behavior_id)
            WHERE bd.active = true
            ORDER BY db.detection_date ASC
        """),
        engine,
    )
    df["detection_date"] = pd.to_datetime(df["detection_date"]).dt.date
    return df


def _load_forward_returns(engine, tickers: list[str]) -> pd.DataFrame:
    """Load daily close prices for return computation."""
    ticker_list = ", ".join(f"'{t}'" for t in tickers)
    df = pd.read_sql(
        text(f"""
            SELECT ticker, date, close
            FROM raw_bars
            WHERE ticker IN ({ticker_list})
            ORDER BY ticker, date
        """),
        engine,
    )
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


# ---------------------------------------------------------------------------
# Forward return computation
# ---------------------------------------------------------------------------

def compute_forward_returns(prices_df: pd.DataFrame,
                            detections_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each detection, compute forward returns at 1d, 5d, 10d horizons.
    Returns detections_df with added columns: ret_1d, ret_5d, ret_10d.
    """
    # Build per-ticker close series indexed by date
    ret_rows = []
    for ticker, det_group in detections_df.groupby("ticker"):
        px = prices_df[prices_df["ticker"] == ticker].set_index("date")["close"]
        if px.empty:
            continue
        dates = sorted(px.index.tolist())
        date_idx = {d: i for i, d in enumerate(dates)}
        closes   = px.reindex(dates).values

        for _, row in det_group.iterrows():
            det_date = row["detection_date"]
            idx = date_idx.get(det_date)
            if idx is None:
                continue
            entry_close = closes[idx]
            if entry_close is None or entry_close != entry_close or entry_close <= 0:
                continue

            def _ret(horizon: int) -> float | None:
                fwd_idx = idx + horizon
                if fwd_idx >= len(closes):
                    return None
                fwd = closes[fwd_idx]
                if fwd is None or fwd != fwd:
                    return None
                return (fwd - entry_close) / entry_close * 100

            ret_rows.append({
                **row.to_dict(),
                "ret_1d":  _ret(1),
                "ret_5d":  _ret(5),
                "ret_10d": _ret(10),
            })

    if not ret_rows:
        return pd.DataFrame()
    return pd.DataFrame(ret_rows)


# ---------------------------------------------------------------------------
# Statistics computation
# ---------------------------------------------------------------------------

def compute_behavior_stats(df: pd.DataFrame, min_samples: int = 10) -> pd.DataFrame:
    """Compute performance statistics per behavior_id."""
    results = []
    for bid, grp in df.groupby("behavior_id"):
        for horizon, col in [(1, "ret_1d"), (5, "ret_5d"), (10, "ret_10d")]:
            valid = grp[col].dropna()
            if len(valid) < min_samples:
                continue
            rets     = valid.values
            winners  = rets[rets > 0]
            losers   = rets[rets <= 0]
            avg_win  = winners.mean() if len(winners) > 0 else 0.0
            avg_loss = abs(losers.mean()) if len(losers) > 0 else 0.0
            pf       = (avg_win * len(winners)) / (avg_loss * len(losers)) if avg_loss * len(losers) > 0 else float("inf")
            exp      = avg_win * (len(winners) / len(rets)) - avg_loss * (len(losers) / len(rets))
            results.append({
                "behavior_id":    bid,
                "category":       grp["category"].iloc[0],
                "direction":      grp["direction"].iloc[0],
                "horizon":        horizon,
                "n":              len(valid),
                "hit_rate":       round(float((rets > 0).mean()), 3),
                "avg_return":     round(float(rets.mean()), 3),
                "expectancy":     round(float(exp), 3),
                "profit_factor":  round(float(min(pf, 99.0)), 3),
                "std":            round(float(rets.std()), 3),
            })
    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# DB upsert
# ---------------------------------------------------------------------------

def upsert_results(engine, stats_df: pd.DataFrame) -> int:
    """Write 5d results to behavior_backtest_results."""
    if stats_df.empty:
        return 0
    h5 = stats_df[stats_df["horizon"] == 5]
    h1 = stats_df[stats_df["horizon"] == 1].set_index("behavior_id")
    h10= stats_df[stats_df["horizon"] == 10].set_index("behavior_id")
    if h5.empty:
        return 0

    as_of = date.today()
    rows  = []
    for _, row in h5.iterrows():
        bid = row["behavior_id"]
        rows.append({
            "behavior_id":      bid,
            "as_of_date":       as_of,
            "sample_size":      int(row["n"]),
            "hit_rate_1d":      float(h1.loc[bid, "hit_rate"]) if bid in h1.index else None,
            "hit_rate_5d":      float(row["hit_rate"]),
            "hit_rate_10d":     float(h10.loc[bid, "hit_rate"]) if bid in h10.index else None,
            "avg_return_1d":    float(h1.loc[bid, "avg_return"]) if bid in h1.index else None,
            "avg_return_5d":    float(row["avg_return"]),
            "avg_return_10d":   float(h10.loc[bid, "avg_return"]) if bid in h10.index else None,
            "expectancy_5d":    float(row["expectancy"]),
            "profit_factor_5d": float(row["profit_factor"]),
            "best_sector":      None,
            "worst_sector":     None,
        })

    sql = text("""
        INSERT INTO behavior_backtest_results (
            behavior_id, as_of_date, sample_size,
            hit_rate_1d, hit_rate_5d, hit_rate_10d,
            avg_return_1d, avg_return_5d, avg_return_10d,
            expectancy_5d, profit_factor_5d, best_sector, worst_sector
        ) VALUES (
            :behavior_id, :as_of_date, :sample_size,
            :hit_rate_1d, :hit_rate_5d, :hit_rate_10d,
            :avg_return_1d, :avg_return_5d, :avg_return_10d,
            :expectancy_5d, :profit_factor_5d, :best_sector, :worst_sector
        )
        ON CONFLICT (behavior_id, as_of_date) DO UPDATE SET
            sample_size      = EXCLUDED.sample_size,
            hit_rate_5d      = EXCLUDED.hit_rate_5d,
            avg_return_5d    = EXCLUDED.avg_return_5d,
            expectancy_5d    = EXCLUDED.expectancy_5d,
            profit_factor_5d = EXCLUDED.profit_factor_5d
    """)
    with engine.begin() as conn:
        conn.execute(sql, rows)
    return len(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Backtest behavior concepts")
    parser.add_argument("--min-samples", type=int, default=10,
                        help="Minimum detections to report stats (default: 10)")
    args = parser.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])

    print("Loading detections...")
    dets = _load_detections(engine)
    if dets.empty:
        print("No detections found. Run detector.py first.")
        return
    print(f"  {len(dets):,} detections across {dets['behavior_id'].nunique()} behaviors "
          f"and {dets['ticker'].nunique()} tickers")

    print("Loading price history for forward return computation...")
    tickers = dets["ticker"].unique().tolist()
    prices  = _load_forward_returns(engine, tickers)

    print("Computing forward returns...")
    with_returns = compute_forward_returns(prices, dets)
    if with_returns.empty:
        print("No valid returns computed.")
        return

    print("Computing statistics...")
    stats = compute_behavior_stats(with_returns, min_samples=args.min_samples)
    if stats.empty:
        print(f"No behaviors with >= {args.min_samples} samples.")
        return

    # Write results
    n_written = upsert_results(engine, stats)
    print(f"Wrote {n_written} behavior stats to behavior_backtest_results.")

    # Print report: 5d horizon sorted by expectancy
    h5 = stats[stats["horizon"] == 5].sort_values("expectancy", ascending=False)
    table = []
    for _, row in h5.iterrows():
        table.append([
            row["behavior_id"],
            row["category"],
            row["direction"],
            f"{int(row['n'])}",
            f"{row['hit_rate']:.1%}",
            f"{row['avg_return']:+.3f}%",
            f"{row['expectancy']:+.3f}%",
            f"{row['profit_factor']:.2f}",
        ])

    print("\n=== BEHAVIOR BACKTEST RESULTS (5d horizon, sorted by expectancy) ===")
    print(tabulate(
        table,
        headers=["Behavior", "Category", "Dir", "N", "Hit Rate", "Avg Ret", "Expectancy", "P/F"],
        tablefmt="simple",
    ))


if __name__ == "__main__":
    main()
