"""
atlas_research.probability.specs
----------------------------------
DB model for test_specifications table.
params stored as canonical JSON text (sort_keys=True) so the TEXT
UNIQUE constraint (ticker, condition_type, params) is deterministic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import text

from atlas_research.db.connection import get_connection


@dataclass
class TestSpec:
    ticker: str
    condition_type: str
    params: dict = field(default_factory=dict)
    question_id: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    id: Optional[int] = None


def _canon(params: dict) -> str:
    """Canonical JSON form — sort_keys for deterministic TEXT uniqueness."""
    return json.dumps(params, sort_keys=True, separators=(",", ":"))


def upsert_spec(spec: TestSpec) -> int:
    params_str = _canon(spec.params)
    with get_connection() as conn:
        row = conn.execute(text("""
            INSERT INTO test_specifications
                (question_id, ticker, condition_type, params, start_date, end_date)
            VALUES (:qid, :ticker, :ctype, :params, :start, :end)
            ON CONFLICT (ticker, condition_type, params) DO UPDATE SET
                question_id = COALESCE(EXCLUDED.question_id, test_specifications.question_id),
                start_date  = COALESCE(EXCLUDED.start_date,  test_specifications.start_date),
                end_date    = COALESCE(EXCLUDED.end_date,    test_specifications.end_date)
            RETURNING id
        """), {
            "qid":    spec.question_id,
            "ticker": spec.ticker,
            "ctype":  spec.condition_type,
            "params": params_str,
            "start":  spec.start_date,
            "end":    spec.end_date,
        }).fetchone()
    return int(row[0])


def get_spec(ticker: str, condition_type: str, params: dict) -> Optional[TestSpec]:
    params_str = _canon(params)
    with get_connection() as conn:
        row = conn.execute(text("""
            SELECT id, question_id, ticker, condition_type, params, start_date, end_date
            FROM test_specifications
            WHERE ticker = :t AND condition_type = :c AND params = :p
        """), {"t": ticker, "c": condition_type, "p": params_str}).fetchone()
    if row is None:
        return None
    return TestSpec(
        id=int(row[0]),
        question_id=row[1],
        ticker=row[2],
        condition_type=row[3],
        params=json.loads(row[4]),
        start_date=str(row[5]) if row[5] else None,
        end_date=str(row[6]) if row[6] else None,
    )
