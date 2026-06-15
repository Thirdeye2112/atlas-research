"""
Repository — single place for all database reads and writes.

All pipeline modules call functions here instead of writing SQL inline.
This keeps SQL in one file and makes the pipeline modules testable
by mocking the repository.

Key design:
  - EAV writes: upsert_features() takes a dict and explodes it to rows
  - Wide reads:  get_feature_matrix() pivots EAV → wide DataFrame for ML
  - All writes use INSERT ... ON CONFLICT DO UPDATE (idempotent)
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import text

from atlas_research.db.connection import get_connection
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)


# =============================================================
# securities
# =============================================================

def upsert_securities(rows: list[dict]) -> int:
    """
    Insert or update securities.
    rows: list of dicts with keys: ticker, name, sector, industry, exchange.
    Returns number of rows affected.
    """
    if not rows:
        return 0
    sql = text("""
        INSERT INTO securities (ticker, name, sector, industry, exchange, active)
        VALUES (:ticker, :name, :sector, :industry, :exchange, true)
        ON CONFLICT (ticker) DO UPDATE SET
            name     = EXCLUDED.name,
            sector   = EXCLUDED.sector,
            industry = EXCLUDED.industry,
            exchange = EXCLUDED.exchange,
            active   = true
    """)
    with get_connection() as conn:
        result = conn.execute(sql, rows)
    return result.rowcount


def get_active_tickers() -> list[str]:
    """Return all active tickers from the securities table."""
    sql = text("SELECT ticker FROM securities WHERE active = true ORDER BY ticker")
    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()
    return [r[0] for r in rows]


def set_ticker_inactive(ticker: str) -> None:
    """Mark a ticker as inactive (e.g. delisted)."""
    with get_connection() as conn:
        conn.execute(
            text("UPDATE securities SET active = false WHERE ticker = :ticker"),
            {"ticker": ticker},
        )


# =============================================================
# raw_bars
# =============================================================

def upsert_bars(rows: list[dict]) -> int:
    """
    Upsert OHLCV rows into raw_bars.
    rows: list of dicts with keys matching raw_bars columns.
    Returns number of rows processed.
    """
    if not rows:
        return 0
    sql = text("""
        INSERT INTO raw_bars
            (ticker, date, open, high, low, close, adjusted_close, volume, source)
        VALUES
            (:ticker, :date, :open, :high, :low, :close, :adjusted_close, :volume, :source)
        ON CONFLICT (ticker, date) DO UPDATE SET
            open           = EXCLUDED.open,
            high           = EXCLUDED.high,
            low            = EXCLUDED.low,
            close          = EXCLUDED.close,
            adjusted_close = EXCLUDED.adjusted_close,
            volume         = EXCLUDED.volume,
            source         = EXCLUDED.source
    """)
    with get_connection() as conn:
        conn.execute(sql, rows)
    return len(rows)


def get_bars(ticker: str, start: date | None = None, end: date | None = None) -> pd.DataFrame:
    """
    Return raw_bars for a ticker as a DataFrame.
    Sorted ascending by date.  adjusted_close is the canonical price.
    """
    where = "WHERE ticker = :ticker"
    params: dict = {"ticker": ticker}
    if start:
        where += " AND date >= :start"
        params["start"] = start
    if end:
        where += " AND date <= :end"
        params["end"] = end

    sql = text(f"""
        SELECT date, open, high, low, close, adjusted_close, volume
        FROM raw_bars
        {where}
        ORDER BY date ASC
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    if not rows:
        return pd.DataFrame(columns=["date","open","high","low","close","adjusted_close","volume"])

    df = pd.DataFrame(rows, columns=["date","open","high","low","close","adjusted_close","volume"])
    # Keep date as Python date objects (not Timestamps) for consistency.
    # validate_bars, feature_factory, and label_factory all expect date objects.
    df["date"] = df["date"].apply(lambda d: d.date() if hasattr(d, "date") and callable(d.date) else d)
    return df


def get_latest_bar_date(ticker: str) -> date | None:
    """Return the most recent date in raw_bars for a ticker."""
    sql = text("SELECT MAX(date) FROM raw_bars WHERE ticker = :ticker")
    with get_connection() as conn:
        result = conn.execute(sql, {"ticker": ticker}).scalar()
    return result


def get_all_tickers_latest_date() -> dict[str, date]:
    """Return {ticker: max_date} for all tickers in raw_bars."""
    sql = text("SELECT ticker, MAX(date) AS max_date FROM raw_bars GROUP BY ticker")
    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()
    return {r[0]: r[1] for r in rows}


# =============================================================
# feature_snapshots  (EAV)
# =============================================================

def upsert_features(ticker: str, snap_date: date, features: dict[str, float | None],
                    version: str = "v1", snapshot_version: str | None = None) -> int:
    """
    Write a feature dict to the EAV feature_snapshots table.
    Each key in `features` becomes one row.

    Args:
        ticker:           Ticker symbol.
        snap_date:        Snapshot date.
        features:         Dict of feature_name → value.
        version:          Feature schema version (e.g. 'v1').
        snapshot_version: Pipeline run tag for reproducibility
                          (e.g. 'run_2026-06-06').  None is acceptable.

    Returns:
        Number of rows upserted.
    """
    if not features:
        return 0

    def _to_py_float(v):
        """Convert numpy scalar → plain Python float (or None).
        psycopg2 cannot bind np.float64 directly — it serialises as
        the string 'np.float64(...)' which Postgres rejects."""
        if v is None:
            return None
        try:
            import math
            f = float(v)
            return None if (math.isnan(f) or math.isinf(f)) else f
        except (TypeError, ValueError):
            return None

    rows = [
        {
            "ticker":           ticker,
            "date":             snap_date,
            "feature_name":     name,
            "feature_value":    _to_py_float(value),
            "feature_version":  version,
            "snapshot_version": snapshot_version,
        }
        for name, value in features.items()
    ]

    sql = text("""
        INSERT INTO feature_snapshots
            (ticker, date, feature_name, feature_value, feature_version, snapshot_version)
        VALUES
            (:ticker, :date, :feature_name, :feature_value, :feature_version, :snapshot_version)
        ON CONFLICT (ticker, date, feature_name, feature_version) DO UPDATE SET
            feature_value    = EXCLUDED.feature_value,
            snapshot_version = EXCLUDED.snapshot_version
    """)
    with get_connection() as conn:
        conn.execute(sql, rows)
    return len(rows)


# =============================================================
# feature_metadata
# =============================================================

def upsert_feature_metadata(entries: list[dict]) -> int:
    """
    Upsert feature_metadata rows from settings.FEATURE_METADATA.
    Called by init_db.py to seed the registry.
    Also called at pipeline startup to register any new features.

    entries keys: feature_name, category, source_module, description, data_type.
    Returns number of rows affected.
    """
    if not entries:
        return 0
    sql = text("""
        INSERT INTO feature_metadata
            (feature_name, category, source_module, description, data_type, active)
        VALUES
            (:feature_name, :category, :source_module, :description, :data_type, true)
        ON CONFLICT (feature_name) DO UPDATE SET
            category      = EXCLUDED.category,
            source_module = EXCLUDED.source_module,
            description   = EXCLUDED.description,
            data_type     = EXCLUDED.data_type,
            active        = true
    """)
    with get_connection() as conn:
        conn.execute(sql, entries)
    return len(entries)


def get_active_features(version: str = "v1") -> list[str]:
    """Return list of active feature names from feature_metadata."""
    sql = text("""
        SELECT feature_name FROM feature_metadata
        WHERE active = true
        ORDER BY category, feature_name
    """)
    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()
    return [r[0] for r in rows]


def get_features_for_date(snap_date: date, version: str = "v1") -> pd.DataFrame:
    """
    Return all features for all tickers on a given date.
    Long format: columns = [ticker, feature_name, feature_value].
    """
    sql = text("""
        SELECT ticker, feature_name, feature_value
        FROM feature_snapshots
        WHERE date = :date
          AND feature_version = :version
        ORDER BY ticker, feature_name
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, {"date": snap_date, "version": version}).fetchall()

    return pd.DataFrame(rows, columns=["ticker", "feature_name", "feature_value"])


def get_feature_matrix(snap_date: date, features: list[str],
                       version: str = "v1") -> pd.DataFrame:
    """
    Return a wide ML-ready feature matrix for a given date.
    Rows = tickers, columns = feature names.
    Missing features are NaN.

    This is the pivot: EAV → wide DataFrame.
    """
    long_df = get_features_for_date(snap_date, version)
    if long_df.empty:
        return pd.DataFrame()

    # Filter to requested features only
    long_df = long_df[long_df["feature_name"].isin(features)]

    # Pivot
    wide = long_df.pivot(index="ticker", columns="feature_name", values="feature_value")
    wide = wide.reindex(columns=features)  # enforce column order
    wide.columns.name = None
    return wide.reset_index()


def get_feature_history(ticker: str, feature_name: str,
                        start: date | None = None, end: date | None = None,
                        version: str = "v1") -> pd.DataFrame:
    """Return time series of a single feature for one ticker."""
    where = "WHERE ticker = :ticker AND feature_name = :feature_name AND feature_version = :version"
    params: dict = {"ticker": ticker, "feature_name": feature_name, "version": version}
    if start:
        where += " AND date >= :start"
        params["start"] = start
    if end:
        where += " AND date <= :end"
        params["end"] = end

    sql = text(f"""
        SELECT date, feature_value
        FROM feature_snapshots
        {where}
        ORDER BY date ASC
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return pd.DataFrame(rows, columns=["date", "feature_value"])


# =============================================================
# labels
# =============================================================

def upsert_label(row: dict) -> None:
    """
    Upsert one label row.
    row keys: ticker, date, return_1d, return_5d, return_10d, return_20d,
              return_60d, max_runup_20d, max_drawdown_20d,
              positive_5d, positive_20d.
    """
    sql = text("""
        INSERT INTO labels
            (ticker, date, return_1d, return_5d, return_10d, return_20d,
             return_60d, max_runup_20d, max_drawdown_20d, positive_5d, positive_20d)
        VALUES
            (:ticker, :date, :return_1d, :return_5d, :return_10d, :return_20d,
             :return_60d, :max_runup_20d, :max_drawdown_20d, :positive_5d, :positive_20d)
        ON CONFLICT (ticker, date) DO UPDATE SET
            return_1d        = EXCLUDED.return_1d,
            return_5d        = EXCLUDED.return_5d,
            return_10d       = EXCLUDED.return_10d,
            return_20d       = EXCLUDED.return_20d,
            return_60d       = EXCLUDED.return_60d,
            max_runup_20d    = EXCLUDED.max_runup_20d,
            max_drawdown_20d = EXCLUDED.max_drawdown_20d,
            positive_5d      = EXCLUDED.positive_5d,
            positive_20d     = EXCLUDED.positive_20d
    """)
    with get_connection() as conn:
        conn.execute(sql, row)


def get_labels(snap_date: date) -> pd.DataFrame:
    """Return all label rows for a given date."""
    sql = text("""
        SELECT ticker, return_1d, return_5d, return_10d, return_20d,
               return_60d, max_runup_20d, max_drawdown_20d, positive_5d, positive_20d
        FROM labels
        WHERE date = :date
        ORDER BY ticker
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, {"date": snap_date}).fetchall()
    cols = ["ticker","return_1d","return_5d","return_10d","return_20d",
            "return_60d","max_runup_20d","max_drawdown_20d","positive_5d","positive_20d"]
    return pd.DataFrame(rows, columns=cols)


# =============================================================
# research_runs
# =============================================================

def create_research_run(run_type: str) -> int:
    """Insert a new research_run record and return its id."""
    sql = text("""
        INSERT INTO research_runs (run_type, status)
        VALUES (:run_type, 'running')
        RETURNING id
    """)
    with get_connection() as conn:
        run_id = conn.execute(sql, {"run_type": run_type}).scalar()
    return run_id


def complete_research_run(run_id: int, *, tickers_processed: int = 0,
                           bars_inserted: int = 0, features_generated: int = 0,
                           labels_generated: int = 0, error: str | None = None) -> None:
    """Mark a research_run as complete (or failed)."""
    status = "failed" if error else "complete"
    sql = text("""
        UPDATE research_runs SET
            finished_at        = now(),
            status             = :status,
            tickers_processed  = :tickers_processed,
            bars_inserted      = :bars_inserted,
            features_generated = :features_generated,
            labels_generated   = :labels_generated,
            error_message      = :error_message
        WHERE id = :id
    """)
    with get_connection() as conn:
        conn.execute(sql, {
            "id": run_id,
            "status": status,
            "tickers_processed": tickers_processed,
            "bars_inserted": bars_inserted,
            "features_generated": features_generated,
            "labels_generated": labels_generated,
            "error_message": error,
        })


# =============================================================
# production_exports
# =============================================================

def insert_production_export(export_date: date, export_type: str,
                              payload: dict | list) -> int:
    """
    Persist a production export payload.
    Returns the new row id.
    """
    sql = text("""
        INSERT INTO production_exports (export_date, export_type, payload)
        VALUES (:export_date, :export_type, CAST(:payload AS jsonb))
        RETURNING id
    """)
    with get_connection() as conn:
        row_id = conn.execute(sql, {
            "export_date": export_date,
            "export_type": export_type,
            "payload": json.dumps(payload),
        }).scalar()
    return row_id


def get_latest_export(export_date: date, export_type: str) -> dict | None:
    """Fetch the most recent export payload for a given date and type."""
    sql = text("""
        SELECT payload FROM production_exports
        WHERE export_date = :export_date AND export_type = :export_type
        ORDER BY created_at DESC
        LIMIT 1
    """)
    with get_connection() as conn:
        row = conn.execute(sql, {"export_date": export_date, "export_type": export_type}).fetchone()
    return row[0] if row else None


# =============================================================
# Phase 2 — Training data loading
# =============================================================

def get_training_data(
    start_date: date,
    end_date: date,
    feature_names: list[str],
    target_col: str,
    feature_version: str = "v1",
    min_quality_score: float = 0.70,
) -> pd.DataFrame:
    """
    Load a wide training DataFrame for a date range.

    Joins feature_snapshots (pivoted wide) with labels.
    Applies quality filter: rows with data_quality_score < min_quality_score
    are excluded before returning.

    Returns a DataFrame with columns:
        ticker, date, <feature columns>, data_quality_score, <target_col>

    Rows where the target_col is NULL are dropped.
    The caller is responsible for the purge gap — pass start/end
    dates that already exclude the purge window.
    """
    # Load parquet files for the date range
    # Parquet files are the canonical source for training data because
    # they already contain the pivoted wide matrix with quality scores.
    from config.settings import PARQUET_OUTPUT_DIR
    import os

    parquet_dir = PARQUET_OUTPUT_DIR
    frames = []

    # Walk the date range using parquet files
    current = start_date
    from datetime import timedelta
    while current <= end_date:
        fpath = parquet_dir / f"feature_matrix_{current.isoformat()}.parquet"
        if fpath.exists():
            try:
                cols_needed = ["ticker", "date"] + feature_names + [target_col]
                df = pd.read_parquet(fpath, engine="pyarrow",
                                     columns=[c for c in cols_needed if c != target_col] +
                                             [target_col])
                frames.append(df)
            except Exception:
                pass
        current += timedelta(days=1)

    if not frames:
        return pd.DataFrame()

    full = pd.concat(frames, ignore_index=True)

    # Quality filter (Q1 resolution)
    if "data_quality_score" in full.columns:
        full = full[full["data_quality_score"] >= min_quality_score]

    # Drop rows where target is missing
    if target_col in full.columns:
        full = full[full[target_col].notna()]

    return full.reset_index(drop=True)


# =============================================================
# Phase 2 — Model registry
# =============================================================

def upsert_model_registry(record: dict) -> int:
    """
    Insert or update a model_registry row.

    record keys (all optional except model_name, model_version, target):
        model_name, model_version, target, horizon,
        training_start, training_end, feature_version,
        feature_names, feature_count, train_rows, val_rows,
        auc, brier, ic, rank_ic, sharpe,
        artifact_path, artifact_hash, hyperparams (dict),
        fold_metrics (list of dicts), promoted, notes.

    Returns the row id.
    """
    import json as _json
    import math as _math
    hyperparams = record.get("hyperparams")
    fold_metrics = record.get("fold_metrics")

    def _sanitise_for_json(obj):
        if isinstance(obj, float):
            return None if (_math.isnan(obj) or _math.isinf(obj)) else obj
        if isinstance(obj, dict):
            return {k: _sanitise_for_json(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitise_for_json(v) for v in obj]
        return obj

    sql = text("""
        INSERT INTO model_registry (
            model_name, model_version, target, horizon,
            training_start, training_end, feature_version,
            feature_names, feature_count, train_rows, val_rows,
            auc, brier, ic, rank_ic, sharpe,
            artifact_path, artifact_hash,
            hyperparams, fold_metrics,
            promoted, notes, feature_set_version
        ) VALUES (
            :model_name, :model_version, :target, :horizon,
            :training_start, :training_end, :feature_version,
            :feature_names, :feature_count, :train_rows, :val_rows,
            :auc, :brier, :ic, :rank_ic, :sharpe,
            :artifact_path, :artifact_hash,
            CAST(:hyperparams AS jsonb), CAST(:fold_metrics AS jsonb),
            :promoted, :notes, :feature_set_version
        )
        ON CONFLICT (model_name, model_version, target, training_end) DO UPDATE SET
            feature_set_version = EXCLUDED.feature_set_version,
            updated_at = now()
        RETURNING id
    """)

    with get_connection() as conn:
        row = conn.execute(sql, {
            "model_name":      record.get("model_name"),
            "model_version":   record.get("model_version", "v1"),
            "target":          record.get("target"),
            "horizon":         record.get("horizon"),
            "training_start":  record.get("training_start"),
            "training_end":    record.get("training_end"),
            "feature_version": record.get("feature_version", "v1"),
            "feature_names":   record.get("feature_names"),
            "feature_count":   record.get("feature_count"),
            "train_rows":      record.get("train_rows"),
            "val_rows":        record.get("val_rows"),
            "auc":             record.get("auc"),
            "brier":           record.get("brier"),
            "ic":              record.get("ic"),
            "rank_ic":         record.get("rank_ic"),
            "sharpe":          record.get("sharpe"),
            "artifact_path":   record.get("artifact_path"),
            "artifact_hash":   record.get("artifact_hash"),
            "hyperparams":     _json.dumps(_sanitise_for_json(hyperparams)) if hyperparams else None,
            "fold_metrics":    _json.dumps(_sanitise_for_json(fold_metrics)) if fold_metrics else None,
            "promoted":            record.get("promoted", False),
            "notes":               record.get("notes"),
            "feature_set_version": record.get("feature_set_version", "v1"),
        }).fetchone()
    return row[0] if row else -1


# =============================================================
# Phase 2 — Predictions
# =============================================================

def upsert_predictions(rows: list[dict]) -> int:
    """
    Upsert model predictions for a batch of tickers.

    row keys: ticker, date, model_name, model_version,
              expected_return, probability_positive,
              expected_drawdown, confidence, rank_percentile.
    """
    if not rows:
        return 0
    sql = text("""
        INSERT INTO predictions (
            ticker, date, model_name, model_version,
            expected_return, probability_positive,
            expected_drawdown, confidence, rank_percentile
        ) VALUES (
            :ticker, :date, :model_name, :model_version,
            :expected_return, :probability_positive,
            :expected_drawdown, :confidence, :rank_percentile
        )
        ON CONFLICT (ticker, date, model_name, model_version) DO UPDATE SET
            expected_return      = EXCLUDED.expected_return,
            probability_positive = EXCLUDED.probability_positive,
            expected_drawdown    = EXCLUDED.expected_drawdown,
            confidence           = EXCLUDED.confidence,
            rank_percentile      = EXCLUDED.rank_percentile
    """)
    with get_connection() as conn:
        conn.execute(sql, rows)
    return len(rows)


def get_predictions(pred_date: date, model_name: str,
                    model_version: str) -> pd.DataFrame:
    """Return predictions for a given date and model."""
    sql = text("""
        SELECT ticker, expected_return, probability_positive,
               expected_drawdown, confidence, rank_percentile
        FROM predictions
        WHERE date = :date
          AND model_name = :model_name
          AND model_version = :model_version
        ORDER BY rank_percentile DESC
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, {
            "date": pred_date,
            "model_name": model_name,
            "model_version": model_version,
        }).fetchall()
    cols = ["ticker", "expected_return", "probability_positive",
            "expected_drawdown", "confidence", "rank_percentile"]
    return pd.DataFrame(rows, columns=cols)


# =============================================================
# Phase 2 — Feature performance
# =============================================================

def upsert_feature_performance(rows: list[dict]) -> int:
    """
    Upsert feature_performance rows for a fold evaluation.

    row keys: feature_name, model_version, target, horizon_days,
              eval_start, eval_end, fold_number,
              spearman_ic, pearson_ic, ic_tstat, mean_ic, ic_std,
              lgbm_gain, lgbm_split.
    """
    if not rows:
        return 0
    sql = text("""
        INSERT INTO feature_performance (
            feature_name, model_version, target, horizon_days,
            eval_start, eval_end, fold_number,
            spearman_ic, pearson_ic, ic_tstat, mean_ic, ic_std,
            lgbm_gain, lgbm_split
        ) VALUES (
            :feature_name, :model_version, :target, :horizon_days,
            :eval_start, :eval_end, :fold_number,
            :spearman_ic, :pearson_ic, :ic_tstat, :mean_ic, :ic_std,
            :lgbm_gain, :lgbm_split
        )
        ON CONFLICT (feature_name, model_version, target,
                     horizon_days, eval_start, eval_end, fold_number)
        DO UPDATE SET
            spearman_ic = EXCLUDED.spearman_ic,
            pearson_ic  = EXCLUDED.pearson_ic,
            ic_tstat    = EXCLUDED.ic_tstat,
            mean_ic     = EXCLUDED.mean_ic,
            ic_std      = EXCLUDED.ic_std,
            lgbm_gain   = EXCLUDED.lgbm_gain,
            lgbm_split  = EXCLUDED.lgbm_split
    """)
    with get_connection() as conn:
        conn.execute(sql, rows)
    return len(rows)
