"""
scripts/_migration_lib.py
==========================
Shared library for apply_migration.py and list_migrations.py.
Not intended to be called directly.

Responsibilities
----------------
- Statement splitting (handles $$ blocks, comments, multi-line DDL)
- Checksum computation (SHA-256)
- schema_migrations bootstrap (creates table if missing)
- Migration discovery (sorted .sql files in db/migrations/)
- Applied migration reads from schema_migrations
- URL masking
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT           = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "db" / "migrations"


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class MigrationFile:
    """A .sql file discovered on disk."""
    name: str       # filename only, e.g. "0003_transcript_pipeline.sql"
    path: Path


@dataclass
class MigrationRecord:
    """A row from schema_migrations."""
    name:              str
    applied_at:        Optional[datetime]
    checksum:          str
    execution_time_ms: Optional[int]


# ── Checksum ──────────────────────────────────────────────────────────────────

def compute_checksum(sql_text: str) -> str:
    """Return SHA-256 hex digest of the raw SQL text (normalised line endings)."""
    normalised = sql_text.replace("\r\n", "\n").strip()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


# ── Statement splitter ────────────────────────────────────────────────────────

def split_statements(sql: str) -> list[str]:
    """
    Split a SQL migration file into individual executable statements.

    Handles correctly:
    - Line comments  (--)
    - Block comments (/* ... */)
    - Dollar-quoted blocks ($$ ... $$) used in DO / CREATE FUNCTION
    - Empty lines and trailing whitespace
    - Statements without trailing semicolon (at end of file)

    Returns a list of non-empty statement strings (with trailing semicolon
    preserved so PL/pgSQL blocks remain valid).
    """
    statements: list[str] = []
    current:    list[str] = []
    in_dollar   = False
    in_block    = False
    dollar_tag  = "$$"   # could be $body$ etc. — we handle simple $$ only

    lines = sql.splitlines()

    for raw_line in lines:
        line    = raw_line.rstrip()
        stripped = line.lstrip()

        # ── Block comment tracking ────────────────────────────────────────
        if not in_dollar:
            if "/*" in line:
                in_block = True
            if "*/" in line:
                in_block = False
                # Don't skip the line; it may contain SQL after */
                # but we still accumulate it for completeness
                current.append(line)
                continue
            if in_block:
                continue  # inside /* ... */ — skip entirely

        # ── Line comment (only outside dollar blocks) ─────────────────────
        if stripped.startswith("--") and not in_dollar:
            continue

        # ── Blank line outside a statement ────────────────────────────────
        if not stripped and not current and not in_dollar:
            continue

        # ── Dollar-quote toggle ───────────────────────────────────────────
        # Count $$ occurrences in this line (odd = toggle)
        dq_count = line.count("$$")
        if dq_count % 2 == 1:
            in_dollar = not in_dollar

        current.append(line)

        # ── Statement boundary ────────────────────────────────────────────
        # A semicolon at the very end of the line (outside a dollar block)
        # ends the current statement.
        if not in_dollar and stripped.endswith(";"):
            stmt = "\n".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []

    # Flush any trailing statement without a final semicolon
    if current:
        stmt = "\n".join(current).strip()
        if stmt:
            statements.append(stmt)

    return [s for s in statements if s.strip()]


# ── schema_migrations bootstrap ───────────────────────────────────────────────

_BOOTSTRAP_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_name    TEXT        PRIMARY KEY,
    applied_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum          TEXT        NOT NULL,
    execution_time_ms INTEGER     NOT NULL DEFAULT 0
);
"""


def bootstrap_tracking_table(engine: Engine) -> None:
    """
    Ensure schema_migrations exists.  Called at the start of every command
    that touches the database, so the table is always available before we
    try to read from it.
    """
    with engine.begin() as conn:
        conn.execute(text(_BOOTSTRAP_SQL.strip()))


# ── Migration discovery ───────────────────────────────────────────────────────

def discover_migrations(directory: Path = MIGRATIONS_DIR) -> list[MigrationFile]:
    """
    Return all .sql files in the migrations directory, sorted by filename.
    Sorting by name gives chronological order when files are named
    0001_, 0002_, etc.
    """
    if not directory.exists():
        return []
    files = sorted(directory.glob("*.sql"), key=lambda p: p.name)
    return [MigrationFile(name=f.name, path=f) for f in files]


# ── Applied migration reads ───────────────────────────────────────────────────

def get_applied_migrations(engine: Engine) -> dict[str, MigrationRecord]:
    """
    Read all rows from schema_migrations.
    Returns a dict keyed by migration_name.
    """
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT migration_name, applied_at, checksum, execution_time_ms "
            "FROM schema_migrations ORDER BY migration_name"
        )).fetchall()
    return {
        row[0]: MigrationRecord(
            name              = row[0],
            applied_at        = row[1],
            checksum          = row[2],
            execution_time_ms = row[3],
        )
        for row in rows
    }


# ── URL masking ───────────────────────────────────────────────────────────────

def masked_url(url: str) -> str:
    """Replace the password in a DB URL with *** for safe display."""
    return re.sub(r"(?<=://)([^:@]+):([^@]+)@", r"\1:***@", url)
