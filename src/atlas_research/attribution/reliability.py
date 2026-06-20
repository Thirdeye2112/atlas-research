"""
Signal reliability engine — computes rolling hit rate, avg return, and IC
per component across multiple windows (30/90/180 days), market regimes,
and quality tiers.

Reads from prediction_outcomes + confluence_score_components.
Writes to signal_reliability_scores.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sqlalchemy import text

from atlas_research.attribution import repository
from atlas_research.db.connection import get_connection
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)

COMPONENTS   = ["ml", "pattern", "probability", "feature_ic", "regime"]
WINDOWS      = [30, 90, 180]
HORIZONS     = [5]
REGIMES      = [None, "bull_market", "bear_market", "high_vol", "low_vol"]
QUALITY_TIERS = [None, "VERY_HIGH", "HIGH", "MODERATE", "LOW"]
MIN_SAMPLE   = 30
TREND_DELTA  = 0.02   # 2pp change = trend shift


def compute_signal_reliability(
    as_of: date | None = None,
    windows: list[int] = WINDOWS,
    horizons: list[int] = HORIZONS,
) -> dict[str, int]:
    """
    Compute and upsert signal_reliability_scores for all components.

    Returns
    -------
    Dict mapping 'component_name' → number of rows written.
    """
    if as_of is None:
        as_of = date.today()

    # Load all matured outcomes up to the longest window
    max_window = max(windows)
    start_date = as_of - timedelta(days=max_window + 30)  # buffer for lookback

    df = _load_component_outcomes(start_date, as_of)
    if df.empty:
        log.info("attribution.reliability.no_data", as_of=str(as_of))
        return {}

    totals: dict[str, int] = {c: 0 for c in COMPONENTS}

    for component in COMPONENTS:
        comp_df = df[df["component_name"] == component].copy()
        if comp_df.empty:
            continue

        for window in windows:
            window_start = as_of - timedelta(days=window)
            w_df = comp_df[comp_df["prediction_date"] >= window_start].copy()

            for regime in REGIMES:
                for tier in QUALITY_TIERS:
                    subset = _filter(w_df, regime, tier)
                    for direction in ["all", "bullish", "bearish"]:
                        dir_df = _filter_direction(subset, direction)
                        if len(dir_df) < MIN_SAMPLE:
                            continue

                        metrics = _compute_metrics(dir_df)

                        # Trend: compare to prior same-length window
                        prior_start = window_start - timedelta(days=window)
                        prior_df = _filter(
                            comp_df[
                                (comp_df["prediction_date"] >= prior_start) &
                                (comp_df["prediction_date"] < window_start)
                            ],
                            regime, tier,
                        )
                        prior_df = _filter_direction(prior_df, direction)
                        prior_hr = float(prior_df["hit_or_miss"].mean()) if len(prior_df) >= MIN_SAMPLE else None
                        delta    = (metrics["hit_rate"] - prior_hr) if prior_hr is not None else None
                        trend    = _classify_trend(delta)

                        for horizon in horizons:
                            row: dict[str, Any] = {
                                "computed_date":      as_of,
                                "component_name":     component,
                                "signal_direction":   direction,
                                "window_days":        window,
                                "regime_filter":      regime,
                                "quality_tier_filter": tier,
                                "horizon_days":       horizon,
                                "n_predictions":      metrics["n"],
                                "n_hits":             metrics["n_hits"],
                                "hit_rate":           metrics["hit_rate"],
                                "avg_return":         metrics["avg_return"],
                                "ic":                 metrics["ic"],
                                "prior_hit_rate":     prior_hr,
                                "hit_rate_delta":     delta,
                                "trend":              trend,
                            }
                            try:
                                repository.upsert_reliability(row)
                                totals[component] += 1
                            except Exception as exc:
                                log.warning("attribution.reliability.skip",
                                            component=component, error=str(exc))

    log.info("attribution.reliability.complete",
             as_of=str(as_of), totals=totals)
    return totals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_component_outcomes(start_date: date, end_date: date) -> pd.DataFrame:
    """
    Join prediction_outcomes with confluence_score_components to get per-component
    hit/miss data. Falls back to aggregate outcomes if no snapshot_id available.
    """
    sql = text("""
        SELECT
            po.prediction_date,
            po.ticker,
            po.predicted_direction,
            po.actual_return,
            po.hit_or_miss,
            po.regime,
            po.vol_regime,
            po.conviction_level,
            po.horizon_days,
            COALESCE(csc.component_name, 'aggregate') AS component_name,
            COALESCE(csc.signal, po.predicted_direction) AS component_signal,
            COALESCE(csc.strength, 0.5)                  AS component_strength
        FROM prediction_outcomes po
        LEFT JOIN confluence_score_components csc
            ON csc.snapshot_id = po.snapshot_id
            AND csc.component_name != 'risk'
        WHERE po.prediction_date BETWEEN :start AND :end
          AND po.hit_or_miss IS NOT NULL
          AND po.horizon_days = 5
        ORDER BY po.prediction_date DESC
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, {"start": start_date, "end": end_date}).fetchall()

    cols = [
        "prediction_date", "ticker", "predicted_direction",
        "actual_return", "hit_or_miss", "regime", "vol_regime",
        "conviction_level", "horizon_days",
        "component_name", "component_signal", "component_strength",
    ]
    df = pd.DataFrame(rows, columns=cols)
    df["prediction_date"] = pd.to_datetime(df["prediction_date"]).dt.date
    df["hit_or_miss"]     = df["hit_or_miss"].astype(bool)
    df["actual_return"]   = pd.to_numeric(df["actual_return"], errors="coerce")
    df["component_strength"] = pd.to_numeric(df["component_strength"], errors="coerce").fillna(0.5)

    # For component-level hit: component fired in same direction as actual outcome
    # component_signal should match actual_direction
    # actual_direction is implied by actual_return > 0 → 'up' → 'bullish'
    df["actual_bullish"] = df["actual_return"] > 0
    df["comp_bullish"]   = df["component_signal"] == "bullish"
    df["comp_bearish"]   = df["component_signal"] == "bearish"
    df["comp_directional"] = df["component_signal"].isin(["bullish", "bearish"])
    df["comp_hit"] = (
        (df["comp_bullish"] & df["actual_bullish"]) |
        (df["comp_bearish"] & ~df["actual_bullish"])
    )
    return df


def _filter(df: pd.DataFrame, regime: str | None, tier: str | None) -> pd.DataFrame:
    out = df
    if regime:
        out = out[out["regime"] == regime]
    if tier:
        out = out[out["conviction_level"] == tier]
    return out


def _filter_direction(df: pd.DataFrame, direction: str) -> pd.DataFrame:
    if direction == "all":
        return df[df["comp_directional"]]
    return df[df["component_signal"] == direction]


def _compute_metrics(df: pd.DataFrame) -> dict[str, Any]:
    n     = len(df)
    n_hits = int(df["comp_hit"].sum())
    hit_rate  = float(df["comp_hit"].mean())
    avg_return = float(df["actual_return"].mean()) if "actual_return" in df else float("nan")

    # Spearman IC: component_strength vs actual_return
    ic = float("nan")
    valid = df[["component_strength", "actual_return"]].dropna()
    if len(valid) >= MIN_SAMPLE:
        rho, _ = spearmanr(valid["component_strength"], valid["actual_return"])
        ic = float(rho) if not math.isnan(rho) else float("nan")

    return {
        "n":          n,
        "n_hits":     n_hits,
        "hit_rate":   hit_rate,
        "avg_return": avg_return,
        "ic":         ic,
    }


def _classify_trend(delta: float | None) -> str:
    if delta is None:
        return "stable"
    if delta > TREND_DELTA:
        return "improving"
    if delta < -TREND_DELTA:
        return "degrading"
    return "stable"
