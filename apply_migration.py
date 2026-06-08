#!/usr/bin/env python
"""
scripts/apply_migration.py
===========================
Python-native database migration runner for atlas-research.
No psql binary required — uses the same SQLAlchemy connection as the rest
of the pipeline.

Usage
-----
    # Apply a .sql file
    python scripts/apply_migration.py db/migrations/003_transcript_intelligence.sql

    # Apply multiple files in order
    python scripts/apply_migration.py db/migrations/001_init.sql db/migrations/002_phase2.sql

    # Apply all migrations (sorted by filename)
    python scripts/apply_migration.py --all

    # Inline SQL (useful for quick ALTER TABLE fixes)
    python scripts/apply_migration.py --sql "ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();"

    # Dry-run: parse and show statements without executing
    python scripts/apply_migration.py db/migrations/003_transcript_intelligence.sql --dry-run

    # Show DATABASE_URL being used (masked)
    python scripts/apply_migration.py --show-url

Idempotency
-----------
All DDL in atlas-research migrations uses IF NOT EXISTS / IF EXISTS guards,
so any migration is safe to re-run.  Each .sql file is applied inside a
single transaction — if any statement fails the whole file is rolled back.

Exit codes
----------
    0   All migrations applied (or dry-run completed)
    1   One or more migrations failed
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Iterator

# ── Repo path bootstrap ──────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


# ── Database URL ─────────────────────────────────────────────────────────────

def _get_database_url() -> str:
    from config.settings import DATABASE_URL
    return DATABASE_URL


def _masked_url(url: str) -> str:
    """Replace password in URL with *** for display."""
    return re.sub(r"(?<=://)([^:@]+):([^@]+)@", r"\1:***@", url)


# ── SQL statement splitter ────────────────────────────────────────────────────

def _split_statements(sql: str) -> list[str]:
    """
    Split a SQL string into individual executable statements.

    Handles:
    - Line comments (--)
    - Block comments (/* ... */)
    - Dollar-quoted blocks ($$ ... $$) used by PL/pgSQL DO blocks
    - Multi-line statements
    - Empty statements (skipped)

    Returns a list of stripped statement strings (without trailing semicolon).
    """
    statements: list[str] = []
    current_lines: list[str] = []
    in_dollar_block = False
    in_block_comment = False

    for line in sql.splitlines():
        stripped = line.strip()

        # Toggle block comment state
        if "/*" in line and not in_dollar_block:
            in_block_comment = True
        if "*/" in line:
            in_block_comment = False
            current_lines.append(line)
            continue

        if in_block_comment:
            continue

        # Skip pure line comments (but keep them inside dollar blocks)
        if stripped.startswith("--") and not in_dollar_block:
            continue

        # Blank line outside a statement
        if not stripped and not current_lines and not in_dollar_block:
            continue

        # Track dollar-quote blocks (DO $$ BEGIN ... END $$;)
        dollar_count = line.count("$$")
        if dollar_count % 2 == 1:
            in_dollar_block = not in_dollar_block

        current_lines.append(line)

        # A semicolon at end of line (outside a dollar block) ends a statement
        if not in_dollar_block and stripped.endswith(";"):
            stmt = "\n".join(current_lines).strip()
            # Remove trailing semicolon — SQLAlchemy text() doesn't want it
            # for DDL, but it's harmless; we keep it for PL/pgSQL blocks.
            if stmt and not stmt.isspace():
                statements.append(stmt)
            current_lines = []

    # Flush anything remaining (statement without trailing semicolon)
    if current_lines:
        stmt = "\n".join(current_lines).strip()
        if stmt and not stmt.isspace():
            statements.append(stmt)

    return [s for s in statements if s]


# ── Migration runner ──────────────────────────────────────────────────────────

def _apply_sql(
    engine: Engine,
    sql: str,
    label: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """
    Parse `sql` into statements and execute them in a single transaction.
    Returns True on success, False on failure.
    """
    statements = _split_statements(sql)
    if not statements:
        print(f"  ⚠  {label}: no executable statements found")
        return True

    print(f"\n{'DRY-RUN: ' if dry_run else ''}Applying: {label}")
    print(f"  {len(statements)} statement(s)")
    print("  " + "─" * 60)

    if dry_run:
        for i, stmt in enumerate(statements, 1):
            preview = stmt.replace("\n", " ")[:100]
            ellipsis = "…" if len(stmt) > 100 else ""
            print(f"  [{i:>2}] {preview}{ellipsis}")
        print("  ✓ Dry-run complete (nothing executed)")
        return True

    t_start = time.time()
    try:
        with engine.begin() as conn:          # begin() = auto-commit on success, rollback on error
            for i, stmt in enumerate(statements, 1):
                t0 = time.time()
                try:
                    conn.execute(text(stmt))
                    elapsed = (time.time() - t0) * 1000
                    if verbose:
                        preview = stmt.replace("\n", " ")[:80]
                        ellipsis = "…" if len(stmt) > 80 else ""
                        print(f"  [{i:>2}] OK ({elapsed:.0f}ms)  {preview}{ellipsis}")
                    else:
                        print(f"  [{i:>2}] OK ({elapsed:.0f}ms)")
                except Exception as exc:
                    # Format a concise error without the full SQLAlchemy traceback
                    err_lines = str(exc).split("\n")
                    err_short = err_lines[0][:200]
                    print(f"  [{i:>2}] FAIL — {err_short}")
                    print(f"\n  ✗ Transaction rolled back.  No changes were applied.")
                    raise   # triggers rollback via engine.begin() context manager

        total_ms = (time.time() - t_start) * 1000
        print(f"\n  ✓ {label} applied successfully ({total_ms:.0f}ms total)")
        return True

    except Exception:
        return False


# ── Migration discovery ───────────────────────────────────────────────────────

def _find_all_migrations() -> list[Path]:
    """Return all .sql files in db/migrations/, sorted by filename."""
    migration_dir = ROOT / "db" / "migrations"
    if not migration_dir.exists():
        print(f"  ⚠  Migration directory not found: {migration_dir}")
        return []
    files = sorted(migration_dir.glob("*.sql"))
    return files


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply SQL migrations to the atlas-research database (no psql needed)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Exit codes")[0].strip(),
    )
    parser.add_argument(
        "files",
        nargs="*",
        metavar="FILE.sql",
        help=".sql file(s) to apply",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Apply all .sql files in db/migrations/ (sorted by name)",
    )
    parser.add_argument(
        "--sql",
        metavar="SQL",
        help="Apply an inline SQL string instead of a file",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and display statements without executing",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show a preview of each statement as it executes",
    )
    parser.add_argument(
        "--show-url",
        action="store_true",
        help="Print the database URL (password masked) and exit",
    )
    args = parser.parse_args()

    # ── Show URL ─────────────────────────────────────────────────────────────
    if args.show_url:
        url = _get_database_url()
        print(f"DATABASE_URL: {_masked_url(url)}")
        return 0

    # ── Build work list ───────────────────────────────────────────────────────
    work: list[tuple[str, str]] = []   # (label, sql_text)

    if args.sql:
        work.append(("inline SQL", args.sql))

    if args.all:
        for fpath in _find_all_migrations():
            sql = fpath.read_text(encoding="utf-8")
            work.append((str(fpath.relative_to(ROOT)), sql))
    elif args.files:
        for farg in args.files:
            fpath = Path(farg)
            if not fpath.exists():
                # Try relative to repo root
                fpath = ROOT / farg
            if not fpath.exists():
                print(f"ERROR: File not found: {farg}")
                return 1
            sql = fpath.read_text(encoding="utf-8")
            work.append((str(fpath.relative_to(ROOT)), sql))

    if not work:
        parser.print_help()
        print("\nERROR: Provide at least one .sql file, --all, or --sql <statement>")
        return 1

    # ── Connect ───────────────────────────────────────────────────────────────
    url = _get_database_url()
    print(f"Database: {_masked_url(url)}")

    if not args.dry_run:
        try:
            engine = create_engine(
                url,
                pool_pre_ping=True,
                pool_size=1,
                max_overflow=0,
                echo=False,
                future=True,
            )
            # Quick connectivity check
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print("Connection: OK")
        except Exception as exc:
            print(f"Connection FAILED: {exc}")
            return 1
    else:
        engine = None  # type: ignore[assignment]
        print("Connection: skipped (dry-run)")

    # ── Apply ─────────────────────────────────────────────────────────────────
    failed = 0
    for label, sql in work:
        ok = _apply_sql(engine, sql, label, dry_run=args.dry_run, verbose=args.verbose)
        if not ok:
            failed += 1

    # ── Summary ───────────────────────────────────────────────────────────────
    total = len(work)
    print()
    print("=" * 64)
    if failed == 0:
        status = "DRY-RUN COMPLETE" if args.dry_run else "ALL MIGRATIONS APPLIED"
        print(f"  ✓ {status}  ({total} file(s))")
    else:
        print(f"  ✗ {failed}/{total} migration(s) FAILED")
    print("=" * 64)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
