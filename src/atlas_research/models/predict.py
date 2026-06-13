"""
Live prediction scoring — Phase 2.

Loads the most recently trained model bundle, scores today's feature
matrix, computes rank percentiles across the universe, and writes to
the predictions table.

Called nightly after training completes (or after walk-forward if a new
champion is promoted).  Can also be run independently via the CLI.

PREDICTION COLUMNS WRITTEN
--------------------------
ticker               TEXT   — from the feature matrix
date                 DATE   — prediction date (today)
model_name           TEXT   — 'return_regressor' | 'positive_classifier' | 'ensemble'
model_version        TEXT   — from settings.MODEL_VERSION
expected_return      FLOAT  — regressor output (log return)
probability_positive FLOAT  — calibrated classifier probability
expected_drawdown    FLOAT  — proxy: -1 × expected_return when negative; else 0
confidence           FLOAT  — abs(probability_positive - 0.5) × 2  (0=uncertain, 1=certain)
rank_percentile      FLOAT  — cross-sectional percentile rank of probability_positive
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from atlas_research.models.dataset import (
    cross_sectional_normalize, load_date_range, to_arrays
)
from atlas_research.models.train import TrainedModelBundle, load_model
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)


def score_universe(
    pred_date: date,
    parquet_dir: Path,
    model_bundle: TrainedModelBundle,
    feature_cols: list[str],
    min_quality_score: float = 0.70,
    normalize_cross_sectional: bool = True,
) -> pd.DataFrame:
    """
    Score all tickers in today's feature matrix using the trained model bundle.

    Args:
        pred_date:               Date to score (loads parquet for this date).
        parquet_dir:             Directory of parquet files.
        model_bundle:            Loaded TrainedModelBundle.
        feature_cols:            Feature columns the model was trained on.
        min_quality_score:       Quality filter (same threshold as training).
        normalize_cross_sectional: Apply rank normalisation (must match training).

    Returns:
        DataFrame with prediction columns, or empty if no data.
    """
    fpath = parquet_dir / f"feature_matrix_{pred_date.isoformat()}.parquet"
    if not fpath.exists():
        log.warning("predict.no_parquet", date=str(pred_date), path=str(fpath))
        return pd.DataFrame()

    needed = {"ticker", "date"} | set(feature_cols)
    try:
        df = pd.read_parquet(fpath, engine="pyarrow",
                             columns=list(needed))
    except Exception as exc:
        log.error("predict.parquet_load_error", error=str(exc))
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    # Quality filter
    if "data_quality_score" in df.columns:
        df = df[df["data_quality_score"] >= min_quality_score]
    else:
        df["data_quality_score"] = 1.0

    if df.empty:
        log.warning("predict.all_filtered_by_quality", date=str(pred_date))
        return pd.DataFrame()

    # Rank normalisation
    if normalize_cross_sectional:
        df = cross_sectional_normalize(df, feature_cols)

    # Ensure all feature_cols are present
    for col in feature_cols:
        if col not in df.columns:
            df = df.copy()
            df[col] = np.nan

    X = df[feature_cols].to_numpy(dtype=np.float64)

    # Generate predictions
    exp_return = model_bundle.predict_return(X)
    prob_pos   = model_bundle.predict_prob(X)

    # Derived columns
    exp_drawdown = np.where(exp_return < 0, exp_return, 0.0)
    confidence   = np.abs(prob_pos - 0.5) * 2.0
    rank_pct     = pd.Series(prob_pos).rank(pct=True).to_numpy()

    result = pd.DataFrame({
        "ticker":               df["ticker"].to_numpy(),
        "date":                 pred_date,
        "expected_return":      exp_return,
        "probability_positive": prob_pos,
        "expected_drawdown":    exp_drawdown,
        "confidence":           confidence,
        "rank_percentile":      rank_pct,
    })

    log.info(
        "predict.scored",
        date=str(pred_date),
        tickers=len(result),
        mean_prob=round(float(prob_pos.mean()), 4),
        mean_rank_ic=round(float(np.corrcoef(
            pd.Series(prob_pos).rank(), pd.Series(exp_return).rank()
        )[0, 1]), 3) if len(result) > 2 else float("nan"),
    )
    return result


def write_predictions(
    predictions: pd.DataFrame,
    model_name: str,
    model_version: str,
) -> int:
    """
    Upsert prediction rows into the predictions table.

    Args:
        predictions:   DataFrame from score_universe().
        model_name:    e.g. 'return_regressor' or 'ensemble'.
        model_version: From settings.MODEL_VERSION.

    Returns:
        Number of rows written.
    """
    if predictions.empty:
        return 0

    from atlas_research.db import repository

    rows = []
    for _, row in predictions.iterrows():
        rows.append({
            "ticker":               row["ticker"],
            "date":                 row["date"],
            "model_name":           model_name,
            "model_version":        model_version,
            "expected_return":      _safe_float(row["expected_return"]),
            "probability_positive": _safe_float(row["probability_positive"]),
            "expected_drawdown":    _safe_float(row["expected_drawdown"]),
            "confidence":           _safe_float(row["confidence"]),
            "rank_percentile":      _safe_float(row["rank_percentile"]),
        })

    n = repository.upsert_predictions(rows)
    log.info("predict.written", rows=n, model=model_name, version=model_version)
    return n


def run_prediction_pipeline(
    pred_date: date,
    model_artifact_path: Path,
    parquet_dir: Path,
    feature_cols: list[str],
    model_name: str,
    model_version: str,
    min_quality_score: float = 0.70,
) -> int:
    """
    Full prediction pipeline:
        1. Load model bundle from disk
        2. Score today's feature matrix
        3. Write to predictions table

    Returns number of prediction rows written.
    """
    log.info("predict.pipeline_start",
             date=str(pred_date), artifact=str(model_artifact_path))

    bundle = load_model(model_artifact_path)
    if not isinstance(bundle, TrainedModelBundle):
        log.error("predict.bad_artifact", type=type(bundle).__name__)
        return 0

    # Use the feature set the model was actually trained on (stored in the artifact),
    # not the current settings list — they diverge when new features are added
    # between training runs.
    if hasattr(bundle, "feature_names") and bundle.feature_names:
        if set(bundle.feature_names) != set(feature_cols):
            log.info(
                "predict.feature_align",
                artifact_features=len(bundle.feature_names),
                settings_features=len(feature_cols),
                dropped=[f for f in feature_cols if f not in bundle.feature_names],
            )
        feature_cols = bundle.feature_names

    preds = score_universe(
        pred_date, parquet_dir, bundle, feature_cols, min_quality_score
    )
    if preds.empty:
        return 0

    return write_predictions(preds, model_name, model_version)


def _safe_float(v) -> float | None:
    import math
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None
