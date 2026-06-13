"""
atlas_research.probability.questions
--------------------------------------
DB model for research_questions table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text

from atlas_research.db.connection import get_connection


@dataclass
class ResearchQuestion:
    name: str
    description: str
    category: str
    id: Optional[int] = None


def upsert_question(q: ResearchQuestion) -> int:
    with get_connection() as conn:
        row = conn.execute(text("""
            INSERT INTO research_questions (name, description, category)
            VALUES (:name, :desc, :cat)
            ON CONFLICT (name) DO UPDATE SET
                description = EXCLUDED.description,
                category    = EXCLUDED.category
            RETURNING id
        """), {"name": q.name, "desc": q.description, "cat": q.category}).fetchone()
    return int(row[0])


def get_question_by_name(name: str) -> Optional[ResearchQuestion]:
    with get_connection() as conn:
        row = conn.execute(text(
            "SELECT id, name, description, category "
            "FROM research_questions WHERE name = :n"
        ), {"n": name}).fetchone()
    if row is None:
        return None
    return ResearchQuestion(id=row[0], name=row[1], description=row[2], category=row[3])
