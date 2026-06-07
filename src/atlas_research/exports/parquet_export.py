"""
Parquet export — nightly wide feature matrix.

Generates:  exports/parquet/feature_matrix_YYYY-MM-DD.parquet

This file is the ML substrate:
    - LightGBM training (Phase 2):  df = pd.read_parquet(...); df = df[df['label_return_5d'].notna()]
    - Jupyter notebooks
    - Walk-forward backtesting
    - Similarity / analog search (Phase 3)

SCHEMA  (one row per ticker, one file per date)
-------
    ticker                TEXT       — primary identifier
    date                  DATE       — snapshot date; same for every row in file
    <feature columns>     FLOAT64    — all Phase-1 + regime features (settings.ALL_FEATURES)
    data_quality_score    FLOAT64    — 1.0 = clean; lower = triggered warnings
    data_quality_flags    TEXT       — pipe-separated warning flag names, e.g. "volume_outlier"
    label_return_5d       FLOAT64    — log forward return; NULL until T+5 bars exist
    label_return_20d      FLOAT64
    label_positive_5d     BOOL
    label_positive_20d    BOOL

LABEL CONTRACT (Q1 resolution)
---------------
Labels are left-joined — one parquet file serves both features-only
and labeled use cases.  Phase 2 training simply filters:
    df_labeled = df[df['label_return_5d'].notna()]
No separate feature-only / labeled split files.

SHAP NOTE (Q3 stub)
----------
The JSON export's topDrivers field is currently domain-knowledge ranked.
Phase 2 replaces this with SHAP mean-absolute values per feature computed
after LightGBM training.  The parquet matrix is the input to that computation.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from atlas_research.utils.logging import get_logger

log = get_logger(__name__)

# Label columns to join from the labels table.
# Prefix 'label_' distinguishes them from feature columns in the wide matrix.
_LABEL_COLS = ["return_5d", "return_20d", "positive_5d", "positive_20d"]


def build_feature_matrix(
    snap_date: date,
    features_long: pd.DataFrame,
    labels_df: pd.DataFrame | None = None,
    feature_names: list[str] | None = None,
    quality_scores: dict[str, float] | None = None,
    quality_flags: dict[str, str]  | None = None,
) -> pd.DataFrame:
    """
    Pivot EAV long-format features to a wide ML matrix.

    Args:
        snap_date:       Date of the snapshot (written as a column).
        features_long:   Long DataFrame: [ticker, feature_name, feature_value].
                         Produced by repository.get_features_for_date().
        labels_df:       Optional labels DataFrame: [ticker, return_5d, ...].
                         Left-joined; columns prefixed with 'label_'.
                         Pass None when labels are not yet available.
        feature_names:   Ordered column list for the wide matrix.
                         Defaults to settings.ALL_FEATURES.
        quality_scores:  {ticker: float} from validation summary.
                         Written as 'data_quality_score' column.
                         Tickers absent from this dict get score 1.0.
        quality_flags:   {ticker: str} pipe-separated flags from validation.
                         Written as 'data_quality_flags' column.
                         Tickers absent get empty string.

    Returns:
        Wide DataFrame (ticker × columns), or empty DataFrame if no data.
    """
    if features_long is None or features_long.empty:
        log.warning("parquet.no_features", date=str(snap_date))
        return pd.DataFrame()

    if feature_names is None:
        from config.settings import ALL_FEATURES
        feature_names = ALL_FEATURES

    # ── Pivot EAV → wide ─────────────────────────────────────
    filtered = features_long[features_long["feature_name"].isin(feature_names)].copy()
    if filtered.empty:
        log.warning("parquet.no_matching_features", date=str(snap_date))
        return pd.DataFrame()

    wide = filtered.pivot(
        index="ticker",
        columns="feature_name",
        values="feature_value",
    )
    wide.columns.name = None
    wide = wide.reindex(columns=feature_names)   # enforce order; missing → NaN
    wide = wide.reset_index()
    wide.insert(1, "date", snap_date)

    # ── Data quality columns ──────────────────────────────────
    # Tickers that passed validation (with or without warnings) appear here.
    # Tickers that failed FATAL checks were never added to feature_snapshots
    # and therefore will not appear in features_long.
    scores = quality_scores or {}
    flags  = quality_flags  or {}

    wide["data_quality_score"] = wide["ticker"].map(
        lambda t: scores.get(t, 1.0)
    ).astype("float64")

    wide["data_quality_flags"] = wide["ticker"].map(
        lambda t: flags.get(t, "")
    ).astype("object")

    # ── Join labels (left — NULL where future bars not yet available) ──
    if labels_df is not None and not labels_df.empty:
        label_cols = ["ticker"] + [c for c in _LABEL_COLS if c in labels_df.columns]
        label_subset = labels_df[label_cols].copy()
        label_subset = label_subset.rename(
            columns={c: f"label_{c}" for c in _LABEL_COLS if c in label_subset.columns}
        )
        wide = wide.merge(label_subset, on="ticker", how="left")

    log.info(
        "parquet.matrix_built",
        date=str(snap_date),
        tickers=len(wide),
        features=len(feature_names),
        has_labels=labels_df is not None and not labels_df.empty,
        quality_scored=bool(scores),
    )
    return wide


def export_parquet(
    snap_date: date,
    matrix: pd.DataFrame,
    output_dir: Path | None = None,
    compression: str | None = None,
) -> Path:
    """
    Write the wide feature matrix to a dated parquet file.

    Raises ValueError if matrix is empty.
    """
    from config import settings

    if matrix is None or matrix.empty:
        raise ValueError(f"Cannot export empty matrix for {snap_date}")

    out_dir = Path(output_dir or settings.PARQUET_OUTPUT_DIR)
    codec   = compression or settings.PARQUET_COMPRESSION
    out_dir.mkdir(parents=True, exist_ok=True)

    filepath = out_dir / f"feature_matrix_{snap_date.isoformat()}.parquet"
    matrix.to_parquet(filepath, engine="pyarrow", compression=codec, index=False)

    size_kb = filepath.stat().st_size // 1024
    log.info(
        "parquet.exported",
        date=str(snap_date),
        path=str(filepath),
        rows=len(matrix),
        size_kb=size_kb,
        compression=codec,
    )
    return filepath


def run_parquet_export(
    snap_date: date,
    *,
    output_dir: Path | None = None,
    feature_version: str = "v1",
    feature_names: list[str] | None = None,
    quality_scores: dict[str, float] | None = None,
    quality_flags: dict[str, str]  | None = None,
) -> Path | None:
    """
    Full parquet export pipeline:
        1. Load features from DB (EAV long format)
        2. Load labels from DB (left-join)
        3. Pivot to wide matrix, attach quality columns
        4. Write parquet file

    quality_scores and quality_flags come from the nightly pipeline's
    validation summary and are threaded through to the matrix builder.
    """
    from atlas_research.db import repository

    log.info("parquet.run_start", date=str(snap_date))

    features_long = repository.get_features_for_date(snap_date, version=feature_version)
    if features_long.empty:
        log.warning("parquet.no_data", date=str(snap_date))
        return None

    try:
        labels_df = repository.get_labels(snap_date)
    except Exception:
        labels_df = None

    matrix = build_feature_matrix(
        snap_date,
        features_long,
        labels_df=labels_df,
        feature_names=feature_names,
        quality_scores=quality_scores,
        quality_flags=quality_flags,
    )
    if matrix.empty:
        return None

    return export_parquet(snap_date, matrix, output_dir=output_dir)


def load_parquet(
    snap_date: date,
    output_dir: Path | None = None,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """
    Load a previously exported parquet file.
    columns= enables columnar pushdown (only load what you need).
    Returns empty DataFrame if the file does not exist.
    """
    from config import settings

    filepath = Path(output_dir or settings.PARQUET_OUTPUT_DIR) / \
               f"feature_matrix_{snap_date.isoformat()}.parquet"

    if not filepath.exists():
        log.warning("parquet.file_not_found", path=str(filepath))
        return pd.DataFrame()

    df = pd.read_parquet(filepath, engine="pyarrow", columns=columns)
    log.info("parquet.loaded", date=str(snap_date), rows=len(df), path=str(filepath))
    return df
