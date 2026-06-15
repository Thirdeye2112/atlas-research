"""
run_score_calibration.py — Atlas Score component decomposition and calibration.

Reads from alpha_signal_snapshots (already synced from atlas_alpha), derives
component scores per snapshot, then runs calibration analysis grouping by
(component, bucket) to identify alpha generators vs destroyers.

Usage
-----
    python scripts/run_score_calibration.py
    python scripts/run_score_calibration.py --sync          # sync from atlas_alpha first
    python scripts/run_score_calibration.py --no-db         # skip writing to DB
    python scripts/run_score_calibration.py --min-n 20      # override min sample
    python scripts/run_score_calibration.py --top 10        # show top N components by alpha

Output
------
    Component Ranking Table:
      component | 1d alpha | 3d alpha | 5d alpha | 10d alpha | 20d alpha |
      sample size | pass/fail

    Summary:
      - Alpha generators (promoted)
      - Neutral features (candidate)
      - Alpha destroyers
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import psycopg2

from atlas_research.calibration.score_decomp import (
    populate_components,
    run_calibration,
    write_calibration,
    print_ranking_table,
    MIN_N,
)
from atlas_research.utils.logging import configure_logging, get_logger

configure_logging()
log = get_logger("run_score_calibration")


def main() -> None:
    parser = argparse.ArgumentParser(description="Atlas Score component calibration")
    parser.add_argument("--sync",    action="store_true",
                        help="Sync signal_snapshots from atlas_alpha first")
    parser.add_argument("--no-db",  action="store_true",
                        help="Skip writing calibration results to DB")
    parser.add_argument("--min-n",  type=int, default=MIN_N,
                        help=f"Minimum sample size per bucket (default {MIN_N})")
    parser.add_argument("--top",    type=int, default=0,
                        help="Show only top N components by 5d alpha (0=all)")
    args = parser.parse_args()

    research_url = os.environ.get("DATABASE_URL")
    alpha_url    = os.environ.get("DATABASE_URL_ALPHA")

    if not research_url:
        sys.exit("[ERROR] DATABASE_URL not set")

    # ── Optional sync ────────────────────────────────────────────────────────
    if args.sync:
        if not alpha_url:
            print("[WARN] DATABASE_URL_ALPHA not set — skipping sync")
        else:
            print("\n[1/3] Syncing signal_snapshots from atlas_alpha -> atlas_research...")
            from atlas_research.calibration.engine import sync_snapshots
            try:
                n = sync_snapshots(alpha_url, research_url)
                print(f"      Synced {n} snapshots")
                log.info("sync.complete", n_synced=n)
            except Exception as exc:
                print(f"[ERROR] Sync failed: {exc}")
                log.error("sync.failed", error=str(exc))
    else:
        print("\n[TIP] Pass --sync to pull latest snapshots from atlas_alpha first")

    # ── Populate component tables ─────────────────────────────────────────────
    print("\n[2/3] Deriving component scores and populating component tables...")
    n_comp, n_out = populate_components(research_url)
    print(f"      {n_comp} component rows  |  {n_out} outcome rows upserted")
    log.info("populate.complete", n_comp=n_comp, n_out=n_out)

    if n_comp == 0:
        sys.exit("[ERROR] No component data — run --sync first to pull resolved snapshots")

    # ── Run calibration ───────────────────────────────────────────────────────
    print(f"\n[3/3] Running calibration (min_n={args.min_n}, perm_iters=5000)...")
    rows = run_calibration(research_url)
    print(f"      Computed {len(rows)} (component, bucket) groups")
    log.info("calibration.complete", n_rows=len(rows))

    if not rows:
        sys.exit("[ERROR] No calibration data (need >= min_n resolved outcomes per bucket)")

    # ── Write to DB ───────────────────────────────────────────────────────────
    if not args.no_db:
        n_written = write_calibration(research_url, rows)
        print(f"      Written {n_written} rows to alpha_score_calibration_runs")
        log.info("write.complete", n_written=n_written)
    else:
        print("      [--no-db] Skipping DB write")

    # ── Compute baseline ──────────────────────────────────────────────────────
    with psycopg2.connect(research_url) as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT AVG(CASE WHEN return_5d > 0 THEN 1.0 ELSE 0.0 END)
            FROM alpha_score_component_outcomes
            WHERE return_5d IS NOT NULL
        """)
        baseline = float(cur.fetchone()[0] or 0.5)

    # ── Filter if --top ───────────────────────────────────────────────────────
    display_rows = rows
    if args.top > 0:
        display_rows = sorted(rows, key=lambda r: -(r.edge_5d or 0))[:args.top]

    # ── Print ranking table ───────────────────────────────────────────────────
    print_ranking_table(display_rows, baseline)

    # ── Print final verdict table ─────────────────────────────────────────────
    print(f"\n  {'Component':<30}  {'Bucket':<22}  {'n':>5}  "
          f"{'1d alpha':>8}  {'5d alpha':>8}  {'10d alpha':>9}  {'P':>7}  {'Status'}")
    print("  " + "-" * 102)

    verdict_rows = sorted(rows, key=lambda r: -(r.edge_5d or 0))
    for r in verdict_rows:
        e1  = f"{(r.hit_1d or 0)-baseline:+.1%}" if r.hit_1d is not None else "  n/a  "
        e5  = f"{r.edge_5d:+.1%}"                 if r.edge_5d is not None else "  n/a  "
        e10 = f"{(r.hit_10d or 0)-baseline:+.1%}" if r.hit_10d is not None else "  n/a  "
        pv  = f"{r.perm_p:.3f}"                    if r.perm_p is not None else "  n/a "
        print(f"  {r.component:<30}  {r.bucket:<22}  {r.n:>5}  "
              f"{e1:>8}  {e5:>8}  {e10:>9}  {pv:>7}  {r.status}")


if __name__ == "__main__":
    main()
