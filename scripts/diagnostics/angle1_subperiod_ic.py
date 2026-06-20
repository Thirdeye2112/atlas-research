#!/usr/bin/env python
"""
Diagnosis Angle 1 — Sub-period IC stability.

Stitches together each walk-forward fold's already-trained, de-leaked V1
validation predictions into a single non-overlapping per-day rank-IC series
spanning the full walk-forward history (2014-07 -> 2025-06), then buckets
by year and quarter to see whether the established pooled IC (+0.0131) is a
steady edge or a few strong early years dragging a decayed-toward-zero mean.

Read-only: loads existing model artifacts (models/return_regressor_v1_*)
and parquet feature matrices; trains nothing, writes nothing to the DB.
Adjacent fold validation windows overlap by ~1 month (each is a ~12-month
window starting the day after a train_end that advances by exactly 1 year);
this script trims each fold's window to end the day before the next fold's
window starts, so every calendar day contributes exactly one IC value.

Does NOT touch the embargoed OOS year (2025-06-15 -> 2026-06-14) at all —
generate_folds() with WF_OOS_MONTHS already excludes it from fold generation.

Usage:
    python scripts/diagnostics/angle1_subperiod_ic.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(override=True)

from config import settings
from atlas_research.models.dataset import load_date_range, cross_sectional_normalize, to_arrays
from atlas_research.models.walk_forward import generate_folds
from atlas_research.models.train import load_model, artifact_path
from atlas_research.models.evaluate import ic_tstat

OUT_DIR = _ROOT / "reports" / "diagnostics"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    parquet_dir = settings.PARQUET_OUTPUT_DIR
    model_dir = settings.MODEL_DIR
    feature_cols = settings.TRAIN_FEATURES

    parquet_files = sorted(parquet_dir.glob("feature_matrix_*.parquet"))
    data_start = date.fromisoformat(parquet_files[0].stem.replace("feature_matrix_", ""))
    data_end = date.fromisoformat(parquet_files[-1].stem.replace("feature_matrix_", ""))

    folds = generate_folds(
        data_start, data_end,
        settings.WF_MIN_TRAIN_YEARS, settings.WF_VAL_MONTHS, settings.WF_OOS_MONTHS,
    )
    print(f"[ANGLE 1] {len(folds)} walk-forward folds generated (data_end={data_end}, "
          f"WF_OOS_MONTHS={settings.WF_OOS_MONTHS}). The embargoed OOS year is excluded "
          f"by generate_folds() and is NOT read by this script (0 reads).")

    daily_records: list[dict] = []

    for i, fold in enumerate(folds):
        effective_val_end = fold.val_end
        if i + 1 < len(folds):
            effective_val_end = min(fold.val_end, folds[i + 1].val_start - timedelta(days=1))

        apath = artifact_path("return_regressor", "v1", fold.train_end, model_dir)
        if not apath.exists():
            print(f"  fold {fold.number}: SKIP — artifact missing at {apath}")
            continue
        bundle = load_model(apath)

        val_df = load_date_range(
            fold.val_start, effective_val_end, feature_cols, "label_return_5d",
            parquet_dir, settings.TRAIN_MIN_QUALITY_SCORE,
        )
        if val_df.empty:
            print(f"  fold {fold.number}: SKIP — no data in trimmed window "
                  f"{fold.val_start}->{effective_val_end}")
            continue

        val_df = cross_sectional_normalize(val_df, feature_cols)
        X_val, y_val, _tickers, dates = to_arrays(val_df, feature_cols, "label_return_5d")
        y_pred = bundle.predict_return(X_val)

        tmp = pd.DataFrame({"date": pd.Series(dates).values, "y_pred": y_pred, "y_true": y_val})
        n_days = 0
        for d, grp in tmp.groupby("date"):
            if len(grp) < 10:
                continue
            if grp["y_pred"].nunique() < 2 or grp["y_true"].nunique() < 2:
                continue
            corr, _ = stats.spearmanr(grp["y_pred"], grp["y_true"])
            if not np.isnan(corr):
                daily_records.append({"date": d, "ic": float(corr), "n": len(grp), "fold": fold.number})
                n_days += 1

        print(f"  fold {fold.number}: trained<= {fold.train_end}, scored "
              f"{fold.val_start}->{effective_val_end} (trimmed from {fold.val_end}), "
              f"{n_days} IC days")

    daily_df = pd.DataFrame(daily_records)
    daily_df.to_csv(OUT_DIR / "angle1_daily_ic.csv", index=False)

    daily_df["date"] = pd.to_datetime(daily_df["date"])
    daily_df["year"] = daily_df["date"].dt.year
    daily_df["quarter"] = daily_df["date"].dt.to_period("Q").astype(str)

    ic_arr = daily_df["ic"].to_numpy()
    print(f"\n[ANGLE 1] Pooled (sanity check vs established +0.0131): "
          f"mean_ic={ic_arr.mean():.4f}  t={ic_tstat(ic_arr):.2f}  n_days={len(ic_arr)}")

    print("\n[ANGLE 1] By year:")
    yearly = daily_df.groupby("year")["ic"].agg(mean_ic="mean", n="count").reset_index()
    yearly["t_stat"] = [
        ic_tstat(daily_df.loc[daily_df["year"] == y, "ic"].to_numpy()) for y in yearly["year"]
    ]
    print(yearly.to_string(index=False))
    yearly.to_csv(OUT_DIR / "angle1_yearly_ic.csv", index=False)

    print("\n[ANGLE 1] By quarter:")
    quarterly = daily_df.groupby("quarter")["ic"].agg(mean_ic="mean", n="count").reset_index()
    quarterly["t_stat"] = [
        ic_tstat(daily_df.loc[daily_df["quarter"] == q, "ic"].to_numpy()) for q in quarterly["quarter"]
    ]
    print(quarterly.to_string(index=False))
    quarterly.to_csv(OUT_DIR / "angle1_quarterly_ic.csv", index=False)


if __name__ == "__main__":
    main()
