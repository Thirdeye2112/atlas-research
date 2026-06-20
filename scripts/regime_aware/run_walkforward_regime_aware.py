#!/usr/bin/env python
"""
Regime-aware rebuild — STEP 2: walk-forward training + evaluation, with a
per-fold, per-regime IC breakdown, run side-by-side against the existing V1
artifacts on the identical validation data.

Uses the EXISTING walk-forward machinery unedited: generate_folds(),
load_date_range(), apply_purge_gap(), cross_sectional_normalize(),
to_arrays(), evaluate_fold() — identical folds, purge, and OOS-reservation
boundary as V1 (WF_MIN_TRAIN_YEARS, WF_VAL_MONTHS, WF_OOS_MONTHS, WF_PURGE_DAYS
all from config.settings, unchanged). Only the regime-weighted model is
TRAINED fresh (via train_regime_weighted.py, a new parallel path); the V1
side of the comparison LOADS the already-trained V1 fold artifacts (no
retraining, pure inference) so both arms are scored on byte-identical
validation data with identical regime tags.

write_db=False throughout -- this is a research rebuild pending review, not
a production promotion. Regime-aware artifacts are saved OUTSIDE the shared
models/ directory (at <repo_root>/models_regime_aware/) so build_model_map()
in the production backtest scripts can never pick them up.

THIS SCRIPT DOES NOT TOUCH THE EMBARGOED OOS YEAR (2025-06-15 -> 2026-06-14)
AT ALL -- generate_folds() with WF_OOS_MONTHS already excludes it. 0 reads.

Usage:
    python scripts/regime_aware/run_walkforward_regime_aware.py
"""
from __future__ import annotations

import sys
from datetime import date
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
from atlas_research.models.dataset import load_date_range, apply_purge_gap, cross_sectional_normalize, to_arrays
from atlas_research.models.walk_forward import generate_folds
from atlas_research.models.train import (
    TrainedModelBundle, artifact_path, save_model, load_model,
)
from atlas_research.models.train_regime_weighted import (
    tag_regime, regime_balanced_weights, train_regressor_weighted, train_classifier_weighted,
)
from atlas_research.models.evaluate import evaluate_fold, ic_tstat

OUT_DIR = _ROOT / "reports" / "validity"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RW_MODEL_DIR = _ROOT / "models_regime_aware"
RW_MODEL_DIR.mkdir(parents=True, exist_ok=True)

REG_TARGET = "label_return_5d"
CLF_TARGET = "label_positive_5d"


def per_regime_ic(dates: pd.Series, y_pred: np.ndarray, y_true: np.ndarray, regime: pd.Series) -> pd.DataFrame:
    """Per-day Spearman IC within each regime bucket. Mirrors the OOS diagnosis Angle 2 helper."""
    df = pd.DataFrame({
        "date": pd.Series(dates).reset_index(drop=True).values,
        "y_pred": y_pred, "y_true": y_true,
        "regime": regime.reset_index(drop=True).values,
    })
    rows = []
    for rgm, grp in df.groupby("regime"):
        ic_vals = []
        for _, day in grp.groupby("date"):
            if len(day) < 10:
                continue
            if day["y_pred"].nunique() < 2 or day["y_true"].nunique() < 2:
                continue
            corr, _ = stats.spearmanr(day["y_pred"], day["y_true"])
            if not np.isnan(corr):
                ic_vals.append(corr)
        if ic_vals:
            arr = np.array(ic_vals)
            rows.append({"regime": rgm, "mean_ic": float(arr.mean()), "t_stat": ic_tstat(arr),
                         "n_days": len(arr), "n_rows": len(grp)})
        else:
            rows.append({"regime": rgm, "mean_ic": float("nan"), "t_stat": float("nan"),
                         "n_days": 0, "n_rows": len(grp)})
    return pd.DataFrame(rows)


def main() -> None:
    parquet_dir = settings.PARQUET_OUTPUT_DIR
    feature_cols = settings.TRAIN_FEATURES

    parquet_files = sorted(parquet_dir.glob("feature_matrix_*.parquet"))
    data_start = date.fromisoformat(parquet_files[0].stem.replace("feature_matrix_", ""))
    data_end = date.fromisoformat(parquet_files[-1].stem.replace("feature_matrix_", ""))

    folds = generate_folds(data_start, data_end, settings.WF_MIN_TRAIN_YEARS,
                            settings.WF_VAL_MONTHS, settings.WF_OOS_MONTHS)
    print(f"[STEP 2] {len(folds)} folds (identical to V1's walk-forward; "
          f"WF_OOS_MONTHS={settings.WF_OOS_MONTHS} embargoes the final year -- "
          f"0 reads of it in this script).")

    fold_summary_rows = []
    regime_rows = []

    for fold in folds:
        print(f"\n[STEP 2] Fold {fold.number}: train {fold.train_start}->{fold.train_end}, "
              f"val {fold.val_start}->{fold.val_end}")

        train_df = load_date_range(fold.train_start, fold.train_end, feature_cols, REG_TARGET,
                                    parquet_dir, settings.TRAIN_MIN_QUALITY_SCORE)
        clf_train = load_date_range(fold.train_start, fold.train_end, feature_cols, CLF_TARGET,
                                     parquet_dir, settings.TRAIN_MIN_QUALITY_SCORE)
        val_df = load_date_range(fold.val_start, fold.val_end, feature_cols, REG_TARGET,
                                  parquet_dir, settings.TRAIN_MIN_QUALITY_SCORE)
        clf_val = load_date_range(fold.val_start, fold.val_end, feature_cols, CLF_TARGET,
                                   parquet_dir, settings.TRAIN_MIN_QUALITY_SCORE)
        if train_df.empty or val_df.empty:
            print(f"  SKIP fold {fold.number}: insufficient data")
            continue

        train_df, val_df = apply_purge_gap(train_df, val_df, settings.WF_PURGE_DAYS)
        clf_train, clf_val = apply_purge_gap(clf_train, clf_val, settings.WF_PURGE_DAYS)

        # Tag regime on RAW (pre-normalize) data -- realized_vol_20 gets rank-
        # normalized away otherwise; market_trend is flag-excluded so it's
        # safe either way, but we tag before normalizing for both, for safety.
        regime_train = tag_regime(train_df)
        regime_val = tag_regime(val_df)
        regime_clf_train = tag_regime(clf_train)

        w_train = regime_balanced_weights(regime_train)
        w_clf_train = regime_balanced_weights(regime_clf_train)

        train_df_n = cross_sectional_normalize(train_df, feature_cols)
        val_df_n = cross_sectional_normalize(val_df, feature_cols)
        clf_train_n = cross_sectional_normalize(clf_train, feature_cols)
        clf_val_n = cross_sectional_normalize(clf_val, feature_cols)

        X_train, y_reg_train, _t, _d = to_arrays(train_df_n, feature_cols, REG_TARGET)
        X_val, y_reg_val, _vt, val_dates = to_arrays(val_df_n, feature_cols, REG_TARGET)
        X_clf_train, y_clf_train, _, _ = to_arrays(clf_train_n, feature_cols, CLF_TARGET)
        X_clf_val, y_clf_val, _, _ = to_arrays(clf_val_n, feature_cols, CLF_TARGET)

        # ---- Train regime-weighted model (fresh) ----
        reg_model, reg_imp = train_regressor_weighted(
            X_train, y_reg_train, w_train, X_val, y_reg_val, feature_cols)
        clf_model, platt, clf_imp = train_classifier_weighted(
            X_clf_train, y_clf_train, w_clf_train, X_clf_val, y_clf_val, feature_cols)

        bundle = TrainedModelBundle(
            regressor=reg_model, classifier=clf_model, platt=platt,
            feature_names=feature_cols, train_end=fold.train_end,
            model_version="v1rw", reg_importances=reg_imp, clf_importances=clf_imp,
        )
        apath = artifact_path("return_regressor", "v1rw", fold.train_end, RW_MODEL_DIR)
        save_model(bundle, apath)

        y_reg_pred_rw = reg_model.predict(X_val)
        y_clf_prob_rw = bundle.predict_prob(X_clf_val)
        rw_metrics = evaluate_fold(y_reg_val, y_reg_pred_rw, y_clf_prob_rw, val_dates, "regression")
        clf_metrics_rw = evaluate_fold(y_clf_val, y_clf_prob_rw, y_clf_prob_rw, val_dates, "classification")
        rw_metrics["clf_auc"] = clf_metrics_rw.get("auc", float("nan"))
        rw_metrics["clf_brier"] = clf_metrics_rw.get("brier", float("nan"))
        rw_metrics["n_trees_reg"] = reg_model.num_trees()
        rw_metrics["n_trees_clf"] = clf_model.num_trees()

        # ---- V1 baseline: LOAD existing artifact, score the SAME val data ----
        v1_apath = artifact_path("return_regressor", "v1", fold.train_end, settings.MODEL_DIR)
        v1_metrics = {}
        if v1_apath.exists():
            v1_bundle = load_model(v1_apath)
            y_reg_pred_v1 = v1_bundle.predict_return(X_val)
            y_clf_prob_v1 = v1_bundle.predict_prob(X_clf_val)
            v1_metrics = evaluate_fold(y_reg_val, y_reg_pred_v1, y_clf_prob_v1, val_dates, "regression")
            clf_metrics_v1 = evaluate_fold(y_clf_val, y_clf_prob_v1, y_clf_prob_v1, val_dates, "classification")
            v1_metrics["clf_auc"] = clf_metrics_v1.get("auc", float("nan"))
            v1_metrics["clf_brier"] = clf_metrics_v1.get("brier", float("nan"))
        else:
            print(f"  WARNING: V1 artifact not found at {v1_apath}; no V1 baseline for this fold")

        print(f"  RW : rank_ic={rw_metrics.get('rank_ic'):.4f}  auc={rw_metrics.get('clf_auc'):.4f}  "
              f"brier={rw_metrics.get('clf_brier'):.4f}  trees(reg/clf)={reg_model.num_trees()}/{clf_model.num_trees()}")
        if v1_metrics:
            print(f"  V1 : rank_ic={v1_metrics.get('rank_ic'):.4f}  auc={v1_metrics.get('clf_auc'):.4f}  "
                  f"brier={v1_metrics.get('clf_brier'):.4f}")

        fold_summary_rows.append({
            "fold": fold.number, "train_end": str(fold.train_end),
            "val_start": str(fold.val_start), "val_end": str(fold.val_end),
            "n_train": len(X_train), "n_val": len(X_val),
            "rw_rank_ic": rw_metrics.get("rank_ic"), "rw_mean_ic": rw_metrics.get("mean_ic"),
            "rw_clf_auc": rw_metrics.get("clf_auc"), "rw_clf_brier": rw_metrics.get("clf_brier"),
            "rw_n_trees_reg": reg_model.num_trees(), "rw_n_trees_clf": clf_model.num_trees(),
            "v1_rank_ic": v1_metrics.get("rank_ic"), "v1_mean_ic": v1_metrics.get("mean_ic"),
            "v1_clf_auc": v1_metrics.get("clf_auc"), "v1_clf_brier": v1_metrics.get("clf_brier"),
        })

        # ---- Per-regime IC, both arms, on the IDENTICAL val data/regime tags ----
        rw_regime_ic = per_regime_ic(val_dates, y_reg_pred_rw, y_reg_val, regime_val)
        rw_regime_ic["fold"] = fold.number
        rw_regime_ic["arm"] = "regime_weighted"
        regime_rows.append(rw_regime_ic)

        if v1_apath.exists():
            v1_regime_ic = per_regime_ic(val_dates, y_reg_pred_v1, y_reg_val, regime_val)
            v1_regime_ic["fold"] = fold.number
            v1_regime_ic["arm"] = "v1"
            regime_rows.append(v1_regime_ic)

    fold_summary = pd.DataFrame(fold_summary_rows)
    fold_summary.to_csv(OUT_DIR / "step2_fold_summary.csv", index=False)
    print("\n[STEP 2] Fold summary (RW vs V1):")
    print(fold_summary.to_string(index=False))

    valid = fold_summary.dropna(subset=["rw_rank_ic"])
    print(f"\n[STEP 2] Mean rank IC -- RW: {valid['rw_rank_ic'].mean():.4f}  "
          f"V1: {valid['v1_rank_ic'].mean():.4f}")
    print(f"[STEP 2] Mean clf AUC -- RW: {valid['rw_clf_auc'].mean():.4f}  "
          f"V1: {valid['v1_clf_auc'].mean():.4f}")

    regime_df = pd.concat(regime_rows, ignore_index=True)
    regime_df.to_csv(OUT_DIR / "step2_per_regime_ic_by_fold.csv", index=False)

    print("\n[STEP 2] Per-regime IC, pooled across all folds (weighted by n_days), RW vs V1:")
    pooled = regime_df.groupby(["arm", "regime"]).apply(
        lambda g: pd.Series({
            "mean_ic_w": float(np.average(g["mean_ic"], weights=g["n_days"])) if g["n_days"].sum() > 0 else float("nan"),
            "n_days": g["n_days"].sum(), "n_rows": g["n_rows"].sum(),
        }), include_groups=False
    ).reset_index()
    print(pooled.to_string(index=False))
    pooled.to_csv(OUT_DIR / "step2_per_regime_ic_pooled.csv", index=False)


if __name__ == "__main__":
    main()
