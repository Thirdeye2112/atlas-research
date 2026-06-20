#!/usr/bin/env python
"""
Diagnosis Angle 4 — the single-tree OOS collapse: degenerate, or honest
"nothing here"?

Part A — early-stopping validation curve (NO OOS read).
Replicates train_regressor's exact recipe (last-10%-of-training early-
stopping carve, same LGBM_PARAMS_REGRESSOR) for the OOS fold's training
window (<=2025-06-14), but adds an lgb.record_evaluation() callback to
capture the per-iteration RMSE curve that the saved joblib artifact doesn't
retain. This uses ONLY training-period data and its own internal ES holdout
-- it never touches the embargoed OOS validation slice.

Part B — input/label distribution shift (ONE OOS read).
Compares per-feature mean / std / missing-rate and the label distribution
between the 12 months immediately before the OOS boundary (2024-06-15 ->
2025-06-14, training-era reference) and the OOS year itself (2025-06-15 ->
2026-06-14). A adjacent, equal-length, immediately-pre/post comparison is
the most direct test of "did something shift right at the boundary."

THIS SCRIPT READS THE PRIMARY OOS SLICE EXACTLY ONCE (Part B only).

Usage:
    python scripts/diagnostics/angle4_single_tree_collapse.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(override=True)

from config import settings
from atlas_research.models.dataset import load_date_range, apply_purge_gap, cross_sectional_normalize, to_arrays
from atlas_research.utils.logging import get_logger

import lightgbm as lgb

log = get_logger("angle4")

OUT_DIR = _ROOT / "reports" / "diagnostics"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OOS_TRAIN_END = date(2025, 6, 14)
OOS_START = date(2025, 6, 15)
OOS_END = date(2026, 6, 14)
REF_START = date(2024, 6, 15)   # last 12 months of training, immediately pre-boundary
REF_END = date(2025, 6, 14)


def part_a_es_curve(parquet_dir: Path, feature_cols: list[str], data_start: date) -> None:
    print("[ANGLE 4 / Part A] Early-stopping curve -- training-data only, 0 OOS reads.")
    train_df = load_date_range(
        data_start, OOS_TRAIN_END, feature_cols, "label_return_5d",
        parquet_dir, settings.TRAIN_MIN_QUALITY_SCORE,
    )
    # Purge needs a non-empty val_df only for its own dates' log line; the
    # purge cutoff is computed entirely from train_df's own trailing dates.
    train_df, _ = apply_purge_gap(train_df, train_df.tail(1), settings.WF_PURGE_DAYS)
    train_df = cross_sectional_normalize(train_df, feature_cols)
    X_train, y_train, _t, _d = to_arrays(train_df, feature_cols, "label_return_5d")

    n_es = max(1, int(len(X_train) * 0.10))
    X_es, y_es = X_train[-n_es:], y_train[-n_es:]
    X_tr, y_tr = X_train[:-n_es], y_train[:-n_es]
    print(f"[ANGLE 4 / Part A] n_train_total={len(X_train)}  n_tr={len(X_tr)}  n_es={len(X_es)}")

    train_data = lgb.Dataset(X_tr, label=y_tr, feature_name=feature_cols)
    es_data = lgb.Dataset(X_es, label=y_es, feature_name=feature_cols, reference=train_data)

    eval_result: dict = {}
    callbacks = [
        lgb.early_stopping(stopping_rounds=20, verbose=False),
        lgb.log_evaluation(period=-1),
        lgb.record_evaluation(eval_result),
    ]
    model = lgb.train(
        settings.LGBM_PARAMS_REGRESSOR.copy(),
        train_set=train_data,
        valid_sets=[es_data],
        callbacks=callbacks,
    )
    print(f"[ANGLE 4 / Part A] n_trees={model.num_trees()} best_iteration={model.best_iteration}")

    metric_key = next(iter(eval_result["valid_0"].keys()))
    curve = eval_result["valid_0"][metric_key]
    curve_df = pd.DataFrame({"iteration": range(1, len(curve) + 1), metric_key: curve})
    curve_df.to_csv(OUT_DIR / "angle4_es_curve.csv", index=False)

    print(f"[ANGLE 4 / Part A] ES curve ({metric_key}), first 10 + last 10 iterations:")
    print(curve_df.head(10).to_string(index=False))
    if len(curve_df) > 10:
        print("  ...")
        print(curve_df.tail(10).to_string(index=False))

    flat = np.allclose(curve, curve[0], atol=1e-6)
    improved = curve[-1] < curve[0] if len(curve) > 1 else False
    best_at_1 = (model.best_iteration or len(curve)) <= 1
    print(f"[ANGLE 4 / Part A] flat_from_iter0={flat}  improved_by_end={improved}  "
          f"best_iteration<=1={best_at_1}  iter0_metric={curve[0]:.6f}  "
          f"best_metric={min(curve):.6f}")


def feature_distribution(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    rows = []
    n = len(df)
    for c in feature_cols:
        if c not in df.columns:
            rows.append({"feature": c, "mean": np.nan, "std": np.nan, "missing_rate": 1.0})
            continue
        col = df[c]
        rows.append({
            "feature": c,
            "mean": float(col.mean()) if col.notna().any() else np.nan,
            "std": float(col.std()) if col.notna().any() else np.nan,
            "missing_rate": float(col.isna().mean()),
        })
    return pd.DataFrame(rows)


def part_b_distribution_shift(parquet_dir: Path, feature_cols: list[str]) -> None:
    print("\n[ANGLE 4 / Part B] OOS-slice read #1 of 1 for this angle "
          "(distribution comparison, not scoring).")

    ref_df = load_date_range(REF_START, REF_END, feature_cols, "label_return_5d",
                              parquet_dir, settings.TRAIN_MIN_QUALITY_SCORE)
    oos_df = load_date_range(OOS_START, OOS_END, feature_cols, "label_return_5d",
                              parquet_dir, settings.TRAIN_MIN_QUALITY_SCORE)
    print(f"[ANGLE 4 / Part B] reference (pre-boundary year) rows={len(ref_df)}  "
          f"OOS (post-boundary year) rows={len(oos_df)}")

    ref_stats = feature_distribution(ref_df, feature_cols).set_index("feature")
    oos_stats = feature_distribution(oos_df, feature_cols).set_index("feature")

    shift = ref_stats.join(oos_stats, lsuffix="_ref", rsuffix="_oos")
    # Standardized mean shift: how many reference-std's did the mean move.
    shift["mean_shift_in_ref_std"] = (shift["mean_oos"] - shift["mean_ref"]) / shift["std_ref"].replace(0, np.nan)
    shift["std_ratio_oos_over_ref"] = shift["std_oos"] / shift["std_ref"].replace(0, np.nan)
    shift["missing_rate_delta"] = shift["missing_rate_oos"] - shift["missing_rate_ref"]
    shift = shift.reset_index()
    shift.to_csv(OUT_DIR / "angle4_feature_distribution_shift.csv", index=False)

    print("\n[ANGLE 4 / Part B] Top 10 features by |standardized mean shift|:")
    top_mean_shift = shift.reindex(
        shift["mean_shift_in_ref_std"].abs().sort_values(ascending=False).index
    ).head(10)
    print(top_mean_shift[["feature", "mean_ref", "mean_oos", "std_ref", "mean_shift_in_ref_std"]]
          .to_string(index=False))

    print("\n[ANGLE 4 / Part B] Top 10 features by std ratio farthest from 1.0 (variance shift):")
    shift["std_ratio_dev"] = (shift["std_ratio_oos_over_ref"] - 1.0).abs()
    top_std_shift = shift.reindex(shift["std_ratio_dev"].sort_values(ascending=False).index).head(10)
    print(top_std_shift[["feature", "std_ref", "std_oos", "std_ratio_oos_over_ref"]].to_string(index=False))

    print("\n[ANGLE 4 / Part B] Top 10 features by missing-rate delta:")
    top_missing = shift.reindex(shift["missing_rate_delta"].abs().sort_values(ascending=False).index).head(10)
    print(top_missing[["feature", "missing_rate_ref", "missing_rate_oos", "missing_rate_delta"]].to_string(index=False))

    # Label distribution
    ref_label = ref_df["label_return_5d"].dropna()
    oos_label = oos_df["label_return_5d"].dropna()
    label_summary = pd.DataFrame({
        "period": ["reference (2024-06-15->2025-06-14)", "OOS (2025-06-15->2026-06-14)"],
        "n": [len(ref_label), len(oos_label)],
        "mean": [ref_label.mean(), oos_label.mean()],
        "std": [ref_label.std(), oos_label.std()],
        "pct_positive": [(ref_label > 0).mean(), (oos_label > 0).mean()],
        "p5": [ref_label.quantile(0.05), oos_label.quantile(0.05)],
        "p95": [ref_label.quantile(0.95), oos_label.quantile(0.95)],
    })
    print("\n[ANGLE 4 / Part B] label_return_5d distribution, reference vs OOS:")
    print(label_summary.to_string(index=False))
    label_summary.to_csv(OUT_DIR / "angle4_label_distribution.csv", index=False)


def main() -> None:
    parquet_dir = settings.PARQUET_OUTPUT_DIR
    feature_cols = settings.TRAIN_FEATURES
    parquet_files = sorted(parquet_dir.glob("feature_matrix_*.parquet"))
    data_start = date.fromisoformat(parquet_files[0].stem.replace("feature_matrix_", ""))

    part_a_es_curve(parquet_dir, feature_cols, data_start)
    part_b_distribution_shift(parquet_dir, feature_cols)


if __name__ == "__main__":
    main()
