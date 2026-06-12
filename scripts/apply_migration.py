#!/usr/bin/env python
"""
scripts/apply_migration.py
===========================
Foundational database migration runner for atlas-research.
No psql binary required â€” pure Python via SQLAlchemy.

Usage
-----
    # Show current migration status
    python scripts/apply_migration.py --status

    # Apply all pending migrations (standard CI/CD usage)
    python scripts/apply_migration.py --all

    # Apply a specific file
    python scripts/apply_migration.py db/migrations/0003_transcript_pipeline.sql

    # Apply multiple files
    python scripts/apply_migration.py db/migrations/0002_core_schema.sql db/migrations/0003_transcript_pipeline.sql

    # Run inline SQL
    python scripts/apply_migration.py --sql "ALTER TABLE model_registry ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();"

    # Preview what would run (no DB changes)
    python scripts/apply_migration.py --all --dry-run

    # Show each statement as it executes
    python scripts/apply_migration.py --all --verbose

    # Verify checksums of applied migrations match files on disk
    python scripts/apply_migration.py --verify

    # Show database URL (password masked)
    python scripts/apply_migration.py --show-url

Exit codes
----------
    0   Success (or dry-run completed)
    1   One or more migrations failed or checksum mismatch
    2   Configuration error (bad URL, missing file, etc.)
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path
from typing import Optional

# â”€â”€ Repo path bootstrap â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# â”€â”€ Deferred heavy imports (after path setup) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from _migration_lib import (  # local helper â€” same directory
    MigrationRecord,
    bootstrap_tracking_table,
    compute_checksum,
    get_applied_migrations,
    discover_migrations,
    split_statements,
    masked_url,
    MIGRATIONS_DIR,
)


# â”€â”€ Database connection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _get_url() -> str:
    from config.settings import DATABASE_URL
    return DATABASE_URL


def _make_engine(url: str) -> Engine:
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
        echo=False,
        future=True,
    )


# â”€â”€ Core apply logic â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def apply_file(
    engine: Engine,
    fpath: Path,
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """
    Apply a single migration file inside a transaction.
    Records the result in schema_migrations on success.
    Returns True on success, False on failure (transaction rolled back).
    """
    name     = fpath.name
    sql_text = fpath.read_text(encoding="utf-8")
    checksum = compute_checksum(sql_text)
    stmts    = split_statements(sql_text)

    if not stmts:
        print(f"  âš   {name}: no executable statements found â€” skipping")
        return True

    print(f"\n  {'[DRY-RUN] ' if dry_run else ''}â†’ {name}")
    print(f"     {len(stmts)} statement(s)   checksum={checksum[:12]}â€¦")

    if dry_run:
        for i, stmt in enumerate(stmts, 1):
            preview = stmt.replace("\n", " ")[:90]
            dot = "â€¦" if len(stmt) > 90 else ""
            print(f"     [{i:>2}] {preview}{dot}")
        print(f"     âœ“ dry-run (no changes)")
        return True

    t_file = time.monotonic()
    try:
        with engine.begin() as conn:
            for i, stmt in enumerate(stmts, 1):
                t0 = time.monotonic()
                conn.execute(text(stmt))
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                if verbose:
                    preview = stmt.replace("\n", " ")[:80]
                    dot = "â€¦" if len(stmt) > 80 else ""
                    print(f"     [{i:>2}] {elapsed_ms:>4}ms  {preview}{dot}")
                else:
                    print(f"     [{i:>2}] OK ({elapsed_ms}ms)")

            # Write tracking record inside same transaction
            total_ms = int((time.monotonic() - t_file) * 1000)
            conn.execute(text("""
                INSERT INTO schema_migrations (migration_name, applied_at, checksum, execution_time_ms)
                VALUES (:name, now(), :checksum, :ms)
                ON CONFLICT (migration_name) DO UPDATE SET
                    applied_at       = now(),
                    checksum         = EXCLUDED.checksum,
                    execution_time_ms = EXCLUDED.execution_time_ms
            """), {"name": name, "checksum": checksum, "ms": total_ms})

        print(f"     âœ“ applied in {total_ms}ms")
        return True

    except Exception as exc:
        # Summarise without the full SQLAlchemy traceback chain
        err = str(exc).split("\n")[0][:200]
        print(f"     âœ— FAILED â€” {err}")
        print(f"     âœ— Transaction rolled back. No changes applied for {name}.")
        return False


def apply_inline(
    engine: Engine,
    sql: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """Apply an inline SQL string (not tracked in schema_migrations)."""
    stmts = split_statements(sql)
    label = "inline SQL"

    if not stmts:
        print(f"  âš   {label}: no executable statements found")
        return True

    print(f"\n  {'[DRY-RUN] ' if dry_run else ''}â†’ {label}")
    print(f"     {len(stmts)} statement(s)")

    if dry_run:
        for i, stmt in enumerate(stmts, 1):
            print(f"     [{i:>2}] {stmt[:90]}")
        return True

    try:
        with engine.begin() as conn:
            for i, stmt in enumerate(stmts, 1):
                t0 = time.monotonic()
                conn.execute(text(stmt))
                ms = int((time.monotonic() - t0) * 1000)
                if verbose:
                    print(f"     [{i:>2}] {ms}ms  {stmt[:80]}")
                else:
                    print(f"     [{i:>2}] OK ({ms}ms)")
        print(f"     âœ“ applied")
        return True
    except Exception as exc:
        err = str(exc).split("\n")[0][:200]
        print(f"     âœ— FAILED â€” {err}")
        return False


# â”€â”€ Commands â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def cmd_status(engine: Engine) -> int:
    """Print a table of all migrations: applied, pending, or drifted."""
    applied = get_applied_migrations(engine)
    on_disk = discover_migrations()

    # Collect all known names
    all_names = sorted(
        set(m.name for m in on_disk) | set(applied.keys())
    )

    W_NAME = max((len(n) for n in all_names), default=30) + 2

    print(f"\n  {'Migration':<{W_NAME}} {'Status':<12} {'Applied at':<22} {'ms':>6}  Checksum")
    print("  " + "â”€" * (W_NAME + 52))

    pending_count  = 0
    applied_count  = 0
    drifted_count  = 0
    orphan_count   = 0

    # Build nameâ†’file map
    file_map = {m.name: m for m in on_disk}

    for name in all_names:
        rec   = applied.get(name)
        fpath = file_map.get(name)

        if rec and fpath:
            # Applied and file exists â€” check checksum
            current_cs = compute_checksum(fpath.path.read_text(encoding="utf-8"))
            if current_cs != rec.checksum:
                status    = "DRIFTED âš "
                drifted_count += 1
            else:
                status    = "applied âœ“"
                applied_count += 1
            at_str    = rec.applied_at.strftime("%Y-%m-%d %H:%M:%S") if rec.applied_at else "â€”"
            ms_str    = str(rec.execution_time_ms) if rec.execution_time_ms is not None else "â€”"
            cs_str    = rec.checksum[:12] + "â€¦"
        elif fpath and not rec:
            status    = "PENDING"
            at_str    = "â€”"
            ms_str    = "â€”"
            cs_str    = compute_checksum(fpath.path.read_text(encoding="utf-8"))[:12] + "â€¦"
            pending_count += 1
        else:
            # In DB but file missing from disk
            status    = "orphan (no file)"
            at_str    = rec.applied_at.strftime("%Y-%m-%d %H:%M:%S") if rec and rec.applied_at else "â€”"
            ms_str    = "â€”"
            cs_str    = (rec.checksum[:12] + "â€¦") if rec else "â€”"
            orphan_count += 1

        print(f"  {name:<{W_NAME}} {status:<12} {at_str:<22} {ms_str:>6}  {cs_str}")

    print()
    summary = []
    if applied_count:  summary.append(f"{applied_count} applied")
    if pending_count:  summary.append(f"{pending_count} pending")
    if drifted_count:  summary.append(f"{drifted_count} DRIFTED")
    if orphan_count:   summary.append(f"{orphan_count} orphaned")
    print(f"  Summary: {', '.join(summary) if summary else 'no migrations found'}")
    print()

    return 1 if drifted_count else 0


def cmd_apply_all(
    engine: Engine,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Apply all pending migrations in sorted filename order."""
    applied  = get_applied_migrations(engine)
    on_disk  = discover_migrations()
    pending  = [m for m in on_disk if m.name not in applied]

    if not pending:
        print("\n  âœ“ All migrations already applied. Nothing to do.")
        return 0

    print(f"\n  {len(pending)} pending migration(s) to apply:")
    for m in pending:
        print(f"    â€¢ {m.name}")

    failed = 0
    for m in pending:
        ok = apply_file(engine, m.path, dry_run=dry_run, verbose=verbose)
        if not ok:
            print(f"\n  âœ— Stopping after failed migration: {m.name}")
            failed += 1
            break

    applied_count = len(pending) - failed
    print()
    print("=" * 64)
    if failed == 0:
        verb = "DRY-RUN" if dry_run else "APPLIED"
        print(f"  âœ“ {verb}: {len(pending)} migration(s)")
    else:
        print(f"  âœ— FAILED after {applied_count}/{len(pending)} migration(s)")
    print("=" * 64)
    return 1 if failed else 0


def cmd_verify(engine: Engine) -> int:
    """Check that applied migrations match files on disk (checksum verification)."""
    applied  = get_applied_migrations(engine)
    on_disk  = discover_migrations()
    file_map = {m.name: m for m in on_disk}

    drifted = []
    for name, rec in sorted(applied.items()):
        if name not in file_map:
            print(f"  âš   {name}: applied but file not on disk (orphan)")
            continue
        current = compute_checksum(file_map[name].path.read_text(encoding="utf-8"))
        if current != rec.checksum:
            print(f"  âœ—  {name}: CHECKSUM MISMATCH")
            print(f"       applied:  {rec.checksum}")
            print(f"       on disk:  {current}")
            drifted.append(name)
        else:
            print(f"  âœ“  {name}: OK")

    print()
    if drifted:
        print(f"  {len(drifted)} drifted migration(s). Files were modified after application.")
        return 1
    print(f"  All {len(applied)} applied migrations verified.")
    return 0


# â”€â”€ Argument parsing + dispatch â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/apply_migration.py",
        description="atlas-research database migration runner (no psql required)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Actions (mutually exclusive)
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--all",
        action="store_true",
        help="Apply all pending migrations in db/migrations/ (sorted by filename)",
    )
    action.add_argument(
        "--status",
        action="store_true",
        help="Show migration status table",
    )
    action.add_argument(
        "--verify",
        action="store_true",
        help="Verify checksums of applied migrations against files on disk",
    )
    action.add_argument(
        "--sql",
        metavar="SQL",
        help="Apply an inline SQL string (not tracked in schema_migrations)",
    )
    action.add_argument(
        "--show-url",
        action="store_true",
        help="Print DATABASE_URL (password masked) and exit",
    )

    # Positional: one or more .sql files
    parser.add_argument(
        "files",
        nargs="*",
        metavar="FILE.sql",
        help="One or more .sql migration files to apply",
    )

    # Modifiers
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and display statements without executing anything",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print each statement as it executes",
    )

    args = parser.parse_args()

    # Show URL only â€” no DB connection needed
    if args.show_url:
        try:
            url = _get_url()
            print(f"DATABASE_URL: {masked_url(url)}")
        except Exception as exc:
            print(f"ERROR: Could not read DATABASE_URL â€” {exc}", file=sys.stderr)
            return 2
        return 0

    # Connect
    try:
        url    = _get_url()
        engine = _make_engine(url)
        if not args.dry_run:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            print(f"Database: {masked_url(url)}")
            # Always ensure tracking table exists before any command
            bootstrap_tracking_table(engine)
        else:
            print(f"Database: {masked_url(url)}  [DRY-RUN â€” no connection made]")
    except Exception as exc:
        print(f"ERROR: Connection failed â€” {exc}", file=sys.stderr)
        return 2

    # Dispatch
    if args.status:
        return cmd_status(engine)

    if args.verify:
        return cmd_verify(engine)

    if args.all:
        return cmd_apply_all(engine, dry_run=args.dry_run, verbose=args.verbose)

    if args.sql:
        ok = apply_inline(engine, args.sql, dry_run=args.dry_run, verbose=args.verbose)
        return 0 if ok else 1

    if args.files:
        failed = 0
        for farg in args.files:
            fpath = Path(farg)
            if not fpath.exists():
                fpath = ROOT / farg        # try relative to repo root
            if not fpath.exists():
                print(f"  âœ— File not found: {farg}", file=sys.stderr)
                failed += 1
                continue
            ok = apply_file(engine, fpath, dry_run=args.dry_run, verbose=args.verbose)
            if not ok:
                failed += 1
                break   # stop on first failure, consistent with --all
        print()
        print("=" * 64)
        total = len(args.files)
        if failed == 0:
            print(f"  âœ“ {'DRY-RUN' if args.dry_run else 'APPLIED'}: {total} file(s)")
        else:
            print(f"  âœ— FAILED: {failed}/{total} file(s)")
        print("=" * 64)
        return 1 if failed else 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())

