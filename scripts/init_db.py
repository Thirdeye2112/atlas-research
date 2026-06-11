#!/usr/bin/env python
"""
init_db.py — one-time database initialisation.

What it does:
  1. Runs db/schema.sql against the configured PostgreSQL instance.
  2. Seeds the securities table from config/universe.csv.

Run once on a fresh environment, or any time the schema needs reset.
Safe to re-run: all CREATE TABLE statements use IF NOT EXISTS.

Usage:
    python scripts/init_db.py
    python scripts/init_db.py --reset   # drops and recreates all tables (DESTRUCTIVE)
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Allow imports from src/ and config/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from config import settings
from atlas_research.db.connection import get_raw_engine, check_connection
from atlas_research.db import repository
from atlas_research.utils.logging import configure_logging, get_logger

configure_logging(level=settings.LOG_LEVEL, fmt=settings.LOG_FORMAT)
log = get_logger("init_db")

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


def run_schema(reset: bool = False) -> None:
    engine = get_raw_engine()

    if reset:
        log.warning("init_db.reset", message="Dropping all tables — data will be lost")
        with engine.begin() as conn:
            from sqlalchemy import text
            conn.execute(text("""
                DROP TABLE IF EXISTS
                    production_exports, predictions, model_registry,
                    research_runs, labels, feature_snapshots,
                    raw_bars, securities
                CASCADE
            """))
        log.info("init_db.dropped")

    sql = SCHEMA_PATH.read_text()
    with engine.begin() as conn:
        from sqlalchemy import text
        conn.execute(text(sql))

    log.info("init_db.schema_applied", path=str(SCHEMA_PATH))


def seed_securities() -> int:
    """Load universe.csv and upsert into securities table."""
    universe_path = settings.UNIVERSE_CSV

    if not universe_path.exists():
        log.warning("init_db.universe_missing", path=str(universe_path))
        return 0

    rows = []
    with open(universe_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ticker = row.get("ticker", "").strip().upper()
            if not ticker:
                continue
            rows.append({
                "ticker":   ticker,
                "name":     row.get("name", "").strip() or None,
                "sector":   row.get("sector", "").strip() or None,
                "industry": row.get("industry", "").strip() or None,
                "exchange": row.get("exchange", "").strip() or None,
            })

    if not rows:
        log.warning("init_db.no_tickers_in_csv")
        return 0

    n = repository.upsert_securities(rows)
    log.info("init_db.securities_seeded", count=len(rows))
    return len(rows)


def seed_feature_metadata() -> int:
    """Upsert the canonical feature_metadata entries from settings."""
    entries = settings.FEATURE_METADATA
    if not entries:
        return 0
    n = repository.upsert_feature_metadata(entries)
    log.info("init_db.feature_metadata_seeded", count=n)
    return n


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialise atlas-research database")
    parser.add_argument(
        "--reset", action="store_true",
        help="Drop all tables before creating. DESTRUCTIVE."
    )
    args = parser.parse_args()

    if args.reset:
        confirm = input("Drop all tables? This deletes all data. Type YES to confirm: ")
        if confirm.strip() != "YES":
            print("Aborted.")
            sys.exit(0)

    log.info("init_db.start", database_url=settings.DATABASE_URL.split("@")[-1])

    if not check_connection():
        log.error("init_db.db_unreachable")
        sys.exit(1)

    # run_schema skipped — schema managed by migrations
    n = seed_securities()
    m = seed_feature_metadata()

    log.info("init_db.complete", securities_seeded=n, feature_metadata_seeded=m)
    print(f"\n✓ Database initialised.")
    print(f"  {n} securities seeded.")
    print(f"  {m} feature_metadata rows seeded.")
    print("  Next: python scripts/backfill_history.py")


if __name__ == "__main__":
    main()
