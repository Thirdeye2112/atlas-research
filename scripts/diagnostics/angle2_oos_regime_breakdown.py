#!/usr/bin/env python
"""
Diagnosis Angle 2 — Regime breakdown of the embargoed OOS year.

Tags every row of the OOS year (2025-06-15 -> 2026-06-14) by regime
(bull/bear/range x high/low vol, same definition as
scripts/compute_feature_reliability.py:load_regime_context — market_trend
sign for trend, realized_vol_20 > 0.30 for vol), scores it with the
already-trained OOS model artifact (models/return_regressor_v1_2025-06-14),
and computes per-day rank IC within each regime bucket. Cross-references
against the regime mix of the training period (2011-07-01 -> 2025-06-14,
column-only read, no scoring) to see whether the OOS year was dominated by
a regime the training data underweighted.

THIS SCRIPT READS THE OOS SLICE EXACTLY ONCE (one load_date_range call on
2025-06-15 -> 2026-06-14, scored once). No iteration, no tuning against it.

Usage:
    python scripts/diagnostics/angle2_oos_regime_breakdown.py
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
from atlas_research.models.dataset import load_date_range, cross_sectional_normalize, to_arrays
from atlas_research.models.walk_forward import oos_window
from atlas_research.models.train import load_model, artifact_path
from atlas_research.models.evaluate import ic_tstat

OUT_DIR = _ROOT / "reports" / "diagnostics"
OUT_DIR.mkdir(parents=True, exist_ok=True)

VOL_THRESHOLD = 0.30  # same threshold as compute_feature_reliability.py


def tag_regime(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["regime_market"] = np.where(df["market_trend"] > 0, "bull",
                           np.where(df["market_trend"] < 0, "bear", "range"))
    df["regime_vol"] = np.where(df["realized_vol_20"] > VOL_THRESHOLD, "high_vol", "low_vol")
    df["regime"] = df["regime_market"] + "_" + df["regime_vol"]
    return df


def per_day_ic(df: pd.DataFrame, pred_col: str, true_col: str) -> pd.DataFrame:
    records = []
    for d, grp in df.groupby("date"):
        if len(grp) < 10:
            continue
        if grp[pred_col].nunique() < 2 or grp[true_col].nunique() < 2:
            continue
        corr, _ = stats.spearmanr(grp[pred_col], grp[true_col])
        if not np.isnan(corr):
            records.append({"date": d, "ic": float(corr), "n": len(grp)})
    return pd.DataFrame(records)


def main() -> None:
    parquet_dir = settings.PARQUET_OUTPUT_DIR
    model_dir = settings.MODEL_DIR
    feature_cols = settings.TRAIN_FEATURES

    parquet_files = sorted(parquet_dir.glob("feature_matrix_*.parquet"))
    data_end = date.fromisoformat(parquet_files[-1].stem.replace("feature_matrix_", ""))
    oos_start, oos_end = oos_window(data_end, settings.WF_OOS_MONTHS)
    print(f"[ANGLE 2] OOS window: {oos_start} -> {oos_end}")

    # ---- Read the OOS slice EXACTLY ONCE ----
    print("[ANGLE 2] OOS-slice read #1 of 1: loading + scoring the embargoed year.")
    val_df = load_date_range(
        oos_start, oos_end, feature_cols, "label_return_5d",
        parquet_dir, settings.TRAIN_MIN_QUALITY_SCORE,
    )
    val_df = tag_regime(val_df)  # market_trend/realized_vol_20 are raw here (pre-normalize)

    apath = artifact_path("return_regressor", "v1", date(2025, 6, 14), model_dir)
    if not apath.exists():
        print(f"FATAL: OOS artifact missing at {apath}")
        sys.exit(1)
    bundle = load_model(apath)

    norm_df = cross_sectional_normalize(val_df, feature_cols)  # market_trend untouched (flag-excluded)
    X_val, y_val, _tickers, dates = to_arrays(norm_df, feature_cols, "label_return_5d")
    y_pred = bundle.predict_return(X_val)

    scored = pd.DataFrame({
        "date": pd.Series(dates).values,
        "y_pred": y_pred,
        "y_true": y_val,
        "regime": val_df["regime"].values,
        "regime_market": val_df["regime_market"].values,
        "regime_vol": val_df["regime_vol"].values,
    })
    scored.to_csv(OUT_DIR / "angle2_oos_scored_rows.csv", index=False)

    # ---- Per-day IC within each regime bucket ----
    print("\n[ANGLE 2] OOS rank IC by regime bucket:")
    rows = []
    for regime, grp in scored.groupby("regime"):
        ic_df = per_day_ic(grp, "y_pred", "y_true")
        if ic_df.empty:
            rows.append({"regime": regime, "mean_ic": float("nan"), "t_stat": float("nan"),
                         "n_days": 0, "n_rows": len(grp)})
            continue
        ic_arr = ic_df["ic"].to_numpy()
        rows.append({
            "regime": regime, "mean_ic": float(np.mean(ic_arr)),
            "t_stat": ic_tstat(ic_arr), "n_days": len(ic_arr), "n_rows": len(grp),
        })
    regime_ic = pd.DataFrame(rows).sort_values("regime")
    print(regime_ic.to_string(index=False))
    regime_ic.to_csv(OUT_DIR / "angle2_oos_ic_by_regime.csv", index=False)

    overall_ic_df = per_day_ic(scored, "y_pred", "y_true")
    overall_arr = overall_ic_df["ic"].to_numpy()
    print(f"\n[ANGLE 2] OOS overall (sanity check vs established -0.0052): "
          f"mean_ic={overall_arr.mean():.4f}  t={ic_tstat(overall_arr):.2f}  n_days={len(overall_arr)}")

    # ---- Regime mix: OOS year ----
    oos_mix = scored["regime"].value_counts(normalize=True).rename("oos_pct").reset_index()
    oos_mix.columns = ["regime", "oos_pct"]

    # ---- Regime mix: training period (column-only read, no scoring, no model touch) ----
    train_start = date.fromisoformat(parquet_files[0].stem.replace("feature_matrix_", ""))
    print(f"\n[ANGLE 2] Reading regime columns only (market_trend, realized_vol_20) for the "
          f"training period {train_start} -> day before {oos_start}, across all parquet files. "
          f"This does not touch labels, features, or the OOS slice.")

    frames = []
    for fp in parquet_files:
        try:
            d = date.fromisoformat(fp.stem.replace("feature_matrix_", ""))
        except ValueError:
            continue
        if d >= oos_start:
            continue
        try:
            frames.append(pd.read_parquet(fp, engine="pyarrow",
                                           columns=["ticker", "date", "market_trend", "realized_vol_20"]))
        except Exception:
            continue
    train_regime_df = pd.concat(frames, ignore_index=True)
    train_regime_df = tag_regime(train_regime_df)
    train_mix = train_regime_df["regime"].value_counts(normalize=True).rename("train_pct").reset_index()
    train_mix.columns = ["regime", "train_pct"]

    mix = train_mix.merge(oos_mix, on="regime", how="outer").fillna(0.0).sort_values("regime")
    mix["train_pct"] = (mix["train_pct"] * 100).round(2)
    mix["oos_pct"] = (mix["oos_pct"] * 100).round(2)
    print("\n[ANGLE 2] Regime mix: training period (%) vs OOS year (%):")
    print(mix.to_string(index=False))
    mix.to_csv(OUT_DIR / "angle2_regime_mix_train_vs_oos.csv", index=False)
    print(f"\n[ANGLE 2] Training period rows scanned for regime mix: {len(train_regime_df):,} "
          f"({len(frames):,} parquet files, {train_start} -> day before {oos_start})")


if __name__ == "__main__":
    main()
