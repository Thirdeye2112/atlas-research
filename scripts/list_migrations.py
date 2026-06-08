#!/usr/bin/env python
"""
scripts/list_migrations.py
===========================
Display migration status with rich detail.  Companion to apply_migration.py.

Usage
-----
    # Full status table (default)
    python scripts/list_migrations.py

    # Show only pending migrations
    python scripts/list_migrations.py --pending

    # Show only applied migrations
    python scripts/list_migrations.py --applied

    # Run checksum verification
    python scripts/list_migrations.py --verify

    # JSON output (for CI / scripting)
    python scripts/list_migrations.py --json

Exit codes
----------
    0   All applied migrations pass checksum; no drift
    1   One or more drifted or failed checksums detected
    2   Configuration error
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from sqlalchemy import create_engine, text

from _migration_lib import (
    MigrationFile,
    MigrationRecord,
    bootstrap_tracking_table,
    compute_checksum,
    discover_migrations,
    get_applied_migrations,
    masked_url,
    MIGRATIONS_DIR,
)


def _get_url() -> str:
    from config.settings import DATABASE_URL
    return DATABASE_URL


def _make_engine(url: str):
    return create_engine(
        url, pool_pre_ping=True, pool_size=1, max_overflow=0,
        echo=False, future=True,
    )


# ── Enriched status record ────────────────────────────────────────────────────

def _build_status_rows(engine) -> list[dict]:
    """
    Merge on-disk files with DB records into a unified list of status dicts.
    Each dict has:
        name, state, applied_at, checksum_db, checksum_disk,
        checksum_ok, execution_time_ms, path
    States: 'applied', 'pending', 'drifted', 'orphan'
    """
    applied  = get_applied_migrations(engine)
    on_disk  = discover_migrations()
    file_map = {m.name: m for m in on_disk}
    all_names = sorted(set(applied) | {m.name for m in on_disk})

    rows = []
    for name in all_names:
        rec   = applied.get(name)
        fmig  = file_map.get(name)

        if rec and fmig:
            cs_disk = compute_checksum(fmig.path.read_text(encoding="utf-8"))
            cs_ok   = cs_disk == rec.checksum
            rows.append({
                "name":               name,
                "state":              "applied" if cs_ok else "drifted",
                "applied_at":         rec.applied_at.isoformat() if rec.applied_at else None,
                "checksum_db":        rec.checksum,
                "checksum_disk":      cs_disk,
                "checksum_ok":        cs_ok,
                "execution_time_ms":  rec.execution_time_ms,
                "path":               str(fmig.path.relative_to(ROOT)),
            })
        elif fmig and not rec:
            cs_disk = compute_checksum(fmig.path.read_text(encoding="utf-8"))
            rows.append({
                "name":               name,
                "state":              "pending",
                "applied_at":         None,
                "checksum_db":        None,
                "checksum_disk":      cs_disk,
                "checksum_ok":        None,
                "execution_time_ms":  None,
                "path":               str(fmig.path.relative_to(ROOT)),
            })
        elif rec and not fmig:
            rows.append({
                "name":               name,
                "state":              "orphan",
                "applied_at":         rec.applied_at.isoformat() if rec.applied_at else None,
                "checksum_db":        rec.checksum,
                "checksum_disk":      None,
                "checksum_ok":        False,
                "execution_time_ms":  rec.execution_time_ms,
                "path":               None,
            })

    return rows


# ── Display ───────────────────────────────────────────────────────────────────

STATE_ICON = {
    "applied": "✓",
    "pending": "·",
    "drifted": "⚠",
    "orphan":  "?",
}

STATE_LABEL = {
    "applied": "applied",
    "pending": "PENDING",
    "drifted": "DRIFTED ⚠",
    "orphan":  "orphan",
}


def _print_table(rows: list[dict], filter_state: str | None = None) -> int:
    if filter_state:
        rows = [r for r in rows if r["state"] == filter_state]

    if not rows:
        print(f"  (no migrations match filter)")
        return 0

    W = max(len(r["name"]) for r in rows) + 2

    print()
    print(f"  {'Migration':<{W}} {'State':<12} {'Applied at':<22} {'ms':>6}  Checksum")
    print("  " + "─" * (W + 52))

    drifted = 0
    for r in rows:
        icon    = STATE_ICON[r["state"]]
        label   = STATE_LABEL[r["state"]]
        at_str  = (r["applied_at"] or "—")[:19].replace("T", " ")
        ms_str  = str(r["execution_time_ms"]) if r["execution_time_ms"] is not None else "—"
        cs_str  = (r.get("checksum_db") or r.get("checksum_disk") or "—")[:12] + "…"
        print(f"  {icon} {r['name']:<{W-2}} {label:<12} {at_str:<22} {ms_str:>6}  {cs_str}")
        if r["state"] == "drifted":
            drifted += 1
            print(f"      db disk:  {r['checksum_db']}")
            print(f"      on disk:  {r['checksum_disk']}")

    print()
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["state"]] = counts.get(r["state"], 0) + 1

    parts = []
    for state in ("applied", "pending", "drifted", "orphan"):
        n = counts.get(state, 0)
        if n:
            parts.append(f"{n} {STATE_LABEL[state]}")
    print(f"  {', '.join(parts) if parts else 'no migrations'}")
    return 1 if drifted else 0


def _print_verify(rows: list[dict]) -> int:
    print()
    print("  Checksum verification:")
    drifted = 0
    for r in rows:
        if r["state"] == "orphan":
            print(f"  ?  {r['name']}: file not found on disk (orphan)")
        elif r["state"] == "pending":
            pass  # pending = not applied, nothing to verify
        elif r["checksum_ok"]:
            print(f"  ✓  {r['name']}")
        else:
            print(f"  ✗  {r['name']}: CHECKSUM MISMATCH")
            print(f"       DB:    {r['checksum_db']}")
            print(f"       Disk:  {r['checksum_disk']}")
            drifted += 1
    print()
    applied_count = sum(1 for r in rows if r["state"] in ("applied", "drifted"))
    if drifted:
        print(f"  ✗ {drifted} drifted migration(s) detected.")
        return 1
    print(f"  ✓ All {applied_count} applied migrations verified clean.")
    return 0


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python scripts/list_migrations.py",
        description="List atlas-research database migration status",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--pending",  action="store_true", help="Show only pending migrations")
    mode.add_argument("--applied",  action="store_true", help="Show only applied migrations")
    mode.add_argument("--verify",   action="store_true", help="Verify checksums of applied migrations")
    mode.add_argument("--json",     action="store_true", help="Output as JSON")
    args = parser.parse_args()

    try:
        url    = _get_url()
        engine = _make_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"Database: {masked_url(url)}")
        bootstrap_tracking_table(engine)
    except Exception as exc:
        print(f"ERROR: Connection failed — {exc}", file=sys.stderr)
        return 2

    rows = _build_status_rows(engine)

    if args.json:
        print(json.dumps(rows, indent=2, default=str))
        return 0

    if args.verify:
        return _print_verify(rows)

    if args.pending:
        return _print_table(rows, filter_state="pending")

    if args.applied:
        return _print_table(rows, filter_state="applied")

    return _print_table(rows)


if __name__ == "__main__":
    sys.exit(main())
