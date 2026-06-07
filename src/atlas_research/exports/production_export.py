"""
Production export — Phase 1.

Generates the current-day feature output consumed by Atlas Alpha.
Persists each export to production_exports and returns the payload.

Phase-1 export shape (per ticker):
{
  "date": "2026-06-06",
  "ticker": "AAPL",
  "features": {
      "return_5d": 0.021,
      "rsi_14": 58.3,
      ...all 23 Phase-1 features...
  },
  "topDrivers": ["rs_spy_60", "distance_sma50", "volume_ratio_20"],
  "dataQuality": {
      "featuresPresent": 23,
      "featuresMissing": 0,
      "barsAvailable": 300
  },
  "similaritySummary": null
}

The similaritySummary field is always null in Phase 1.
It will be populated in Phase 3 when the similarity engine exists.

Atlas Alpha currently consumes /api/stock/:ticker/analysis.
This export is the future replacement — a clean, ML-generated signal
that Atlas Alpha will read instead of computing its own scores.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pandas as pd

from atlas_research.db import repository
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)

# Features sorted by typical importance for topDrivers ranking.
# Phase 1: ranked by domain knowledge; Phase 2: replaced by SHAP values.
_DRIVER_PRIORITY = [
    "rs_spy_60",
    "rs_spy_120",
    "rs_spy_20",
    "distance_sma200",
    "distance_sma50",
    "distance_sma20",
    "volume_ratio_20",
    "realized_vol_20",
    "rsi_14",
    "macd_histogram",
    "return_20d",
    "return_60d",
    "roc_20",
    "atr_14",
    "dollar_volume_20",
]


def run_export(
    export_date: date,
    *,
    feature_version: str = "v1",
    persist: bool = True,
) -> list[dict]:
    """
    Build the production export for all tickers on export_date.

    Args:
        export_date:     Date to export (usually today).
        feature_version: Feature version tag.
        persist:         If True, write to production_exports table.

    Returns:
        List of per-ticker export dicts.
    """
    log.info("export.started", date=str(export_date))

    # Load all features for the date (long format)
    long_df = repository.get_features_for_date(export_date, version=feature_version)
    if long_df.empty:
        log.warning("export.no_features", date=str(export_date))
        return []

    tickers = long_df["ticker"].unique().tolist()
    log.info("export.tickers", count=len(tickers), date=str(export_date))

    payload_list = []
    for ticker in sorted(tickers):
        ticker_df = long_df[long_df["ticker"] == ticker]
        feature_dict = dict(zip(ticker_df["feature_name"], ticker_df["feature_value"]))

        record = _build_ticker_record(ticker, export_date, feature_dict)
        payload_list.append(record)

    if persist and payload_list:
        export_id = repository.insert_production_export(
            export_date=export_date,
            export_type="feature_snapshot_v1",
            payload=payload_list,
        )
        log.info("export.persisted", id=export_id, tickers=len(payload_list))

    log.info("export.complete", date=str(export_date), records=len(payload_list))
    return payload_list


def export_single_ticker(
    ticker: str,
    export_date: date,
    feature_version: str = "v1",
) -> dict | None:
    """
    Build and return the export record for a single ticker.
    Does not persist to the database.
    """
    long_df = repository.get_features_for_date(export_date, version=feature_version)
    if long_df.empty:
        return None

    ticker_df = long_df[long_df["ticker"] == ticker]
    if ticker_df.empty:
        return None

    feature_dict = dict(zip(ticker_df["feature_name"], ticker_df["feature_value"]))
    return _build_ticker_record(ticker, export_date, feature_dict)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_ticker_record(
    ticker: str,
    export_date: date,
    features: dict[str, float | None],
) -> dict:
    """Build the export dict for one ticker."""

    # Count data quality metrics
    present  = sum(1 for v in features.values() if v is not None)
    missing  = sum(1 for v in features.values() if v is None)

    # Top drivers: features with non-null values ranked by domain priority
    top_drivers = [
        f for f in _DRIVER_PRIORITY
        if features.get(f) is not None
    ][:3]

    return {
        "date":       export_date.isoformat(),
        "ticker":     ticker,
        "features":   {k: _round(v) for k, v in sorted(features.items())},
        "topDrivers": top_drivers,
        "dataQuality": {
            "featuresPresent": present,
            "featuresMissing": missing,
        },
        # Phase 3: will be populated by similarity engine
        "similaritySummary": None,
    }


def _round(v: float | None, decimals: int = 6) -> float | None:
    if v is None:
        return None
    try:
        return round(float(v), decimals)
    except (TypeError, ValueError):
        return None
