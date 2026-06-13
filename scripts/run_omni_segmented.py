#!/usr/bin/env python3
"""
run_omni_segmented.py
---------------------
Segments the full universe into quality tiers and reports OMNI cross_up
hit rates per tier, exposing the quality-dependent signal reversal.

Tier definitions (applied to trailing 252-day median price and avg dollar vol):
  Tier 1 — Large cap : price > $50  AND avg_dollar_vol > $25M
  Tier 2 — Mid cap   : price $20-$50 AND avg_dollar_vol > $5M
  Tier 3 — Small cap : price $5-$20  AND avg_dollar_vol > $1M
  Tier 4 — Micro/junk: everything else (price < $5, very low volume, or distressed)

Usage:
    python scripts/run_omni_segmented.py
    python scripts/run_omni_segmented.py --pattern omni_82_cross_up
    python scripts/run_omni_segmented.py --pattern omni_82_cross_up --horizon 5 20
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

import pandas as pd
from scipy import stats
from sqlalchemy import create_engine, text

# ── Tier thresholds ──────────────────────────────────────────────────────────

TIERS = [
    {"name": "Tier 1 — Large cap",  "min_price": 50.0,  "max_price": None, "min_dvol": 25_000_000},
    {"name": "Tier 2 — Mid cap",    "min_price": 20.0,  "max_price": 50.0, "min_dvol":  5_000_000},
    {"name": "Tier 3 — Small cap",  "min_price":  5.0,  "max_price": 20.0, "min_dvol":  1_000_000},
    {"name": "Tier 4 — Micro/junk", "min_price": None,  "max_price": None, "min_dvol": None},  # catch-all
]


def assign_tier(price: float, dvol: float) -> str:
    if price > 50 and dvol > 25_000_000:
        return "Tier 1 — Large cap"
    if 20 <= price <= 50 and dvol > 5_000_000:
        return "Tier 2 — Mid cap"
    if 5 <= price <= 20 and dvol > 1_000_000:
        return "Tier 3 — Small cap"
    return "Tier 4 — Micro/junk"


def get_ticker_stats(engine) -> pd.DataFrame:
    """Return median_price and avg_dollar_vol per ticker using last 252 bars."""
    sql = text("""
        WITH ranked AS (
            SELECT
                ticker,
                adjusted_close,
                (adjusted_close * volume) AS dollar_vol,
                ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) AS rn
            FROM raw_bars
            WHERE adjusted_close > 0 AND volume > 0
        )
        SELECT
            ticker,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY adjusted_close) AS median_price,
            AVG(dollar_vol)                                               AS avg_dollar_vol,
            COUNT(*)                                                      AS bar_count
        FROM ranked
        WHERE rn <= 252
        GROUP BY ticker
        HAVING COUNT(*) >= 20
    """)
    with engine.connect() as conn:
        return pd.read_sql(sql, conn)


def get_omni_results(engine, pattern_name: str) -> pd.DataFrame:
    """Return per-ticker OMNI results from conditional_pattern_results."""
    sql = text("""
        SELECT cpr.ticker, cpr.horizon_days, cpr.sample_size,
               cpr.hit_rate, cpr.avg_return, cpr.p_value
        FROM conditional_pattern_results cpr
        JOIN conditional_patterns cp ON cp.id = cpr.pattern_id
        WHERE cp.name = :pattern
          AND cpr.ticker IS NOT NULL
          AND cpr.ticker != ''
          AND cpr.sample_size >= 5
    """)
    with engine.connect() as conn:
        return pd.read_sql(sql, conn, params={"pattern": pattern_name})


def weighted_hit_rate(group: pd.DataFrame, horizon: int) -> dict:
    h = group[group["horizon_days"] == horizon].copy()
    if h.empty:
        return {}
    total_n = h["sample_size"].sum()
    if total_n == 0:
        return {}
    wt_hit  = (h["hit_rate"]   * h["sample_size"]).sum() / total_n
    wt_ret  = (h["avg_return"] * h["sample_size"]).sum() / total_n

    # Aggregate p-value via Fisher's method if multiple tickers
    chi2 = 0.0
    valid_p = h["p_value"].dropna()
    if len(valid_p) > 0:
        import math
        chi2 = -2 * sum(math.log(max(p, 1e-300)) for p in valid_p)
        df = 2 * len(valid_p)
        agg_p = 1.0 - stats.chi2.cdf(chi2, df)
    else:
        agg_p = None

    return {
        "tickers":  len(h),
        "n":        int(total_n),
        "hit_rate": wt_hit,
        "avg_ret":  wt_ret,
        "p_value":  agg_p,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pattern", default="omni_82_cross_up")
    parser.add_argument("--horizon", type=int, nargs="+", default=[1, 5, 10, 20])
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_URL_RESEARCH")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        sys.exit(1)
    engine = create_engine(db_url)

    print(f"Pattern : {args.pattern}")
    print("Loading ticker stats from raw_bars…")
    stats_df = get_ticker_stats(engine)
    print(f"  {len(stats_df):,} tickers with ≥20 bars")

    print("Loading per-ticker OMNI results…")
    omni_df = get_omni_results(engine, args.pattern)
    if omni_df.empty:
        print(f"ERROR: no per-ticker results found for '{args.pattern}'")
        sys.exit(1)
    unique_tickers = omni_df["ticker"].nunique()
    print(f"  {unique_tickers:,} tickers with results")

    # Assign tiers
    stats_df["tier"] = stats_df.apply(
        lambda r: assign_tier(r["median_price"], r["avg_dollar_vol"]), axis=1
    )

    # Merge
    merged = omni_df.merge(stats_df[["ticker", "tier", "median_price", "avg_dollar_vol"]],
                           on="ticker", how="left")
    merged["tier"] = merged["tier"].fillna("Tier 4 — Micro/junk")

    tier_order = [t["name"] for t in TIERS]

    # ── Print table ──────────────────────────────────────────────────────────
    print()
    print(f"{'Tier':<24} {'Tkrs':>5}", end="")
    for h in args.horizon:
        print(f"  {h}d Hit%  {h}d Ret%  {h}d p", end="")
    print()
    print("-" * (24 + 6 + len(args.horizon) * 26))

    tier_summaries = {}
    for tier_name in tier_order:
        grp = merged[merged["tier"] == tier_name]
        tickers_in_tier = grp["ticker"].nunique()
        row = f"{tier_name:<24} {tickers_in_tier:>5}"
        tier_summaries[tier_name] = {}
        for h in args.horizon:
            res = weighted_hit_rate(grp, h)
            if res:
                hit_pct = res["hit_rate"] * 100
                ret_pct = res["avg_ret"] * 100
                p = res["p_value"]
                p_str = f"{p:.3f}" if p is not None else "  N/A"
                row += f"  {hit_pct:>6.1f}%  {ret_pct:>+6.2f}%  {p_str}"
                tier_summaries[tier_name][h] = res
            else:
                row += "       —        —     —"
        print(row)

    # SPY reference row
    spy_ref = {1: (67.0, 0.25), 5: (67.0, 1.05), 10: (72.3, 1.64), 20: (81.9, 2.12)}
    row = f"{'SPY only (reference)':<24} {'1':>5}"
    for h in args.horizon:
        if h in spy_ref:
            hit, ret = spy_ref[h]
            row += f"  {hit:>6.1f}%  {ret:>+6.2f}%  known"
        else:
            row += "       —        —     —"
    print(row)

    print()
    print("Notes:")
    print("  Hit rate = fraction of signals where fwd return > 0 (long direction)")
    print("  Avg Ret  = weighted average forward return across tickers in tier")
    print("  p-value  = Fisher combined p across per-ticker tests")
    print()

    # Tier composition summary
    print("Tier composition:")
    for tier_name in tier_order:
        grp_tickers = merged[merged["tier"] == tier_name]["ticker"].unique()
        grp_stats = stats_df[stats_df["tier"] == tier_name]
        median_p  = grp_stats["median_price"].median()
        median_dv = grp_stats["avg_dollar_vol"].median()
        print(f"  {tier_name:<24}: {len(grp_tickers):>4} tickers | "
              f"median price=${median_p:.0f} | median dvol=${median_dv/1e6:.1f}M")

    # Key finding
    print()
    t1 = tier_summaries.get("Tier 1 — Large cap", {}).get(20, {})
    t4 = tier_summaries.get("Tier 4 — Micro/junk", {}).get(20, {})
    if t1 and t4:
        direction = "CONFIRMED" if t1["hit_rate"] > 0.55 and t4["hit_rate"] < 0.50 else "MIXED"
        print(f"KEY FINDING ({direction}):")
        print(f"  Tier 1 (Large cap) 20d: {t1['hit_rate']*100:.1f}% hit rate — "
              f"{'BULLISH ✓' if t1['hit_rate'] > 0.50 else 'BEARISH ✗'}")
        print(f"  Tier 4 (Micro/junk) 20d: {t4['hit_rate']*100:.1f}% hit rate — "
              f"{'BULLISH ✓' if t4['hit_rate'] > 0.50 else 'BEARISH ✗'}")


if __name__ == "__main__":
    main()
