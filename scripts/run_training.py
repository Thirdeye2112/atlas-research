#!/usr/bin/env python
"""
run_training.py — Phase 2 model training entry point.

Runs walk-forward validation (or baseline mode) across all available
parquet data, writes model_registry and feature_performance rows,
then scores today's universe and writes predictions.

Usage:
    python scripts/run_training.py                    # full walk-forward
    python scripts/run_training.py --baseline         # baseline mode only
    python scripts/run_training.py --predict-only     # skip training, score today
    python scripts/run_training.py --start 2015-01-01 --end 2023-12-31
    python scripts/run_training.py --no-db            # dry run (no DB writes)
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from config import settings
from atlas_research.db.connection import check_connection
from atlas_research.models.walk_forward import run_baseline, run_walk_forward, oos_window
from atlas_research.utils.logging import configure_logging, get_logger

configure_logging(level=settings.LOG_LEVEL, fmt=settings.LOG_FORMAT)
log = get_logger("run_training")


def main() -> None:
    parser = argparse.ArgumentParser(description="Atlas Research Phase 2 — model training")
    parser.add_argument("--start",        default=None,  help="Training data start YYYY-MM-DD")
    parser.add_argument("--end",          default=None,  help="Training data end   YYYY-MM-DD")
    parser.add_argument("--baseline",     action="store_true",
                        help="Quick baseline mode (single model, no walk-forward)")
    parser.add_argument("--predict-only", action="store_true",
                        help="Skip training; only score today's universe")
    parser.add_argument("--artifact",      default=None,
                        help="Path to model.joblib to use for --predict-only (default: newest by mtime)")
    parser.add_argument("--date",          default=None,
                        help="Prediction date YYYY-MM-DD for --predict-only (default: today)")
    parser.add_argument("--no-db",        action="store_true",
                        help="Dry run — do not write to database")
    parser.add_argument("--version",      default=settings.MODEL_VERSION,
                        help=f"Model version tag (default: {settings.MODEL_VERSION})")
    args = parser.parse_args()

    if not check_connection():
        log.error("run_training.db_unreachable")
        sys.exit(1)

    parquet_dir = settings.PARQUET_OUTPUT_DIR
    model_dir   = settings.MODEL_DIR
    model_dir.mkdir(parents=True, exist_ok=True)

    feature_cols = settings.TRAIN_FEATURES
    write_db     = not args.no_db

    log.info(
        "run_training.start",
        baseline=args.baseline,
        predict_only=args.predict_only,
        write_db=write_db,
        parquet_dir=str(parquet_dir),
        n_features=len(feature_cols),
    )

    # ── Predict-only mode ─────────────────────────────────────
    if args.predict_only:
        pred_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else date.today()
        _run_predict_only(parquet_dir, model_dir, feature_cols, args.version, write_db,
                          artifact_override=args.artifact, pred_date=pred_date)
        return

    # ── Determine date range ──────────────────────────────────
    today = date.today()
    end_date = (
        datetime.strptime(args.end, "%Y-%m-%d").date() if args.end
        else today
    )
    if args.start:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
    else:
        # Detect actual parquet data start instead of using BACKFILL_YEARS.
        # BACKFILL_YEARS=15 would set data_start to 2011, but parquet files
        # only exist from 2019. Using BACKFILL_YEARS causes folds 1-5 to skip.
        parquet_files = sorted(settings.PARQUET_OUTPUT_DIR.glob("feature_matrix_*.parquet"))
        if parquet_files:
            # Parse date from filename: feature_matrix_YYYY-MM-DD.parquet
            first_name = parquet_files[0].stem  # e.g. "feature_matrix_2019-01-23"
            start_date = date.fromisoformat(first_name.replace("feature_matrix_", ""))
            log.info("run_training.parquet_start_detected", start=str(start_date))
        else:
            start_date = today.replace(year=today.year - settings.BACKFILL_YEARS)

    # ── Baseline or walk-forward ──────────────────────────────
    if args.baseline:
        result = run_baseline(
            train_start       = start_date,
            train_end         = end_date,
            parquet_dir       = parquet_dir,
            model_dir         = model_dir,
            feature_cols      = feature_cols,
            model_version     = args.version,
            purge_days        = settings.WF_PURGE_DAYS,
            min_quality_score = settings.TRAIN_MIN_QUALITY_SCORE,
            write_db          = write_db,
        )
        if result.error:
            print(f"\n✗ Baseline failed: {result.error}")
            sys.exit(1)
        print("\n✓ Baseline training complete.")
        print(f"  Train rows:  {result.n_train}")
        print(f"  Val rows:    {result.n_val}")
        _print_metrics(result.val_metrics)

    else:
        oos_start, oos_end = oos_window(end_date, settings.WF_OOS_MONTHS)
        if oos_start:
            print(f"\n[OOS] Reserved hold-out (never used for fold selection): "
                  f"{oos_start} -> {oos_end} ({settings.WF_OOS_MONTHS} months)")
        else:
            print("\n[OOS] No hold-out reserved (WF_OOS_MONTHS <= 0).")

        results = run_walk_forward(
            data_start           = start_date,
            data_end             = end_date,
            parquet_dir          = parquet_dir,
            model_dir            = model_dir,
            feature_cols         = feature_cols,
            model_version        = args.version,
            min_train_years      = settings.WF_MIN_TRAIN_YEARS,
            val_months           = settings.WF_VAL_MONTHS,
            purge_days           = settings.WF_PURGE_DAYS,
            min_quality_score    = settings.TRAIN_MIN_QUALITY_SCORE,
            write_db             = write_db,
            feature_set_version  = settings.MODEL_FEATURE_SET_VERSION,
            oos_months           = settings.WF_OOS_MONTHS,
        )
        ok  = [r for r in results if not r.error]
        err = [r for r in results if r.error]
        print(f"\n[OK] Walk-forward complete: {len(ok)} folds OK, {len(err)} errors.")
        for r in ok[-3:]:   # show last 3 folds
            print(f"  Fold {r.fold.number} ({r.fold.val_start}->{r.fold.val_end}):")
            _print_metrics(r.val_metrics, indent="    ")


def _run_predict_only(parquet_dir, model_dir, feature_cols, version, write_db,
                      artifact_override: str | None = None,
                      pred_date: date | None = None):
    """Find the most recently saved artifact (by mtime) and score `pred_date`."""
    from atlas_research.models.predict import run_prediction_pipeline
    if pred_date is None:
        pred_date = date.today()

    if artifact_override:
        newest = Path(artifact_override)
        if not newest.exists():
            log.error("predict_only.artifact_not_found", path=str(newest))
            sys.exit(1)
    else:
        # Sort by modification time (newest last) rather than alphabetically,
        # so a 2026-01-23 artifact doesn't shadow a freshly trained 2025-07-01 fold.
        artifacts = sorted(model_dir.rglob("model.joblib"), key=lambda p: p.stat().st_mtime)
        if not artifacts:
            log.error("predict_only.no_artifacts", model_dir=str(model_dir))
            sys.exit(1)
        newest = artifacts[-1]

    log.info("predict_only.using_artifact", path=str(newest))

    n = run_prediction_pipeline(
        pred_date           = pred_date,
        model_artifact_path = newest,
        parquet_dir         = parquet_dir,
        feature_cols        = feature_cols,
        model_name          = "return_regressor",
        model_version       = version,
        min_quality_score   = settings.TRAIN_MIN_QUALITY_SCORE,
    )
    print(f"\n[OK] Predictions written: {n} rows.")


def _print_metrics(metrics: dict, indent: str = "  ") -> None:
    for key in ["rank_ic", "sharpe", "mean_ic", "clf_auc", "clf_brier"]:
        v = metrics.get(key)
        if v is not None and v == v:  # not NaN
            print(f"{indent}{key}: {round(v, 4)}")


if __name__ == "__main__":
    main()
