"""
Pytest fixtures for atlas-research tests.

Uses an in-process SQLite database (via SQLAlchemy) so tests run
without a real PostgreSQL instance. The schema is identical; only
the upsert SQL (ON CONFLICT) needs minor guarding for SQLite compat.

For integration tests against real PostgreSQL, set TEST_DATABASE_URL
in the environment.
"""

from __future__ import annotations

import os
from datetime import date
from typing import Generator

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from atlas_research.db.models import Base, RawBar, FeatureSnapshot, Label, ResearchRun


# ── Engine fixture ────────────────────────────────────────────

@pytest.fixture(scope="session")
def db_engine():
    """
    SQLAlchemy engine backed by SQLite in-memory for unit tests,
    or a real PostgreSQL URL if TEST_DATABASE_URL is set.
    """
    test_url = os.environ.get("TEST_DATABASE_URL")

    if test_url:
        engine = create_engine(test_url, pool_pre_ping=True, future=True)
    else:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            future=True,
        )

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """
    Yield a SQLAlchemy session that rolls back after each test.
    Ensures test isolation without re-creating the schema.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection, future=True)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ── Sample data factories ─────────────────────────────────────

def make_raw_bar(
    ticker: str = "AAPL",
    bar_date: date = date(2024, 1, 2),
    close: float = 185.0,
    adj_close: float = 185.0,
    volume: int = 50_000_000,
    **kwargs,
) -> RawBar:
    return RawBar(
        ticker=ticker,
        bar_date=bar_date,
        open=close * 0.99,
        high=close * 1.01,
        low=close * 0.98,
        close=close,
        adj_close=adj_close,
        volume=volume,
        source="yahoo",
        **kwargs,
    )


def make_feature_snapshot(
    ticker: str = "AAPL",
    snap_date: date = date(2024, 1, 2),
    feature_version: int = 1,
    **kwargs,
) -> FeatureSnapshot:
    return FeatureSnapshot(
        ticker=ticker,
        snap_date=snap_date,
        feature_version=feature_version,
        ret_1d=0.01,
        ret_5d=0.03,
        rsi_14=55.0,
        close=185.0,
        **kwargs,
    )


def make_label(
    ticker: str = "AAPL",
    snap_date: date = date(2024, 1, 2),
    horizon_days: int = 5,
    **kwargs,
) -> Label:
    return Label(
        ticker=ticker,
        snap_date=snap_date,
        horizon_days=horizon_days,
        is_complete=False,
        **kwargs,
    )


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def raw_bar(db_session) -> RawBar:
    bar = make_raw_bar()
    db_session.add(bar)
    db_session.flush()
    return bar


@pytest.fixture
def feature_snapshot(db_session) -> FeatureSnapshot:
    snap = make_feature_snapshot()
    db_session.add(snap)
    db_session.flush()
    return snap


@pytest.fixture
def label(db_session) -> Label:
    lbl = make_label()
    db_session.add(lbl)
    db_session.flush()
    return lbl
