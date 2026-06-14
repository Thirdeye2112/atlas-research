"""
run_score_backtest.py — Backtest all 4 experimental score variants.

Joins experimental_score_snapshots with labels, buckets each score
(0-20, 20-40, 40-60, 60-80, 80-100), and computes per-bucket metrics
at 1d, 3d, 5d, 10d, 20d horizons.

Metrics: hit rate, avg return, median return, max drawdown, permutation p/pass.

Usage
-----
    python scripts/run_score_backtest.py
    python scripts/run_score_backtest.py --no-db
    python scripts/run_score_backtest.py --perm-iters 2000
    python scripts/run_score_backtest.py --min-n 30
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch

from atlas_research.utils.logging import configure_logging, get_logger

configure_logging()
log = get_logger("run_score_backtest")

HORIZONS    = [1, 5, 10, 20]
BUCKETS     = ["0-20", "20-40", "40-60", "60-80", "80-100"]
MIN_N       = 30
PERM_ITERS  = 3000
SCORE_COLS  = {
    "v1_current":        "score_v1_current",
    "v2_mean_reversion": "score_v2_mean_reversion",
    "v3_hybrid":         "score_v3_hybrid",
    "v4_tier_adjusted":  "score_v4_tier_adjusted",
}
LABEL_COLS = {
    1:  "return_1d",
    5:  "return_5d",
    10: "return_10d",
    20: "return_20d",
}


def _permutation_p(returns: np.ndarray, universe: np.ndarray, n_iters: int) -> float:
    observed = float(np.mean(returns > 0))
    count = 0
    for _ in range(n_iters):
        sample = np.random.choice(universe, size=len(returns), replace=True)
        if float(np.mean(sample > 0)) >= observed:
            count += 1
    return count / n_iters


def backtest_version(
    df: pd.DataFrame,
    score_col: str,
    version_name: str,
    universe_returns: dict[int, np.ndarray],
    min_n: int,
    perm_iters: int,
) -> list[dict]:
    rows = []
    for bkt in BUCKETS:
        mask = df["bucket"] == bkt
        bucket_df = df[mask]

        for hz in HORIZONS:
            lcol = LABEL_COLS[hz]
            if lcol not in bucket_df.columns:
                continue
            sub = bucket_df[lcol].dropna()
            n = len(sub)
            if n < min_n:
                continue

            arr = sub.to_numpy(dtype=float)
            hit_rate  = float(np.mean(arr > 0))
            avg_ret   = float(np.mean(arr))
            med_ret   = float(np.median(arr))
            cum       = np.cumsum(arr) if len(arr) > 0 else np.array([0.0])
            drawdown  = float(np.min(np.minimum.accumulate(cum) - cum))

            perm_p  = _permutation_p(arr, universe_returns[hz], perm_iters)
            perm_pass = perm_p < 0.05

            # Yearly breakdown
            yearly = {}
            if "year" in bucket_df.columns:
                for yr, grp in bucket_df[mask][["year", lcol]].dropna().groupby("year"):
                    yret = grp[lcol].to_numpy(dtype=float)
                    yearly[int(yr)] = {
                        "n": len(yret),
                        "hit_rate": round(float(np.mean(yret > 0)), 3),
                        "avg_return": round(float(np.mean(yret)), 4),
                    }

            rows.append({
                "score_version":    version_name,
                "bucket":           bkt,
                "horizon_days":     hz,
                "n":                n,
                "hit_rate":         round(hit_rate, 4),
                "avg_return":       round(avg_ret, 4),
                "median_return":    round(med_ret, 4),
                "max_drawdown":     round(drawdown, 4),
                "perm_p":           round(perm_p, 4),
                "perm_pass":        perm_pass,
                "yearly_breakdown": json.dumps(yearly),
            })
    return rows


def print_table(all_rows: list[dict], baseline: dict[int, float]) -> None:
    sep = "-" * 100
    print(f"\n{sep}")
    print("  SCORE BACKTEST RESULTS")
    print(sep)

    versions = list({r["score_version"] for r in all_rows})
    for ver in sorted(versions):
        print(f"\n  == {ver.upper()} ==")
        print(f"  {'Bucket':<10}  {'Hz':>3}  {'n':>6}  {'HR':>7}  {'AvgRet':>8}  "
              f"{'Med':>8}  {'MaxDD':>8}  {'P':>7}  {'Pass'}")
        print("  " + "-" * 72)

        ver_rows = [r for r in all_rows if r["score_version"] == ver]
        for bkt in BUCKETS:
            bkt_rows = sorted([r for r in ver_rows if r["bucket"] == bkt],
                              key=lambda x: x["horizon_days"])
            for r in bkt_rows:
                bl = baseline.get(r["horizon_days"], 0.5)
                edge_str = f"{(r['hit_rate']-bl)*100:+.1f}pp"
                p_str = f"{r['perm_p']:.3f}"
                pf = "PASS" if r["perm_pass"] else "fail"
                print(f"  {bkt:<10}  {r['horizon_days']:>3}d  {r['n']:>6}  "
                      f"{r['hit_rate']*100:>6.1f}%  {r['avg_return']*100:>+7.2f}%  "
                      f"{r['median_return']*100:>+7.2f}%  {r['max_drawdown']*100:>+7.2f}%  "
                      f"{p_str:>7}  {pf} ({edge_str})")

    # Summary table: 5d HR by version and bucket
    print(f"\n{sep}")
    print("  5-DAY HIT RATE SUMMARY  (universe baseline shown per version)")
    print(sep)
    hz5_rows = [r for r in all_rows if r["horizon_days"] == 5]
    print(f"  {'Version':<22}  " + "  ".join(f"{b:^10}" for b in BUCKETS))
    print("  " + "-" * 80)
    for ver in sorted(versions):
        cells = []
        for bkt in BUCKETS:
            row = next((r for r in hz5_rows
                        if r["score_version"] == ver and r["bucket"] == bkt), None)
            if row:
                bl5 = baseline.get(5, 0.5)
                cells.append(f"{row['hit_rate']*100:>5.1f}% ({(row['hit_rate']-bl5)*100:+.1f})")
            else:
                cells.append(f"{'n/a':^10}")
        print(f"  {ver:<22}  " + "  ".join(cells))
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest experimental score variants")
    parser.add_argument("--no-db",      action="store_true")
    parser.add_argument("--perm-iters", type=int, default=PERM_ITERS)
    parser.add_argument("--min-n",      type=int, default=MIN_N)
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        sys.exit("[ERROR] DATABASE_URL not set")

    # ── Load experimental scores + labels ────────────────────────────────
    print("\nLoading experimental scores and labels...")
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT e.ticker, e.date,
                       e.score_v1_current, e.score_v2_mean_reversion,
                       e.score_v3_hybrid,  e.score_v4_tier_adjusted,
                       l.return_1d, l.return_5d,
                       l.return_10d, l.return_20d,
                       EXTRACT(YEAR FROM e.date)::int AS year
                FROM experimental_score_snapshots e
                JOIN labels l ON l.ticker = e.ticker AND l.date = e.date
                WHERE l.return_5d IS NOT NULL
                ORDER BY e.date
            """)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]

    if not rows:
        print("[ERROR] No rows found. Run run_score_variants.py first.")
        return

    df = pd.DataFrame(rows, columns=cols)
    print(f"  Loaded {len(df):,} rows  ({df['date'].min()} to {df['date'].max()})")

    # Universe baseline (all ticker-dates)
    universe_returns = {
        hz: df[LABEL_COLS[hz]].dropna().to_numpy(dtype=float)
        for hz in HORIZONS
    }
    baseline = {hz: float(np.mean(universe_returns[hz] > 0)) for hz in HORIZONS}
    print(f"  Universe baseline: " + "  ".join(f"{hz}d={baseline[hz]*100:.1f}%"
                                                for hz in HORIZONS))

    # ── Backtest each version ────────────────────────────────────────────
    t0 = time.monotonic()
    all_results: list[dict] = []

    for ver_name, score_col in SCORE_COLS.items():
        if score_col not in df.columns:
            continue
        sub = df[["ticker", "date", "year", score_col] +
                 list(LABEL_COLS.values())].copy()
        sub = sub.rename(columns={score_col: "score"})
        sub["bucket"] = pd.cut(
            sub["score"],
            bins=[0, 20, 40, 60, 80, 100.01],
            labels=BUCKETS,
            right=False,
        ).astype(str)
        sub["bucket"] = sub["bucket"].replace("nan", None)

        res = backtest_version(sub, score_col, ver_name,
                               universe_returns, args.min_n, args.perm_iters)
        all_results.extend(res)
        print(f"  {ver_name}: {len(res)} (bucket, horizon) groups computed")

    elapsed = time.monotonic() - t0
    print(f"  Backtest done in {elapsed:.1f}s")

    if not all_results:
        print("[ERROR] No results computed — check score distribution.")
        return

    # ── Write to DB ──────────────────────────────────────────────────────
    if not args.no_db:
        with psycopg2.connect(db_url) as conn:
            with conn.cursor() as cur:
                execute_batch(cur, """
                    INSERT INTO score_backtest_results
                        (score_version, bucket, horizon_days, n,
                         hit_rate, avg_return, median_return, max_drawdown,
                         perm_p, perm_pass, yearly_breakdown)
                    VALUES
                        (%(score_version)s, %(bucket)s, %(horizon_days)s, %(n)s,
                         %(hit_rate)s, %(avg_return)s, %(median_return)s, %(max_drawdown)s,
                         %(perm_p)s, %(perm_pass)s, %(yearly_breakdown)s::jsonb)
                    ON CONFLICT (score_version, bucket, horizon_days) DO UPDATE SET
                        n                = EXCLUDED.n,
                        hit_rate         = EXCLUDED.hit_rate,
                        avg_return       = EXCLUDED.avg_return,
                        median_return    = EXCLUDED.median_return,
                        max_drawdown     = EXCLUDED.max_drawdown,
                        perm_p           = EXCLUDED.perm_p,
                        perm_pass        = EXCLUDED.perm_pass,
                        yearly_breakdown = EXCLUDED.yearly_breakdown,
                        computed_at      = now()
                """, all_results, page_size=200)
            conn.commit()
        print(f"  Written {len(all_results)} rows to score_backtest_results")

    print_table(all_results, baseline)


if __name__ == "__main__":
    main()
