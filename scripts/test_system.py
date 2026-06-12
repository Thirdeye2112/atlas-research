#!/usr/bin/env python
"""
scripts/test_system.py
=======================
End-to-end system health check for Atlas Research Engine.
Tests every layer from DB connectivity to prediction serving.

Usage:
    python scripts/test_system.py
    python scripts/test_system.py --api-url http://localhost:8080
    python scripts/test_system.py --verbose
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

PASS = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN]"

results: list[tuple[str, bool, str]] = []

def check(name: str, fn, warn_only: bool = False):
    try:
        msg = fn()
        results.append((name, True, msg or "OK"))
        print(f"  {PASS}  {name:<55} {msg or ''}")
    except Exception as e:
        short = str(e).split('\n')[0][:80]
        results.append((name, False, short))
        icon = WARN if warn_only else FAIL
        print(f"  {icon}  {name:<55} {short}")


# ── Layer 1: Database connectivity ────────────────────────────────────────────

def test_db():
    from sqlalchemy import create_engine, text
    from config.settings import DATABASE_URL
    e = create_engine(DATABASE_URL)
    with e.connect() as c:
        row = c.execute(text("SELECT version()")).fetchone()
    return f"PostgreSQL connected"

def test_db_tables():
    from sqlalchemy import create_engine, text
    from config.settings import DATABASE_URL
    e = create_engine(DATABASE_URL)
    with e.connect() as c:
        rows = c.execute(text("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)).fetchall()
    tables = [r[0] for r in rows]
    required = ['raw_bars','feature_snapshots','labels','model_registry',
                'predictions','schema_migrations','pattern_signals']
    missing = [t for t in required if t not in tables]
    if missing:
        raise Exception(f"Missing tables: {missing}")
    return f"{len(tables)} tables present"

def test_migrations():
    from sqlalchemy import create_engine, text
    from config.settings import DATABASE_URL
    from scripts._migration_lib import discover_migrations, get_applied_migrations
    sys.path.insert(0, str(ROOT / "scripts"))
    e = create_engine(DATABASE_URL)
    applied = get_applied_migrations(e)
    on_disk = discover_migrations(ROOT / "db" / "migrations")
    pending = [m for m in on_disk if m.name not in applied]
    if pending:
        raise Exception(f"{len(pending)} pending migrations: {[m.name for m in pending]}")
    return f"{len(applied)} migrations applied"


# ── Layer 2: Data coverage ─────────────────────────────────────────────────────

def test_raw_bars():
    from sqlalchemy import create_engine, text
    from config.settings import DATABASE_URL
    e = create_engine(DATABASE_URL)
    with e.connect() as c:
        row = c.execute(text(
            "SELECT COUNT(*), COUNT(DISTINCT ticker), MAX(date)::text FROM raw_bars"
        )).fetchone()
    rows, tickers, last = row
    if rows < 1000:
        raise Exception(f"Only {rows} rows — backfill may not have run")
    days_ago = (date.today() - date.fromisoformat(last)).days
    if days_ago > 5:
        raise Exception(f"Last bar is {days_ago} days old ({last}) — run nightly pipeline")
    return f"{rows:,} rows | {tickers} tickers | last={last}"

def test_parquet():
    parquet_dir = ROOT / "exports" / "parquet"
    files = sorted(parquet_dir.glob("feature_matrix_*.parquet"))
    if not files:
        raise Exception("No parquet files found — run nightly pipeline")
    latest = files[-1]
    latest_date = latest.stem.replace("feature_matrix_", "")
    days_ago = (date.today() - date.fromisoformat(latest_date)).days
    if days_ago > 3:
        raise Exception(f"Latest parquet is {days_ago} days old ({latest_date})")
    return f"{len(files)} files | latest={latest_date}"

def test_labels():
    from sqlalchemy import create_engine, text
    from config.settings import DATABASE_URL
    e = create_engine(DATABASE_URL)
    with e.connect() as c:
        row = c.execute(text(
            "SELECT COUNT(*), SUM(CASE WHEN return_5d IS NOT NULL THEN 1 ELSE 0 END)::float / COUNT(*) FROM labels"
        )).fetchone()
    total, coverage = row
    if total < 1000:
        raise Exception(f"Only {total} label rows")
    if coverage < 0.95:
        raise Exception(f"Label coverage only {coverage:.1%}")
    return f"{total:,} labels | {coverage:.1%} coverage"


# ── Layer 3: Model registry ───────────────────────────────────────────────────

def test_model_registry():
    from sqlalchemy import create_engine, text
    from config.settings import DATABASE_URL
    e = create_engine(DATABASE_URL)
    with e.connect() as c:
        rows = c.execute(text(
            "SELECT COUNT(*), AVG(rank_ic), MAX(training_end)::text FROM model_registry"
        )).fetchone()
    count, mean_ic, trained_through = rows
    if count == 0:
        raise Exception("model_registry is empty — run training")
    return f"{count} folds | mean IC={mean_ic:.4f} | trained_through={trained_through}"

def test_model_artifacts():
    models_dir = ROOT / "models"
    artifacts = list(models_dir.glob("*/model.joblib"))
    if not artifacts:
        raise Exception("No model.joblib files found")
    return f"{len(artifacts)} model artifact(s)"


# ── Layer 4: Predictions ──────────────────────────────────────────────────────

def test_predictions():
    from sqlalchemy import create_engine, text
    from config.settings import DATABASE_URL
    e = create_engine(DATABASE_URL)
    with e.connect() as c:
        row = c.execute(text(
            "SELECT COUNT(*), MAX(date)::text FROM predictions WHERE model_name = 'return_regressor'"
        )).fetchone()
    count, pred_date = row
    if count == 0:
        raise Exception("No predictions — run: python scripts/run_training.py --predict-only")
    days_ago = (date.today() - date.fromisoformat(pred_date)).days if pred_date else 99
    if days_ago > 3:
        raise Exception(f"Latest predictions are {days_ago} days old ({pred_date})")
    return f"{count} predictions | latest={pred_date}"

def test_prediction_columns():
    from sqlalchemy import create_engine, text
    from config.settings import DATABASE_URL
    e = create_engine(DATABASE_URL)
    with e.connect() as c:
        row = c.execute(text("""
            SELECT rank_percentile, confidence, expected_return, probability_positive
            FROM predictions WHERE model_name = 'return_regressor' LIMIT 1
        """)).fetchone()
    if row is None:
        raise Exception("No predictions rows")
    nulls = [i for i, v in enumerate(['rank_pct','confidence','exp_return','prob_pos']) if row[i] is None]
    if nulls:
        raise Exception(f"NULL ML columns: {nulls} — migration 0007 may not have backfilled")
    return f"rank_pct={row[0]:.1f} conf={row[1]:.3f} exp_ret={row[2]:.4f}"


# ── Layer 5: API endpoints ────────────────────────────────────────────────────

def test_api_health(api_url: str):
    import urllib.request, json
    r = urllib.request.urlopen(f"{api_url}/api/health", timeout=5)
    return f"HTTP {r.status}"

def test_api_metrics(api_url: str):
    import urllib.request, json
    r = urllib.request.urlopen(f"{api_url}/api/research/metrics/latest", timeout=5)
    data = json.loads(r.read())
    if not data.get("champion"):
        raise Exception("champion field is null — predictions may be missing")
    ic = data["champion"].get("latest_rank_ic")
    return f"IC={ic:.4f} | coverage={data['coverage']['raw_bars']:,} bars"

def test_api_predictions(api_url: str):
    import urllib.request, json
    r = urllib.request.urlopen(f"{api_url}/api/research/predictions", timeout=5)
    data = json.loads(r.read())
    count = data.get("count", 0)
    if count == 0:
        raise Exception("0 predictions returned — run predict-only then rebuild server")
    top = data["predictions"][0]
    return f"{count} predictions | top={top['ticker']} rank={top.get('rank_percentile','?')}"

def test_api_signal(api_url: str):
    import urllib.request, json
    r = urllib.request.urlopen(f"{api_url}/api/research/signal/AAPL", timeout=5)
    data = json.loads(r.read())
    if not data.get("available"):
        raise Exception("AAPL signal not available — route may not be registered or no predictions")
    return f"strength={data['ml_signal_strength']} dir={data['ml_direction']} rank={data.get('ml_rank_percentile','?')}"

def test_api_signals_batch(api_url: str):
    import urllib.request, json
    r = urllib.request.urlopen(f"{api_url}/api/research/signals?tickers=AAPL,MSFT,NVDA", timeout=5)
    data = json.loads(r.read())
    count = data.get("count", 0)
    if count == 0:
        raise Exception("0 signals returned — route not registered or no predictions")
    return f"{count}/3 tickers have signals"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(prog="python scripts/test_system.py")
    parser.add_argument("--api-url", default="http://localhost:8080")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--skip-api", action="store_true", help="Skip API tests (server not running)")
    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"  Atlas Research Engine — System Health Check")
    print(f"  {date.today()}  |  API: {args.api_url}")
    print(f"{'='*70}\n")

    print("  Layer 1 — Database")
    check("DB connectivity",           test_db)
    check("Required tables present",   test_db_tables)
    check("Migrations up to date",     test_migrations)

    print("\n  Layer 2 — Data Coverage")
    check("raw_bars populated",        test_raw_bars)
    check("Parquet files current",     test_parquet)
    check("Labels coverage",           test_labels)

    print("\n  Layer 3 — Model")
    check("model_registry has folds",  test_model_registry)
    check("Model artifacts on disk",   test_model_artifacts)

    print("\n  Layer 4 — Predictions")
    check("Predictions in DB",         test_predictions)
    check("ML columns populated",      test_prediction_columns)

    if not args.skip_api:
        print(f"\n  Layer 5 — API ({args.api_url})")
        check("GET /api/health",                lambda: test_api_health(args.api_url), warn_only=True)
        check("GET /api/research/metrics/latest", lambda: test_api_metrics(args.api_url))
        check("GET /api/research/predictions",    lambda: test_api_predictions(args.api_url))
        check("GET /api/research/signal/AAPL",   lambda: test_api_signal(args.api_url),    warn_only=True)
        check("GET /api/research/signals?tickers=...", lambda: test_api_signals_batch(args.api_url), warn_only=True)

    # ── Summary ───────────────────────────────────────────────────────────────
    passed  = sum(1 for _, ok, _ in results if ok)
    failed  = sum(1 for _, ok, _ in results if not ok)
    total   = len(results)

    print(f"\n{'='*70}")
    print(f"  Results: {passed}/{total} passed", end="")
    if failed:
        print(f"  |  {failed} FAILED", end="")
        print()
        print()
        print("  Failed checks:")
        for name, ok, msg in results:
            if not ok:
                print(f"    {FAIL} {name}")
                print(f"      > {msg}")
    else:
        print(f"  -- All checks passed [OK]")
    print(f"{'='*70}\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())