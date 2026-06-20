#!/usr/bin/env python
"""
score_oos.py — score the embargoed OOS hold-out exactly once.

run_walk_forward() reserves the final WF_OOS_MONTHS of data and never lets
fold generation touch it (see walk_forward.oos_window / generate_folds).
This script trains the chosen model (V1) on every date up to the OOS
boundary and scores it once on the embargoed block — the single-shot
final check, not part of fold selection.

Reuses walk_forward.run_fold() directly (same training/eval/DB-write path
as every other fold) with a synthetic Fold spanning the OOS window, so the
result is identical in kind to a normal fold's FoldResult, and a normal
model_registry row + model.joblib artifact is produced for downstream
consumers (confluence/conviction backtests) to pick up.

Usage:
    python scripts/score_oos.py
    python scripts/score_oos.py --no-db
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(override=True)

from config import settings
from atlas_research.db.connection import check_connection
from atlas_research.models.walk_forward import Fold, run_fold, oos_window
from atlas_research.utils.logging import configure_logging, get_logger

configure_logging(level=settings.LOG_LEVEL, fmt=settings.LOG_FORMAT)
log = get_logger("score_oos")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score the embargoed OOS hold-out once")
    parser.add_argument("--no-db", action="store_true", help="Dry run — no DB writes")
    parser.add_argument("--version", default=settings.MODEL_VERSION)
    args = parser.parse_args()

    write_db = not args.no_db
    if write_db and not check_connection():
        log.error("score_oos.db_unreachable")
        sys.exit(1)

    parquet_dir = settings.PARQUET_OUTPUT_DIR
    model_dir = settings.MODEL_DIR
    model_dir.mkdir(parents=True, exist_ok=True)
    feature_cols = settings.TRAIN_FEATURES

    parquet_files = sorted(parquet_dir.glob("feature_matrix_*.parquet"))
    data_start = date.fromisoformat(parquet_files[0].stem.replace("feature_matrix_", ""))
    data_end = date.fromisoformat(parquet_files[-1].stem.replace("feature_matrix_", ""))

    oos_start, oos_end = oos_window(data_end, settings.WF_OOS_MONTHS)
    if oos_start is None:
        print("[OOS] WF_OOS_MONTHS <= 0 — nothing reserved, nothing to score.")
        sys.exit(1)

    fold = Fold(
        number=12,
        train_start=data_start,
        train_end=oos_start - timedelta(days=1),
        val_start=oos_start,
        val_end=oos_end,
    )
    print(f"[OOS] Training on {fold.train_start} -> {fold.train_end}, "
          f"scoring once on {fold.val_start} -> {fold.val_end}")

    result = run_fold(
        fold=fold,
        parquet_dir=parquet_dir,
        model_dir=model_dir,
        feature_cols=feature_cols,
        reg_target="label_return_5d",
        clf_target="label_positive_5d",
        model_version=args.version,
        purge_days=settings.WF_PURGE_DAYS,
        min_quality_score=settings.TRAIN_MIN_QUALITY_SCORE,
        write_db=write_db,
        feature_set_version=settings.MODEL_FEATURE_SET_VERSION,
    )

    if result.error:
        print(f"\n[FAIL] OOS scoring failed: {result.error}")
        sys.exit(1)

    print(f"\n[OK] OOS scored. n_train={result.n_train} n_val={result.n_val}")
    for key in ["rank_ic", "mean_ic", "sharpe", "clf_auc", "clf_brier"]:
        v = result.val_metrics.get(key)
        if v is not None and v == v:
            print(f"  {key}: {round(v, 4)}")


if __name__ == "__main__":
    main()
