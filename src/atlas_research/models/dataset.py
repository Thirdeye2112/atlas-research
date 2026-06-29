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

# ── V4 mean-reversion feature (mr_score) ──────────────────────────────────────
# Like the V3 interaction features, mr_score is computed off-pipeline and is NOT
# stored in the daily parquet matrices. It is merged on-the-fly from a lookup
# parquet (built by scripts/build_mr_lookup.py) keyed on (ticker, date) — exactly
# the path validated in run_v3_v4_experiment.py. Names here are excluded from the
# columnar parquet read and added after concat, mirroring add_interactions().
LOADER_MERGED_NAMES = {"mr_score"}
_MR_LOOKUP_PATH = Path(__file__).resolve().parents[3] / "exports" / "parquet" / "mr_score_lookup.parquet"
_MR_CACHE: pd.DataFrame | None = None


def _mr_lookup() -> pd.DataFrame | None:
    """Cached (ticker, date)->mr_score table; None if the lookup is absent."""
    global _MR_CACHE
    if _MR_CACHE is None:
        if not _MR_LOOKUP_PATH.exists():
            log.warning("dataset.mr_lookup_missing", path=str(_MR_LOOKUP_PATH))
            return None
        m = pd.read_parquet(_MR_LOOKUP_PATH)
        m["date"] = pd.to_datetime(m["date"]).dt.normalize()
        _MR_CACHE = m
    return _MR_CACHE


def add_mr_score(full: pd.DataFrame) -> None:
    """Left-merge mr_score onto a loaded frame by (ticker, date), in place.
    No-op (column of NaN) if the lookup is unavailable — to_arrays() tolerates NaN."""
    if "mr_score" in full.columns:
        return
    m = _mr_lookup()
    if m is None:
        full["mr_score"] = np.nan
        return
    key = pd.to_datetime(full["date"]).dt.normalize()
    merged = pd.DataFrame({"ticker": full["ticker"].values, "date": key.values}).merge(
        m, on=["ticker", "date"], how="left")
    full["mr_score"] = merged["mr_score"].values


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

    # Interaction features (computed on-the-fly) and loader-merged features
    # (mr_score, joined from a lookup) are never in parquet. Remove them from the
    # columnar-read set and add the interaction features' required base columns.
    base_feature_cols = [f for f in feature_cols
                         if f not in INTERACTION_NAMES and f not in LOADER_MERGED_NAMES]
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

    # Add V4 mean-reversion feature (mr_score), merged from the lookup parquet.
    # Idempotent; harmless for V1/V2/V3 callers (column simply goes unused).
    add_mr_score(full)

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
    Remove the last ``purge_days`` *trading* days of training.

    This prevents label leakage: a training row on date T with a 5-day label
    window uses data through T+5.  The training rows nearest the validation
    period are exactly the ones whose forward-label window overlaps it, so we
    drop them.

    The purge is counted in trading days, not calendar days.  The previous
    implementation used ``val_start - timedelta(days=purge_days)`` (calendar),
    which over a weekend/holiday leaves ~1-2 trading days still leaking.  Here
    we drop rows on the last ``purge_days`` *distinct trading dates* present in
    the training set, which is leak-free regardless of weekends/holidays.

    Args:
        train_df:    Training DataFrame with a 'date' column.
        val_df:      Validation DataFrame with a 'date' column.
        purge_days:  Number of trading days to purge from the end of training.

    Returns:
        (purged_train_df, val_df) — val_df is unchanged.
    """
    if train_df.empty or val_df.empty:
        return train_df, val_df

    if purge_days <= 0:
        log.info("dataset.purge_applied", purge_days=purge_days, rows_purged=0)
        return train_df.reset_index(drop=True), val_df

    # Normalise the date column to plain date objects for comparison.
    def to_date(s: pd.Series) -> pd.Series:
        if len(s) and hasattr(s.iloc[0], "date"):
            return s.apply(lambda d: d.date() if hasattr(d, "date") else d)
        return s

    train_dates = to_date(train_df["date"])

    # Sorted unique trading dates in the training set; drop rows falling on the
    # last ``purge_days`` of them.
    unique_dates = np.sort(train_dates.unique())
    if len(unique_dates) <= purge_days:
        # Entire training set is within the purge window.
        purge_cutoff = unique_dates[0] if len(unique_dates) else None
        purged_dates = set(unique_dates.tolist())
    else:
        purge_cutoff = unique_dates[-purge_days]   # first purged trading date
        purged_dates = set(unique_dates[-purge_days:].tolist())

    before = len(train_df)
    keep_mask = ~train_dates.isin(purged_dates).to_numpy()
    out = train_df[keep_mask].reset_index(drop=True)
    purged = before - len(out)

    log.info(
        "dataset.purge_applied",
        val_start=str(to_date(val_df["date"]).min()),
        purge_cutoff=str(purge_cutoff),
        purge_days=purge_days,
        trading_dates_purged=min(purge_days, len(unique_dates)),
        rows_purged=purged,
    )
    return out, val_df


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
    Ranking a binary 0/1 flag would destroy its meaning (every 1 maps to the
    same mid-rank within the day, every 0 to another), so flags are detected by
    their value set ({-1, 0, 1}) and skipped — this covers above_sma*, *_above,
    spy_above_*, market_trend, bounce flags, and binary interaction products.

    Args:
        df:           DataFrame with 'date' and feature columns.
        feature_cols: Columns to normalize.
        exclude:      Additional columns to skip (e.g. 'data_quality_score').

    Returns:
        DataFrame with normalized feature columns; date and ticker unchanged.
    """
    skip = set(exclude or []) | {"data_quality_score"}
    candidates = [c for c in feature_cols if c not in skip and c in df.columns]

    # Detect binary / flag columns by their value set and exclude them.
    flag_values = {-1.0, 0.0, 1.0}
    to_normalize = []
    for c in candidates:
        vals = df[c].dropna().unique()
        if len(vals) > 0 and set(vals).issubset(flag_values):
            continue  # binary / ternary flag — leave unchanged
        to_normalize.append(c)

    if not to_normalize:
        return df

    df = df.copy()
    df[to_normalize] = df.groupby("date")[to_normalize].rank(pct=True)
    return df
