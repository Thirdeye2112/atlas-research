"""
Atlas Behavior Analysis - Step 4: Behavior Interaction Analysis
===============================================================
Finds behavior pairs that co-occurred on the same ticker+date and tests
whether the combination outperforms either behavior alone.

Synergy score = (combined_hit_rate - max(hit_a, hit_b)) / baseline_hit_rate
  > 0: the pair performs better than the best individual
  < 0: the pair performs worse (conflicting signals)

Usage:
    python scripts/python/analyze_behavior_interactions.py
    python scripts/python/analyze_behavior_interactions.py --min-samples 5
    python scripts/python/analyze_behavior_interactions.py --min-samples 5 --top 20
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from itertools import combinations

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from tabulate import tabulate

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_detections_with_returns(engine) -> pd.DataFrame:
    """
    Load detections joined with 5d forward returns (from behavior_backtest_results
    via stored avg_return, or recomputed from raw_bars).
    """
    # Load detected_behaviors
    dets = pd.read_sql(
        text("""
            SELECT db.ticker, db.detection_date, db.behavior_id,
                   bd.category, bd.direction
            FROM detected_behaviors db
            JOIN behavior_definitions bd USING (behavior_id)
            WHERE bd.active = true
        """),
        engine,
    )
    if dets.empty:
        return pd.DataFrame()

    dets["detection_date"] = pd.to_datetime(dets["detection_date"]).dt.date

    # Load 5d forward returns from raw_bars (compute from prices)
    tickers = dets["ticker"].unique().tolist()
    tk_list = ", ".join(f"'{t}'" for t in tickers)
    prices  = pd.read_sql(
        text(f"SELECT ticker, date, close FROM raw_bars WHERE ticker IN ({tk_list}) ORDER BY ticker, date"),
        engine,
    )
    prices["date"] = pd.to_datetime(prices["date"]).dt.date

    # Compute 5d return per (ticker, date)
    ret_map: dict[tuple, float] = {}
    for ticker, px in prices.groupby("ticker"):
        px = px.set_index("date").sort_index()
        dates  = list(px.index)
        closes = px["close"].values
        didx   = {d: i for i, d in enumerate(dates)}
        for d, i in didx.items():
            if i + 5 < len(closes):
                c0, c5 = closes[i], closes[i + 5]
                if c0 > 0 and c5 > 0 and c5 == c5:
                    ret_map[(ticker, d)] = (c5 - c0) / c0 * 100

    dets["ret_5d"] = dets.apply(
        lambda r: ret_map.get((r["ticker"], r["detection_date"])), axis=1
    )
    return dets


# ---------------------------------------------------------------------------
# Interaction analysis
# ---------------------------------------------------------------------------

def compute_interactions(dets: pd.DataFrame,
                         min_samples: int = 5) -> pd.DataFrame:
    """
    For every co-occurring pair of behaviors (same ticker, same date),
    compute combined and individual performance and compute synergy score.
    """
    # Build a map: (ticker, date) -> list of behavior_ids
    grp_map: dict[tuple, list[str]] = {}
    for _, row in dets.iterrows():
        key = (row["ticker"], row["detection_date"])
        grp_map.setdefault(key, []).append(row["behavior_id"])

    # Build individual performance lookup
    valid = dets[dets["ret_5d"].notna()]
    indiv: dict[str, dict] = {}
    for bid, g in valid.groupby("behavior_id"):
        rets = g["ret_5d"].values
        indiv[bid] = {
            "n":        len(rets),
            "hit_rate": float((rets > 0).mean()),
            "avg_ret":  float(rets.mean()),
        }

    # Identify all co-occurring pairs
    pair_rets: dict[tuple[str, str], list[float]] = {}
    for (ticker, det_date), bids in grp_map.items():
        if len(bids) < 2:
            continue
        ret = dets.loc[
            (dets["ticker"] == ticker) & (dets["detection_date"] == det_date),
            "ret_5d"
        ].iloc[0] if not dets.loc[
            (dets["ticker"] == ticker) & (dets["detection_date"] == det_date),
            "ret_5d"
        ].empty else None

        if ret is None or ret != ret:
            continue

        for a, b in combinations(sorted(set(bids)), 2):
            pair_key = (a, b)
            pair_rets.setdefault(pair_key, []).append(ret)

    # Compute interaction stats
    baseline_hit = float((valid["ret_5d"] > 0).mean()) if len(valid) > 0 else 0.5
    results = []
    for (a, b), rets_list in pair_rets.items():
        if len(rets_list) < min_samples:
            continue
        rets = np.array(rets_list)
        combined_hit  = float((rets > 0).mean())
        combined_avg  = float(rets.mean())
        hit_a = indiv.get(a, {}).get("hit_rate", 0.5)
        hit_b = indiv.get(b, {}).get("hit_rate", 0.5)
        lift_a = combined_hit - hit_a
        lift_b = combined_hit - hit_b
        synergy = (combined_hit - max(hit_a, hit_b)) / max(baseline_hit, 0.01)

        results.append({
            "behavior_a":           a,
            "behavior_b":           b,
            "combined_n":           len(rets_list),
            "combined_hit_rate_5d": round(combined_hit, 3),
            "combined_avg_return_5d": round(combined_avg, 3),
            "hit_rate_a":           round(hit_a, 3),
            "hit_rate_b":           round(hit_b, 3),
            "lift_vs_a":            round(lift_a, 3),
            "lift_vs_b":            round(lift_b, 3),
            "synergy_score":        round(synergy, 3),
        })

    return pd.DataFrame(results) if results else pd.DataFrame()


# ---------------------------------------------------------------------------
# DB upsert
# ---------------------------------------------------------------------------

def upsert_interactions(engine, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    as_of = date.today()
    rows  = []
    for _, row in df.iterrows():
        rows.append({
            "behavior_a":            row["behavior_a"],
            "behavior_b":            row["behavior_b"],
            "as_of_date":            as_of,
            "combined_n":            int(row["combined_n"]),
            "combined_hit_rate_5d":  float(row["combined_hit_rate_5d"]),
            "combined_avg_return_5d":float(row["combined_avg_return_5d"]),
            "lift_vs_a":             float(row["lift_vs_a"]),
            "lift_vs_b":             float(row["lift_vs_b"]),
            "synergy_score":         float(row["synergy_score"]),
        })

    sql = text("""
        INSERT INTO behavior_interaction_results (
            behavior_a, behavior_b, as_of_date,
            combined_n, combined_hit_rate_5d, combined_avg_return_5d,
            lift_vs_a, lift_vs_b, synergy_score
        ) VALUES (
            :behavior_a, :behavior_b, :as_of_date,
            :combined_n, :combined_hit_rate_5d, :combined_avg_return_5d,
            :lift_vs_a, :lift_vs_b, :synergy_score
        )
        ON CONFLICT (behavior_a, behavior_b, as_of_date) DO UPDATE SET
            combined_n              = EXCLUDED.combined_n,
            combined_hit_rate_5d    = EXCLUDED.combined_hit_rate_5d,
            combined_avg_return_5d  = EXCLUDED.combined_avg_return_5d,
            lift_vs_a               = EXCLUDED.lift_vs_a,
            lift_vs_b               = EXCLUDED.lift_vs_b,
            synergy_score           = EXCLUDED.synergy_score
    """)
    with engine.begin() as conn:
        conn.execute(sql, rows)
    return len(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Analyze behavior interaction synergies")
    parser.add_argument("--min-samples", type=int, default=5,
                        help="Minimum co-occurrences to include a pair (default: 5)")
    parser.add_argument("--top", type=int, default=25,
                        help="How many top/bottom pairs to show (default: 25)")
    args = parser.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])

    print("Loading detections with 5d forward returns...")
    dets = load_detections_with_returns(engine)
    if dets.empty:
        print("No detections found. Run detector.py first.")
        return
    print(f"  {len(dets):,} detections, {dets['ret_5d'].notna().sum():,} with returns available")

    print(f"Computing interactions (min {args.min_samples} co-occurrences)...")
    interactions = compute_interactions(dets, min_samples=args.min_samples)
    if interactions.empty:
        print(f"No behavior pairs found with >= {args.min_samples} co-occurrences.")
        return

    n_written = upsert_interactions(engine, interactions)
    print(f"Wrote {n_written} behavior interaction results to DB.")

    # Report: top synergies
    top = interactions.nlargest(args.top, "synergy_score")
    bot = interactions.nsmallest(min(10, args.top // 2), "synergy_score")

    def fmt_row(r):
        return [
            r["behavior_a"],
            r["behavior_b"],
            int(r["combined_n"]),
            f"{r['combined_hit_rate_5d']:.1%}",
            f"{r['hit_rate_a']:.1%}",
            f"{r['hit_rate_b']:.1%}",
            f"{r['combined_avg_return_5d']:+.3f}%",
            f"{r['synergy_score']:+.3f}",
        ]

    headers = ["Behavior A", "Behavior B", "N", "Combined HR", "HR-A", "HR-B", "Avg Ret", "Synergy"]

    print(f"\n=== TOP {len(top)} SYNERGISTIC PAIRS ===")
    print(tabulate([fmt_row(r) for _, r in top.iterrows()], headers=headers, tablefmt="simple"))

    print(f"\n=== BOTTOM {len(bot)} CONFLICTING PAIRS ===")
    print(tabulate([fmt_row(r) for _, r in bot.iterrows()], headers=headers, tablefmt="simple"))


if __name__ == "__main__":
    main()
