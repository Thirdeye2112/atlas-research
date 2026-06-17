#!/usr/bin/env python
"""
inject_labels_into_parquet.py — attach freshly-backfilled labels to existing
parquet feature matrices WITHOUT regenerating features.

Why not re-run run_parquet_export?  The existing parquet files were exported
from a fuller feature source than the current feature_snapshots EAV table
(parquet has every universe ticker; feature_snapshots now holds far fewer).
Re-exporting would shrink each file.  Instead we left-join the label_* columns
from the labels table onto the existing rows, preserving every feature row and
only filling/refreshing the label columns.

Run AFTER scripts/backfill_recent_labels.py.

Usage:
    python scripts/inject_labels_into_parquet.py
    python scripts/inject_labels_into_parquet.py --start 2026-03-20 --end 2026-06-14
    python scripts/inject_labels_into_parquet.py --dry-run
"""
from __future__ import annotations

import argparse
import glob
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import pandas as pd
from sqlalchemy import text

from atlas_research.db import connection
from config import settings

# DB column -> parquet column
_LABEL_MAP = {
    "return_5d":    "label_return_5d",
    "return_20d":   "label_return_20d",
    "positive_5d":  "label_positive_5d",
    "positive_20d": "label_positive_20d",
}


def main() -> None:
    p = argparse.ArgumentParser(description="Inject labels into existing parquet")
    p.add_argument("--start", default="2026-03-20")
    p.add_argument("--end",   default="2026-06-14")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    pdir = settings.PARQUET_OUTPUT_DIR
    files = sorted(glob.glob(str(pdir / "feature_matrix_*.parquet")))
    files = [f for f in files
             if args.start <= Path(f).stem.replace("feature_matrix_", "") <= args.end]
    print(f"Injecting labels into {len(files)} parquet files "
          f"[{args.start}..{args.end}]  ({'DRY RUN' if args.dry_run else 'writing'})")

    total_rows = total_labeled = changed = 0
    for f in files:
        d = Path(f).stem.replace("feature_matrix_", "")
        df = pd.read_parquet(f, engine="pyarrow")
        with connection.get_connection() as conn:
            lab = pd.read_sql(
                text("SELECT ticker, return_5d, return_20d, positive_5d, positive_20d "
                     "FROM labels WHERE date = :d"),
                conn, params={"d": d},
            )
        if lab.empty:
            print(f"  {d}: no labels in DB — skipped")
            continue
        lab = lab.rename(columns=_LABEL_MAP)

        # Drop any stale label columns, then left-join the fresh ones.
        df = df.drop(columns=[c for c in _LABEL_MAP.values() if c in df.columns])
        merged = df.merge(lab, on="ticker", how="left")

        n_lab = int(merged["label_return_5d"].notna().sum())
        total_rows += len(merged)
        total_labeled += n_lab
        changed += 1
        print(f"  {d}: rows={len(merged):<6} label_return_5d non-null={n_lab}")

        if not args.dry_run:
            merged.to_parquet(f, engine="pyarrow",
                              compression=settings.PARQUET_COMPRESSION, index=False)

    print(f"\nDone. files={changed}  total_rows={total_rows:,}  "
          f"rows_with_5d_label={total_labeled:,}  "
          f"{'(dry-run, nothing written)' if args.dry_run else 'written'}")


if __name__ == "__main__":
    main()
