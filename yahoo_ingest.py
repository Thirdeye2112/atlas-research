"""
Database connection — renamed from atlas_research/db/engine.py.
Logic unchanged: SQLAlchemy engine + get_connection() context manager.

All SQL in this project is written as raw strings (text()).
SQLAlchemy is used only for connection pooling and transaction management,
not as an ORM.  The schema lives in db/schema.sql.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

# Lazy import to avoid circular at module load time
def _get_database_url() -> str:
    from config.settings import DATABASE_URL
    return DATABASE_URL


_engine = None


def _engine_instance():
    global _engine
    if _engine is None:
        _engine = create_engine(
            _get_database_url(),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=False,
            future=True,
        )
    return _engine


@contextmanager
def get_connection() -> Generator[Connection, None, None]:
    """
    Yield a SQLAlchemy Connection inside a transaction.
    Commits on clean exit, rolls back on exception.

    Usage:
        from atlas_research.db.connection import get_connection

        with get_connection() as conn:
            conn.execute(text("INSERT INTO ..."), {...})
            # commits automatically on exit
    """
    engine = _engine_instance()
    with engine.begin() as conn:
        yield conn


def check_connection() -> bool:
    """Return True if the database is reachable."""
    try:
        with get_connection() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        print(f"[connection] DB unreachable: {exc}", file=sys.stderr)
        return False


def get_raw_engine():
    """Return the underlying engine (for schema init scripts)."""
    return _engine_instance()
