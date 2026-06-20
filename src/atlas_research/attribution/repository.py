"""
DB reads and writes for the attribution system.
All SQL is raw; SQLAlchemy used only for connection/transaction management.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import text

from atlas_research.db.connection import get_connection
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# prediction_outcomes
# ---------------------------------------------------------------------------

def upsert_prediction(row: dict[str, Any]) -> int:
    """Insert or update a prediction_outcomes record. Returns id."""
    sql = text("""
        INSERT INTO prediction_outcomes (
            ticker, prediction_date, horizon_days,
            predicted_direction, predicted_probability, expected_return,
            confluence_score, conviction_level, conviction_score,
            aligned_count, conflicting_count, neutral_count,
            aligned_signals, conflicting_signals, neutral_signals,
            regime, vol_regime, quality_tier,
            feature_set_version, model_version, engine_version,
            snapshot_id
        ) VALUES (
            :ticker, :prediction_date, :horizon_days,
            :predicted_direction, :predicted_probability, :expected_return,
            :confluence_score, :conviction_level, :conviction_score,
            :aligned_count, :conflicting_count, :neutral_count,
            :aligned_signals, :conflicting_signals, :neutral_signals,
            :regime, :vol_regime, :quality_tier,
            :feature_set_version, :model_version, :engine_version,
            :snapshot_id
        )
        ON CONFLICT (ticker, prediction_date, horizon_days, engine_version) DO UPDATE SET
            predicted_direction   = EXCLUDED.predicted_direction,
            predicted_probability = EXCLUDED.predicted_probability,
            expected_return       = EXCLUDED.expected_return,
            confluence_score      = EXCLUDED.confluence_score,
            conviction_level      = EXCLUDED.conviction_level,
            conviction_score      = EXCLUDED.conviction_score,
            aligned_count         = EXCLUDED.aligned_count,
            conflicting_count     = EXCLUDED.conflicting_count,
            neutral_count         = EXCLUDED.neutral_count,
            aligned_signals       = EXCLUDED.aligned_signals,
            conflicting_signals   = EXCLUDED.conflicting_signals,
            neutral_signals       = EXCLUDED.neutral_signals,
            regime                = EXCLUDED.regime,
            vol_regime            = EXCLUDED.vol_regime,
            quality_tier          = EXCLUDED.quality_tier,
            snapshot_id           = EXCLUDED.snapshot_id
        RETURNING id
    """)
    with get_connection() as conn:
        result = conn.execute(sql, row).fetchone()
    return int(result[0])


def update_outcome(
    outcome_id: int,
    outcome_date: date,
    actual_return: float | None,
    actual_direction: str,
    hit_or_miss: bool | None,
    prediction_error: float | None,
    max_runup: float | None,
    max_drawdown: float | None,
) -> None:
    """Fill in realized outcome fields for a matured prediction."""
    sql = text("""
        UPDATE prediction_outcomes SET
            outcome_date         = :outcome_date,
            actual_return        = :actual_return,
            actual_direction     = :actual_direction,
            hit_or_miss          = :hit_or_miss,
            prediction_error     = :prediction_error,
            max_runup            = :max_runup,
            max_drawdown         = :max_drawdown,
            outcome_computed_at  = now()
        WHERE id = :outcome_id
    """)
    with get_connection() as conn:
        conn.execute(sql, {
            "outcome_id": outcome_id,
            "outcome_date": outcome_date,
            "actual_return": actual_return,
            "actual_direction": actual_direction,
            "hit_or_miss": hit_or_miss,
            "prediction_error": prediction_error,
            "max_runup": max_runup,
            "max_drawdown": max_drawdown,
        })


def get_pending_outcomes(horizon_days: int, as_of: date) -> pd.DataFrame:
    """Return predictions whose horizon has elapsed but outcome not yet computed."""
    sql = text("""
        SELECT
            po.id,
            po.ticker,
            po.prediction_date,
            po.horizon_days,
            po.predicted_direction,
            po.predicted_probability,
            po.confluence_score,
            po.conviction_level,
            po.aligned_count,
            po.conflicting_count,
            po.regime,
            po.vol_regime,
            po.snapshot_id,
            -- Outcome data (from labels)
            l.return_5d,
            l.return_10d,
            l.return_20d,
            l.max_runup_20d,
            l.max_drawdown_20d,
            l.positive_5d
        FROM prediction_outcomes po
        LEFT JOIN labels l
            ON l.ticker = po.ticker
            AND l.date  = po.prediction_date
        WHERE po.outcome_computed_at IS NULL
          AND po.horizon_days = :horizon
          AND po.prediction_date <= :cutoff
        ORDER BY po.prediction_date ASC
        LIMIT 50000
    """)
    cutoff = date(as_of.year, as_of.month, as_of.day)
    from datetime import timedelta
    # Outcome available once horizon_days + buffer have elapsed
    cutoff = date.fromordinal(cutoff.toordinal() - horizon_days)
    with get_connection() as conn:
        rows = conn.execute(sql, {"horizon": horizon_days, "cutoff": cutoff}).fetchall()
    cols = [
        "id", "ticker", "prediction_date", "horizon_days",
        "predicted_direction", "predicted_probability",
        "confluence_score", "conviction_level",
        "aligned_count", "conflicting_count",
        "regime", "vol_regime", "snapshot_id",
        "return_5d", "return_10d", "return_20d",
        "max_runup_20d", "max_drawdown_20d", "positive_5d",
    ]
    return pd.DataFrame(rows, columns=cols)


def get_matured_outcomes_without_attribution(limit: int = 10000) -> pd.DataFrame:
    """Return matured predictions that haven't been attributed yet."""
    sql = text("""
        SELECT
            po.id AS outcome_id,
            po.ticker,
            po.prediction_date,
            po.horizon_days,
            po.predicted_direction,
            po.predicted_probability,
            po.expected_return,
            po.confluence_score,
            po.conviction_level,
            po.aligned_count,
            po.conflicting_count,
            po.neutral_count,
            po.regime,
            po.vol_regime,
            po.actual_return,
            po.actual_direction,
            po.hit_or_miss,
            po.max_runup,
            po.max_drawdown,
            po.snapshot_id
        FROM prediction_outcomes po
        WHERE po.outcome_computed_at IS NOT NULL
          AND po.id NOT IN (
              SELECT outcome_id FROM prediction_error_attribution WHERE is_primary = true
          )
        ORDER BY po.prediction_date ASC
        LIMIT :limit
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, {"limit": limit}).fetchall()
    cols = [
        "outcome_id", "ticker", "prediction_date", "horizon_days",
        "predicted_direction", "predicted_probability", "expected_return",
        "confluence_score", "conviction_level",
        "aligned_count", "conflicting_count", "neutral_count",
        "regime", "vol_regime",
        "actual_return", "actual_direction", "hit_or_miss",
        "max_runup", "max_drawdown", "snapshot_id",
    ]
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------
# prediction_error_attribution
# ---------------------------------------------------------------------------

def insert_attribution(row: dict[str, Any]) -> None:
    sql = text("""
        INSERT INTO prediction_error_attribution (
            outcome_id, ticker, prediction_date, horizon_days,
            hit_or_miss, failure_class, confidence, details, is_primary
        ) VALUES (
            :outcome_id, :ticker, :prediction_date, :horizon_days,
            :hit_or_miss, :failure_class, :confidence, :details::jsonb, :is_primary
        )
        ON CONFLICT DO NOTHING
    """)
    with get_connection() as conn:
        conn.execute(sql, {
            **row,
            "details": json.dumps(row.get("details") or {}),
        })


def get_attribution_summary(
    start_date: date,
    end_date: date,
    horizon_days: int = 5,
) -> pd.DataFrame:
    """Aggregate failure class counts over a date range."""
    sql = text("""
        SELECT
            a.failure_class,
            COUNT(*)                                AS n_total,
            SUM(CASE WHEN NOT a.hit_or_miss THEN 1 ELSE 0 END) AS n_misses,
            AVG(a.confidence)                       AS avg_confidence,
            MIN(po.prediction_date)::text           AS earliest,
            MAX(po.prediction_date)::text           AS latest
        FROM prediction_error_attribution a
        JOIN prediction_outcomes po ON po.id = a.outcome_id
        WHERE a.is_primary = true
          AND po.prediction_date BETWEEN :start AND :end
          AND po.horizon_days = :horizon
        GROUP BY a.failure_class
        ORDER BY n_total DESC
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, {
            "start": start_date, "end": end_date, "horizon": horizon_days,
        }).fetchall()
    cols = ["failure_class", "n_total", "n_misses", "avg_confidence", "earliest", "latest"]
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------
# signal_reliability_scores
# ---------------------------------------------------------------------------

def upsert_reliability(row: dict[str, Any]) -> None:
    sql = text("""
        INSERT INTO signal_reliability_scores (
            computed_date, component_name, signal_direction,
            window_days, regime_filter, quality_tier_filter, horizon_days,
            n_predictions, n_hits, hit_rate, avg_return, ic,
            prior_hit_rate, hit_rate_delta, trend
        ) VALUES (
            :computed_date, :component_name, :signal_direction,
            :window_days, :regime_filter, :quality_tier_filter, :horizon_days,
            :n_predictions, :n_hits, :hit_rate, :avg_return, :ic,
            :prior_hit_rate, :hit_rate_delta, :trend
        )
        ON CONFLICT (computed_date, component_name, signal_direction,
                     window_days, regime_filter, quality_tier_filter, horizon_days)
        DO UPDATE SET
            n_predictions  = EXCLUDED.n_predictions,
            n_hits         = EXCLUDED.n_hits,
            hit_rate       = EXCLUDED.hit_rate,
            avg_return     = EXCLUDED.avg_return,
            ic             = EXCLUDED.ic,
            prior_hit_rate = EXCLUDED.prior_hit_rate,
            hit_rate_delta = EXCLUDED.hit_rate_delta,
            trend          = EXCLUDED.trend,
            computed_at    = now()
    """)
    with get_connection() as conn:
        conn.execute(sql, row)


def get_reliability_snapshot(
    computed_date: date | None = None,
    window_days: int = 90,
    horizon_days: int = 5,
) -> pd.DataFrame:
    """Latest reliability scores for all components."""
    date_clause = "computed_date = :dt" if computed_date else "computed_date = (SELECT MAX(computed_date) FROM signal_reliability_scores)"
    sql = text(f"""
        SELECT
            component_name, signal_direction,
            window_days, regime_filter, quality_tier_filter,
            n_predictions, hit_rate, avg_return, ic,
            prior_hit_rate, hit_rate_delta, trend,
            computed_date::text
        FROM signal_reliability_scores
        WHERE {date_clause}
          AND window_days = :window
          AND horizon_days = :horizon
          AND signal_direction = 'all'
        ORDER BY component_name, regime_filter NULLS FIRST
    """)
    params: dict[str, Any] = {"window": window_days, "horizon": horizon_days}
    if computed_date:
        params["dt"] = computed_date
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    cols = [
        "component_name", "signal_direction", "window_days",
        "regime_filter", "quality_tier_filter",
        "n_predictions", "hit_rate", "avg_return", "ic",
        "prior_hit_rate", "hit_rate_delta", "trend", "computed_date",
    ]
    return pd.DataFrame(rows, columns=cols)


def get_component_reliability_history(
    component_name: str,
    window_days: int = 90,
    days_back: int = 180,
) -> pd.DataFrame:
    sql = text("""
        SELECT
            computed_date::text,
            signal_direction,
            regime_filter,
            n_predictions,
            hit_rate,
            avg_return,
            ic,
            trend
        FROM signal_reliability_scores
        WHERE component_name = :comp
          AND window_days    = :window
          AND horizon_days   = 5
          AND computed_date >= CURRENT_DATE - :days * INTERVAL '1 day'
        ORDER BY computed_date DESC, regime_filter NULLS FIRST
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, {
            "comp": component_name, "window": window_days, "days": days_back,
        }).fetchall()
    cols = ["computed_date", "signal_direction", "regime_filter",
            "n_predictions", "hit_rate", "avg_return", "ic", "trend"]
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------
# adaptive_weight_recommendations
# ---------------------------------------------------------------------------

def insert_recommendation(row: dict[str, Any]) -> int:
    sql = text("""
        INSERT INTO adaptive_weight_recommendations (
            generated_date, component_name, recommendation,
            current_weight, suggested_weight,
            regime_filter, horizon_days, window_days,
            priority, rationale, evidence
        ) VALUES (
            :generated_date, :component_name, :recommendation,
            :current_weight, :suggested_weight,
            :regime_filter, :horizon_days, :window_days,
            :priority, :rationale, :evidence::jsonb
        )
        RETURNING id
    """)
    with get_connection() as conn:
        result = conn.execute(sql, {
            **row,
            "evidence": json.dumps(row.get("evidence") or {}),
        }).fetchone()
    return int(result[0])


def get_pending_recommendations(limit: int = 100) -> pd.DataFrame:
    sql = text("""
        SELECT
            id, generated_date::text, component_name, recommendation,
            current_weight, suggested_weight,
            regime_filter, priority, rationale, evidence,
            created_at::text
        FROM adaptive_weight_recommendations
        WHERE status = 'pending'
        ORDER BY priority DESC, generated_date DESC
        LIMIT :limit
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, {"limit": limit}).fetchall()
    cols = [
        "id", "generated_date", "component_name", "recommendation",
        "current_weight", "suggested_weight", "regime_filter",
        "priority", "rationale", "evidence", "created_at",
    ]
    return pd.DataFrame(rows, columns=cols)


def get_all_recommendations(days_back: int = 30) -> pd.DataFrame:
    sql = text("""
        SELECT
            id, generated_date::text, component_name, recommendation,
            current_weight, suggested_weight,
            regime_filter, priority, rationale, evidence,
            status, reviewed_at::text, promoted_at::text,
            rejection_reason, notes, created_at::text
        FROM adaptive_weight_recommendations
        WHERE generated_date >= CURRENT_DATE - :days * INTERVAL '1 day'
        ORDER BY generated_date DESC, priority DESC
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, {"days": days_back}).fetchall()
    cols = [
        "id", "generated_date", "component_name", "recommendation",
        "current_weight", "suggested_weight", "regime_filter",
        "priority", "rationale", "evidence",
        "status", "reviewed_at", "promoted_at",
        "rejection_reason", "notes", "created_at",
    ]
    return pd.DataFrame(rows, columns=cols)


def promote_recommendation(rec_id: int, reviewed_by: str = "system") -> None:
    sql = text("""
        UPDATE adaptive_weight_recommendations
        SET status = 'promoted', promoted_at = now(), reviewed_at = now(), reviewed_by = :by
        WHERE id = :id
    """)
    with get_connection() as conn:
        conn.execute(sql, {"id": rec_id, "by": reviewed_by})


def reject_recommendation(rec_id: int, reason: str, reviewed_by: str = "system") -> None:
    sql = text("""
        UPDATE adaptive_weight_recommendations
        SET status = 'rejected', reviewed_at = now(),
            reviewed_by = :by, rejection_reason = :reason
        WHERE id = :id
    """)
    with get_connection() as conn:
        conn.execute(sql, {"id": rec_id, "by": reviewed_by, "reason": reason})


# ---------------------------------------------------------------------------
# Analytical reads (used by report generator and API)
# ---------------------------------------------------------------------------

def get_prediction_outcomes_df(
    start_date: date,
    end_date: date,
    horizon_days: int = 5,
    min_conviction: str | None = None,
) -> pd.DataFrame:
    where = "po.prediction_date BETWEEN :start AND :end AND po.horizon_days = :horizon AND po.hit_or_miss IS NOT NULL"
    params: dict[str, Any] = {"start": start_date, "end": end_date, "horizon": horizon_days}
    if min_conviction:
        conviction_order = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "VERY_HIGH": 3}
        min_idx = conviction_order.get(min_conviction, 0)
        levels = [k for k, v in conviction_order.items() if v >= min_idx]
        where += " AND po.conviction_level = ANY(:levels)"
        params["levels"] = levels

    sql = text(f"""
        SELECT
            po.id,
            po.ticker,
            po.prediction_date::text,
            po.horizon_days,
            po.predicted_direction,
            po.predicted_probability,
            po.confluence_score,
            po.conviction_level,
            po.conviction_score,
            po.aligned_count,
            po.conflicting_count,
            po.regime,
            po.vol_regime,
            po.actual_return,
            po.actual_direction,
            po.hit_or_miss,
            po.prediction_error,
            po.max_runup,
            po.max_drawdown,
            ea.failure_class
        FROM prediction_outcomes po
        LEFT JOIN prediction_error_attribution ea
            ON ea.outcome_id = po.id AND ea.is_primary = true
        WHERE {where}
        ORDER BY po.prediction_date DESC
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    cols = [
        "id", "ticker", "prediction_date", "horizon_days",
        "predicted_direction", "predicted_probability",
        "confluence_score", "conviction_level", "conviction_score",
        "aligned_count", "conflicting_count",
        "regime", "vol_regime",
        "actual_return", "actual_direction", "hit_or_miss",
        "prediction_error", "max_runup", "max_drawdown",
        "failure_class",
    ]
    return pd.DataFrame(rows, columns=cols)


def get_outcome_stats_by_group(
    group_col: str,
    start_date: date,
    end_date: date,
    horizon_days: int = 5,
) -> pd.DataFrame:
    """Hit rate and avg return grouped by conviction_level, regime, etc."""
    valid_groups = {"conviction_level", "regime", "vol_regime",
                    "predicted_direction", "aligned_count", "conflicting_count"}
    if group_col not in valid_groups:
        raise ValueError(f"group_col must be one of {valid_groups}")
    sql = text(f"""
        SELECT
            {group_col}                           AS grp,
            COUNT(*)                              AS n,
            SUM(CASE WHEN hit_or_miss THEN 1 ELSE 0 END) AS n_hits,
            AVG(CASE WHEN hit_or_miss THEN 1.0 ELSE 0.0 END) AS hit_rate,
            AVG(actual_return)                    AS avg_return,
            AVG(max_runup)                        AS avg_runup,
            AVG(max_drawdown)                     AS avg_drawdown
        FROM prediction_outcomes
        WHERE prediction_date BETWEEN :start AND :end
          AND horizon_days = :horizon
          AND hit_or_miss IS NOT NULL
          AND {group_col} IS NOT NULL
        GROUP BY {group_col}
        ORDER BY hit_rate DESC
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, {
            "start": start_date, "end": end_date, "horizon": horizon_days,
        }).fetchall()
    cols = ["grp", "n", "n_hits", "hit_rate", "avg_return", "avg_runup", "avg_drawdown"]
    return pd.DataFrame(rows, columns=cols)
