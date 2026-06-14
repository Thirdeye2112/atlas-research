"""
wide_export.py — Pivot EAV feature_snapshots → feature_snapshots_wide.

EAV remains the source of truth. This is a read-optimized denormalization
for model training, scanner reads, and prediction reads.

Nightly refresh: called after features are written to EAV.
Full backfill: refresh_wide_all(db_url)
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch

from atlas_research.utils.logging import get_logger

log = get_logger(__name__)

# All features that appear as rows in feature_snapshots (EAV).
# Imported from settings to stay in sync with the pipeline.
from config.settings import ALL_FEATURES

# Extra quality columns written to EAV by feature_factory and validate step.
_QUALITY_COLS = ["quality_tier", "jarvis_quality_adjusted", "data_quality_score"]

# Complete set of feature columns in feature_snapshots_wide.
WIDE_FEATURES: list[str] = ALL_FEATURES + _QUALITY_COLS

# Table schema column order (excludes metadata columns ticker, date, snapshot_version,
# feature_version, refreshed_at). Must match feature_snapshots_wide DDL exactly.
_SCHEMA_FEATURE_COLS: list[str] = WIDE_FEATURES


def refresh_wide(
    run_date: date,
    db_url: str,
    feature_version: str = "v1",
) -> int:
    """
    Pivot EAV rows for run_date into feature_snapshots_wide.

    Reads only the latest snapshot_version per (ticker, date).
    Returns number of rows upserted.
    """
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT fs.ticker, fs.date, fs.feature_name,
                       fs.feature_value, fs.snapshot_version
                FROM feature_snapshots fs
                INNER JOIN (
                    SELECT ticker, date, MAX(snapshot_version) AS snap_ver
                    FROM feature_snapshots
                    WHERE date = %s
                    GROUP BY ticker, date
                ) latest
                  ON fs.ticker          = latest.ticker
                 AND fs.date            = latest.date
                 AND fs.snapshot_version = latest.snap_ver
                WHERE fs.date = %s
            """, (run_date, run_date))
            rows = cur.fetchall()

    if not rows:
        log.info("wide_export.no_eav_rows", date=str(run_date))
        return 0

    df = pd.DataFrame(rows, columns=[
        "ticker", "date", "feature_name", "feature_value", "snapshot_version"
    ])

    wide = (
        df.pivot_table(
            index=["ticker", "date", "snapshot_version"],
            columns="feature_name",
            values="feature_value",
            aggfunc="first",
        )
        .reset_index()
    )
    wide.columns.name = None
    wide["feature_version"] = feature_version

    n = _upsert_wide(wide, db_url)
    log.info("wide_export.refresh_done", date=str(run_date), n_rows=n)
    return n


def refresh_wide_all(db_url: str, feature_version: str = "v1") -> dict[str, int]:
    """
    Full refresh — pivot EAV for every distinct date → upsert into wide table.
    Returns {date_str: n_rows}.
    """
    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT date FROM feature_snapshots ORDER BY date")
            dates = [r[0] for r in cur.fetchall()]

    log.info("wide_export.full_refresh_start", n_dates=len(dates))
    results: dict[str, int] = {}
    for d in dates:
        n = refresh_wide(d, db_url, feature_version=feature_version)
        results[str(d)] = n

    total = sum(results.values())
    log.info("wide_export.full_refresh_done", n_dates=len(results), total_rows=total)
    return results


def load_wide(
    db_url: str,
    start_date: date | None = None,
    end_date: date | None = None,
    quality_tier: int | None = None,
    feature_cols: list[str] | None = None,
) -> pd.DataFrame:
    """
    Read from feature_snapshots_wide into a pandas DataFrame.

    Args:
        start_date:    Inclusive lower bound on date. None = no lower bound.
        end_date:      Inclusive upper bound on date. None = no upper bound.
        quality_tier:  Filter to a specific tier (1-4). None = all tiers.
        feature_cols:  Subset of columns to read. None = all feature columns.

    Returns:
        DataFrame with columns [ticker, date, <feature_cols>, quality_tier,
        data_quality_score, feature_version].
    """
    cols = feature_cols or _SCHEMA_FEATURE_COLS
    select_cols = ["ticker", "date"] + [c for c in cols if c not in ("ticker", "date")]
    select_str = ", ".join(select_cols)

    conditions = []
    params: list = []
    if start_date is not None:
        conditions.append("date >= %s")
        params.append(start_date)
    if end_date is not None:
        conditions.append("date <= %s")
        params.append(end_date)
    if quality_tier is not None:
        conditions.append("quality_tier = %s")
        params.append(float(quality_tier))

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"SELECT {select_str} FROM feature_snapshots_wide {where} ORDER BY date, ticker"

    with psycopg2.connect(db_url) as conn:
        return pd.read_sql_query(sql, conn, params=params if params else None)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _upsert_wide(wide: pd.DataFrame, db_url: str) -> int:
    """Upsert pivoted wide DataFrame into feature_snapshots_wide."""
    if wide.empty:
        return 0

    # Only upsert columns that exist in the schema
    available_feat = [c for c in _SCHEMA_FEATURE_COLS if c in wide.columns]
    meta_cols = ["ticker", "date", "snapshot_version", "feature_version"]

    all_insert_cols = meta_cols + available_feat
    col_str = ", ".join(all_insert_cols) + ", refreshed_at"
    val_str = ", ".join(["%s"] * len(all_insert_cols)) + ", now()"
    update_str = (
        ", ".join(f"{c} = EXCLUDED.{c}"
                  for c in ["snapshot_version", "feature_version"] + available_feat)
        + ", refreshed_at = now()"
    )

    sql = (
        f"INSERT INTO feature_snapshots_wide ({col_str}) "
        f"VALUES ({val_str}) "
        f"ON CONFLICT (ticker, date) DO UPDATE SET {update_str}"
    )

    data: list[tuple] = []
    for _, row in wide.iterrows():
        vals: list = [
            row["ticker"],
            row["date"],
            row.get("snapshot_version"),
            row.get("feature_version", "v1"),
        ]
        for feat in available_feat:
            v = row.get(feat)
            if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
                vals.append(None)
            else:
                vals.append(float(v))
        data.append(tuple(vals))

    with psycopg2.connect(db_url) as conn:
        with conn.cursor() as cur:
            execute_batch(cur, sql, data, page_size=500)
        conn.commit()

    return len(data)
