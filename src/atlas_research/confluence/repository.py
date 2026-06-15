"""DB reads and writes for the confluence engine."""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
from sqlalchemy import text

from atlas_research.confluence.components.base import ComponentResult
from atlas_research.db.connection import get_connection
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)


# ── Runs ──────────────────────────────────────────────────────────────────────

def create_run(run_date: date, engine_version: str = "v1", notes: str | None = None) -> int:
    sql = text("""
        INSERT INTO confluence_score_runs (run_date, engine_version, notes)
        VALUES (:run_date, :engine_version, :notes)
        RETURNING id
    """)
    with get_connection() as conn:
        row = conn.execute(sql, {
            "run_date": run_date,
            "engine_version": engine_version,
            "notes": notes,
        }).fetchone()
    return int(row[0])


def update_run_count(run_id: int, n_tickers: int) -> None:
    sql = text("UPDATE confluence_score_runs SET n_tickers=:n WHERE id=:id")
    with get_connection() as conn:
        conn.execute(sql, {"n": n_tickers, "id": run_id})


# ── Snapshots ─────────────────────────────────────────────────────────────────

def upsert_snapshot(
    run_id: int,
    ticker: str,
    snap_date: date,
    score: float,
    direction: str,
    ml_prob: float | None,
    ml_exp_ret: float | None,
    risk_level: float | None,
    aligned: int,
    conflicting: int,
    neutral: int,
    total: int,
    market_regime: str | None,
    vol_regime: str | None,
    engine_version: str = "v1",
) -> int:
    sql = text("""
        INSERT INTO confluence_score_snapshots (
            run_id, ticker, snapshot_date, engine_version,
            confluence_score, confluence_direction,
            confluence_probability, confluence_expected_return, confluence_risk,
            aligned_signal_count, conflicting_signal_count,
            neutral_signal_count, total_signal_count,
            regime, vol_regime
        ) VALUES (
            :run_id, :ticker, :snap_date, :engine_version,
            :score, :direction,
            :ml_prob, :ml_exp_ret, :risk_level,
            :aligned, :conflicting, :neutral, :total,
            :regime, :vol_regime
        )
        ON CONFLICT (ticker, snapshot_date, engine_version) DO UPDATE SET
            run_id                     = EXCLUDED.run_id,
            confluence_score           = EXCLUDED.confluence_score,
            confluence_direction       = EXCLUDED.confluence_direction,
            confluence_probability     = EXCLUDED.confluence_probability,
            confluence_expected_return = EXCLUDED.confluence_expected_return,
            confluence_risk            = EXCLUDED.confluence_risk,
            aligned_signal_count       = EXCLUDED.aligned_signal_count,
            conflicting_signal_count   = EXCLUDED.conflicting_signal_count,
            neutral_signal_count       = EXCLUDED.neutral_signal_count,
            total_signal_count         = EXCLUDED.total_signal_count,
            regime                     = EXCLUDED.regime,
            vol_regime                 = EXCLUDED.vol_regime,
            computed_at                = now()
        RETURNING id
    """)
    with get_connection() as conn:
        row = conn.execute(sql, {
            "run_id": run_id, "ticker": ticker, "snap_date": snap_date,
            "engine_version": engine_version, "score": score,
            "direction": direction, "ml_prob": ml_prob,
            "ml_exp_ret": ml_exp_ret, "risk_level": risk_level,
            "aligned": aligned, "conflicting": conflicting,
            "neutral": neutral, "total": total,
            "regime": market_regime, "vol_regime": vol_regime,
        }).fetchone()
    return int(row[0])


def upsert_components(
    snapshot_id: int,
    ticker: str,
    snap_date: date,
    components: list[ComponentResult],
) -> None:
    sql = text("""
        INSERT INTO confluence_score_components (
            snapshot_id, ticker, snapshot_date,
            component_name, signal, strength, score, weight, available, details
        ) VALUES (
            :snapshot_id, :ticker, :snap_date,
            :name, :signal, :strength, :score, :weight, :available, :details::jsonb
        )
        ON CONFLICT (snapshot_id, component_name) DO UPDATE SET
            signal     = EXCLUDED.signal,
            strength   = EXCLUDED.strength,
            score      = EXCLUDED.score,
            weight     = EXCLUDED.weight,
            available  = EXCLUDED.available,
            details    = EXCLUDED.details,
            computed_at = now()
    """)
    import json
    rows = [
        {
            "snapshot_id": snapshot_id,
            "ticker": ticker,
            "snap_date": snap_date,
            "name": c.name,
            "signal": c.signal,
            "strength": c.strength,
            "score": c.score,
            "weight": c.weight,
            "available": c.available,
            "details": json.dumps({
                k: v for k, v in c.details.items() if k != "fitness_table"
            }),
        }
        for c in components
    ]
    with get_connection() as conn:
        for row in rows:
            conn.execute(sql, row)


# ── Reads ─────────────────────────────────────────────────────────────────────

def get_latest_snapshot(ticker: str, engine_version: str = "v1") -> dict[str, Any] | None:
    sql = text("""
        SELECT s.*, r.run_date
        FROM confluence_score_snapshots s
        JOIN confluence_score_runs r ON r.id = s.run_id
        WHERE s.ticker = :ticker
          AND s.engine_version = :ver
        ORDER BY s.snapshot_date DESC
        LIMIT 1
    """)
    with get_connection() as conn:
        row = conn.execute(sql, {"ticker": ticker, "ver": engine_version}).fetchone()
    if row is None:
        return None
    keys = [
        "id", "run_id", "ticker", "snapshot_date", "engine_version",
        "confluence_score", "confluence_direction", "confluence_probability",
        "confluence_expected_return", "confluence_risk",
        "aligned_signal_count", "conflicting_signal_count",
        "neutral_signal_count", "total_signal_count",
        "regime", "vol_regime", "computed_at", "run_date",
    ]
    return dict(zip(keys, row))


def get_components_for_snapshot(snapshot_id: int) -> list[dict[str, Any]]:
    sql = text("""
        SELECT component_name, signal, strength, score, weight, available, details
        FROM confluence_score_components
        WHERE snapshot_id = :sid
        ORDER BY weight DESC
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, {"sid": snapshot_id}).fetchall()
    keys = ["component_name", "signal", "strength", "score", "weight", "available", "details"]
    return [dict(zip(keys, r)) for r in rows]


def get_top_confluence(
    snap_date: date,
    direction: str | None = None,
    min_score: float = 60.0,
    limit: int = 50,
    engine_version: str = "v1",
) -> pd.DataFrame:
    where = "snapshot_date = :date AND engine_version = :ver AND confluence_score >= :min_score"
    params: dict[str, Any] = {
        "date": snap_date, "ver": engine_version, "min_score": min_score, "limit": limit,
    }
    if direction:
        where += " AND confluence_direction = :direction"
        params["direction"] = direction

    sql = text(f"""
        SELECT ticker, confluence_score, confluence_direction,
               confluence_probability, confluence_expected_return,
               aligned_signal_count, conflicting_signal_count, regime
        FROM confluence_score_snapshots
        WHERE {where}
        ORDER BY confluence_score DESC
        LIMIT :limit
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    cols = [
        "ticker", "confluence_score", "confluence_direction",
        "confluence_probability", "confluence_expected_return",
        "aligned_signal_count", "conflicting_signal_count", "regime",
    ]
    return pd.DataFrame(rows, columns=cols)
