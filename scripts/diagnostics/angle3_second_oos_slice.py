#!/usr/bin/env python
"""
Diagnosis Angle 3 — a second, non-overlapping embargoed slice.

t=-2.20 over a single OOS year is borderline, not decisive. This trains one
model on data <= 2024-06-14 and scores it, once, on 2024-06-15 -> 2025-06-14
-- a year that does NOT overlap the primary embargoed OOS year
(2025-06-15 -> 2026-06-14) -- using the exact same walk-forward + purge
machinery (run_fold(), unedited) as every other fold.

The model artifact is saved to a diagnostics-only directory (NOT the shared
models/ dir), so build_model_map() in the production backtest scripts can
never pick it up. write_db=False -- nothing is written to model_registry;
this is a diagnostic-only model, not a production candidate.

THIS SCRIPT READS THIS SECOND EMBARGOED SLICE EXACTLY ONCE.

Usage:
    python scripts/diagnostics/angle3_second_oos_slice.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(override=True)

from config import settings
from atlas_research.models.walk_forward import Fold, run_fold

OUT_DIR = _ROOT / "reports" / "diagnostics"
OUT_DIR.mkdir(parents=True, exist_ok=True)
DIAG_MODEL_DIR = OUT_DIR / "angle3_diagnostic_artifacts"
DIAG_MODEL_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    parquet_dir = settings.PARQUET_OUTPUT_DIR
    feature_cols = settings.TRAIN_FEATURES

    parquet_files = sorted(parquet_dir.glob("feature_matrix_*.parquet"))
    data_start = date.fromisoformat(parquet_files[0].stem.replace("feature_matrix_", ""))

    slice2_train_end = date(2024, 6, 14)
    slice2_val_start = date(2024, 6, 15)
    slice2_val_end = date(2025, 6, 14)

    print(f"[ANGLE 3] Second embargoed slice -- READ #1 of 1.")
    print(f"[ANGLE 3] Train {data_start} -> {slice2_train_end}, score once on "
          f"{slice2_val_start} -> {slice2_val_end}.")
    print(f"[ANGLE 3] Primary OOS slice is 2025-06-15 -> 2026-06-14 -- no overlap with this slice.")
    print(f"[ANGLE 3] Note: this DOES overlap the regular walk-forward's fold 11 "
          f"(train<=2024-07-01, val 2024-07-02->2025-06-19) by design -- that's a "
          f"different, separately-trained model; non-overlap is required only "
          f"against the primary OOS slice, per the task definition.")
    print(f"[ANGLE 3] Model artifact -> {DIAG_MODEL_DIR} (NOT the shared models/ dir; "
          f"build_model_map() cannot see it). write_db=False (no model_registry write).")

    fold = Fold(
        number=998,
        train_start=data_start,
        train_end=slice2_train_end,
        val_start=slice2_val_start,
        val_end=slice2_val_end,
    )

    result = run_fold(
        fold=fold,
        parquet_dir=parquet_dir,
        model_dir=DIAG_MODEL_DIR,
        feature_cols=feature_cols,
        reg_target="label_return_5d",
        clf_target="label_positive_5d",
        model_version="v1-diag-slice2",
        purge_days=settings.WF_PURGE_DAYS,
        min_quality_score=settings.TRAIN_MIN_QUALITY_SCORE,
        write_db=False,
        feature_set_version=settings.MODEL_FEATURE_SET_VERSION,
    )

    if result.error:
        print(f"[ANGLE 3] FAILED: {result.error}")
        sys.exit(1)

    print(f"\n[ANGLE 3] n_train={result.n_train}  n_val={result.n_val}")
    for key in ["rank_ic", "mean_ic", "sharpe", "clf_auc", "clf_brier"]:
        v = result.val_metrics.get(key)
        if v is not None and v == v:
            print(f"  {key}: {round(v, 4)}")

    import json
    summary = {
        "train_start": str(data_start), "train_end": str(slice2_train_end),
        "val_start": str(slice2_val_start), "val_end": str(slice2_val_end),
        "n_train": result.n_train, "n_val": result.n_val,
        "val_metrics": result.val_metrics,
    }
    with open(OUT_DIR / "angle3_second_slice_result.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\n[ANGLE 3] Saved -> {OUT_DIR / 'angle3_second_slice_result.json'}")


if __name__ == "__main__":
    main()
