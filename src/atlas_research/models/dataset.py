"""
Dataset preparation for Phase 2 model training.

Loads wide feature matrices from daily parquet files, applies quality
filtering, handles the purge gap, and returns clean numpy arrays.

KEY DESIGN DECISIONS
--------------------
1. Parquet files are the canonical training source (not the DB).
   They are already wide, already quality-scored, already label-joined.
   The DB is queried as a fallback only.

2. Quality filter: rows with data_quality_score < threshold are dropped
   before any model sees them.  This is a hard filter, not a feature weight.
   data_quality_score IS included as a training feature (Q1 answer).

3. Purge gap: the caller specifies train_end and val_start.
   This module enforces the gap by filtering — if the caller passes overlapping
   dates, _any_ rows within [train_end - purge_days, val_start] are dropped.

4. All returned arrays are float64.  Boolean label columns (positive_5d) are
   cast to 0.0 / 1.0.  NaN in features is left as NaN — LightGBM handles it
   natively and better than imputation for financial data.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from atlas_research.features.regime_interactions import (
    INTERACTION_NAMES, BASE_COLS_NEEDED, add_interactions,
)
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)


def load_date_range(
    start_date: date,
    end_date: date,
    feature_cols: list[str],
    target_col: str,
    parquet_dir: Path,
    min_quality_score: float = 0.70,
) -> pd.DataFrame:
    """
    Load and concatenate daily parquet files for [start_date, end_date].

    Applies quality filter and drops rows where target is null.
    Returns a DataFrame with columns: ticker, date, <feature_cols>, <target_col>.

    Args:
        start_date:        First date to load (inclusive).
        end_date:          Last date to load (inclusive).
        feature_cols:      Ordered feature column names (including data_quality_score).
        target_col:        Label column, e.g. 'label_return_5d' or 'label_positive_5d'.
        parquet_dir:       Directory containing feature_matrix_YYYY-MM-DD.parquet files.
        min_quality_score: Rows below this are excluded.

    Returns:
        DataFrame ready for splitting into X / y arrays.
        Empty DataFrame if no parquet files found in range.
    """
    frames: list[pd.DataFrame] = []
    current = start_date
    files_found = 0

    # Interaction feature names are computed on-the-fly and are never in parquet.
    # Remove them from the columnar-read set and add their required base columns.
    base_feature_cols = [f for f in feature_cols if f not in INTERACTION_NAMES]
    needed_base = (
        {"ticker", "date"}
        | set(base_feature_cols)
        | {target_col}
        | BASE_COLS_NEEDED
    )

    while current <= end_date:
        fpath = parquet_dir / f"feature_matrix_{current.isoformat()}.parquet"
        if fpath.exists():
            files_found += 1
            df: pd.DataFrame | None = None
            try:
                # Columnar read — only load what we need
                df = pd.read_parquet(fpath, engine="pyarrow",
                                     columns=list(needed_base))
            except Exception:
                # Schema evolution: older file missing new columns — load all,
                # select available; to_arrays() fills the rest with NaN.
                try:
                    full_df = pd.read_parquet(fpath, engine="pyarrow")
                    available = [c for c in needed_base if c in full_df.columns]
                    df = full_df[available]
                    missing_cols = sorted(needed_base - set(available))
                    if missing_cols:
                        log.info("dataset.schema_fallback",
                                 path=str(fpath), missing=missing_cols)
                except Exception as exc2:
                    log.warning("dataset.parquet_load_error",
                                path=str(fpath), error=str(exc2))
            if df is not None:
                frames.append(df)
        current += timedelta(days=1)

    if not frames:
        log.warning("dataset.no_parquet_files",
                    start=str(start_date), end=str(end_date),
                    parquet_dir=str(parquet_dir))
        return pd.DataFrame()

    full = pd.concat(frames, ignore_index=True)
    n_raw = len(full)

    # Add V3 regime-interaction features (idempotent, cheap, always available)
    add_interactions(full)

    # ── Quality filter ────────────────────────────────────────
    if "data_quality_score" in full.columns:
        full = full[full["data_quality_score"] >= min_quality_score]
        n_quality_dropped = n_raw - len(full)
    else:
        n_quality_dropped = 0
        # Synthesise a neutral score column so feature_cols works
        full["data_quality_score"] = 1.0

    # ── Drop missing targets ──────────────────────────────────
    if target_col in full.columns:
        full = full[full[target_col].notna()]
    else:
        log.error("dataset.missing_target_col", col=target_col)
        return pd.DataFrame()

    log.info(
        "dataset.loaded",
        start=str(start_date), end=str(end_date),
        files=files_found,
        n_raw=n_raw,
        quality_dropped=n_quality_dropped,
        n_final=len(full),
    )
    return full.reset_index(drop=True)


def to_arrays(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
) -> tuple[np.ndarray, np.ndarray, pd.Series, pd.Series]:
    """
    Extract feature matrix X, target vector y, and index metadata from df.

    Args:
        df:           DataFrame from load_date_range().
        feature_cols: Ordered feature columns.
        target_col:   Target column name.

    Returns:
        X:       float64 array (n_samples, n_features). NaN kept for LightGBM.
        y:       float64 array (n_samples,). Booleans cast to 0.0/1.0.
        tickers: Series of ticker strings aligned to X.
        dates:   Series of date values aligned to X.
    """
    # Ensure all feature_cols are present (fill missing with NaN)
    for col in feature_cols:
        if col not in df.columns:
            df = df.copy()
            df[col] = np.nan

    X = df[feature_cols].to_numpy(dtype=np.float64)
    y_raw = df[target_col]

    # Cast boolean labels to float (True→1.0, False→0.0)
    if y_raw.dtype == bool or str(y_raw.dtype) in ("bool", "boolean"):
        y = y_raw.astype(np.float64).to_numpy()
    else:
        y = y_raw.to_numpy(dtype=np.float64)

    tickers = df["ticker"].reset_index(drop=True)
    dates   = df["date"].reset_index(drop=True)

    return X, y, tickers, dates


def apply_purge_gap(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    purge_days: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Remove rows from train_df that are within purge_days of val_df's start.

    This prevents label leakage: a training row on date T with a 5-day label
    window overlaps with validation rows on T+1 through T+5.  Removing the
    last purge_days rows from training ensures no forward-looking information
    bleeds into the validation set.

    Args:
        train_df:    Training DataFrame with a 'date' column.
        val_df:      Validation DataFrame with a 'date' column.
        purge_days:  Number of trading days to purge before val_start.

    Returns:
        (purged_train_df, val_df) — val_df is unchanged.
    """
    if train_df.empty or val_df.empty:
        return train_df, val_df

    # Convert date column to actual date objects for comparison
    def to_date(s: pd.Series) -> pd.Series:
        if hasattr(s.iloc[0], "date"):
            return s.apply(lambda d: d.date() if hasattr(d, "date") else d)
        return s

    train_dates = to_date(train_df["date"])
    val_dates   = to_date(val_df["date"])

    val_start   = val_dates.min()
    purge_cutoff = val_start - timedelta(days=purge_days)

    before = len(train_df)
    train_df = train_df[train_dates < purge_cutoff].reset_index(drop=True)
    purged   = before - len(train_df)

    log.info(
        "dataset.purge_applied",
        val_start=str(val_start),
        purge_cutoff=str(purge_cutoff),
        purge_days=purge_days,
        rows_purged=purged,
    )
    return train_df, val_df


def cross_sectional_normalize(
    df: pd.DataFrame,
    feature_cols: list[str],
    exclude: list[str] | None = None,
) -> pd.DataFrame:
    """
    Rank-normalize features within each date cross-section.

    Converts raw feature values to percentile ranks [0, 1] within each date.
    This removes regime effects (e.g. RSI distribution shifts in bull vs bear)
    and makes features more comparable across different market periods.

    data_quality_score and boolean/flag columns are excluded from normalization.

    Args:
        df:           DataFrame with 'date' and feature columns.
        feature_cols: Columns to normalize.
        exclude:      Additional columns to skip (e.g. 'data_quality_score').

    Returns:
        DataFrame with normalized feature columns; date and ticker unchanged.
    """
    skip = set(exclude or []) | {"data_quality_score"}
    to_normalize = [c for c in feature_cols if c not in skip and c in df.columns]

    if not to_normalize:
        return df

    df = df.copy()
    df[to_normalize] = df.groupby("date")[to_normalize].rank(pct=True)
    return df
