---
name: run-atlas-research
description: Run, start, test, or drive the Atlas Research ML pipeline — nightly data fetch, feature generation, model training, predictions, conditional backtests, and system health checks. Use for any request involving the Python ML pipeline, migrations, backtest patterns, or research database.
---

# Atlas Research — Run Skill

Python ML pipeline. PostgreSQL DB at `atlas_research`. Paths relative to `C:\Atlas\atlas-research`.

## Prerequisites

```powershell
# Python venv at .venv (already set up)
Set-Location C:\Atlas\atlas-research
.\.venv\Scripts\python.exe --version  # 3.11+

# Always set before running any script
$env:DATABASE_URL = "<set in .env, do not hardcode>"
$env:PYTHONIOENCODING = "utf-8"
```

## Run — Agent Path

### Migrations

```powershell
# Check status
.\.venv\Scripts\python.exe scripts\apply_migration.py --status

# Apply all pending
.\.venv\Scripts\python.exe scripts\apply_migration.py --all --verbose
```

### Nightly Pipeline (data → features → labels → parquet)

```powershell
.\.venv\Scripts\python.exe scripts\run_nightly.py
# Partial status is normal (yfinance rate-limits ~75/186 tickers at night)
# Outputs: exports/parquet/feature_matrix_YYYY-MM-DD.parquet
```

### Predictions (score all tickers with latest model)

```powershell
.\.venv\Scripts\python.exe scripts\run_training.py --predict-only
# Verified 2026-06-10: 184 rows written, mean_prob=0.484
```

### Conditional Backtests

```powershell
# List patterns
.\.venv\Scripts\python.exe scripts\run_conditional.py --list

# Run one pattern
.\.venv\Scripts\python.exe scripts\run_conditional.py --pattern spy_down_4d

# Show results table
.\.venv\Scripts\python.exe scripts\run_conditional.py --results

# Run all patterns (~30 min for 16 patterns × 184 tickers)
.\.venv\Scripts\python.exe scripts\run_conditional.py
```

### System Health Check

```powershell
# Skip API layer (no server needed)
.\.venv\Scripts\python.exe scripts\test_system.py --skip-api
# Verified 2026-06-10: 10/10 passed

# Full check (API server must be running on :8080)
.\.venv\Scripts\python.exe scripts\test_system.py --api-url http://localhost:8080
```

## Conditional Backtest Results (2026-06-10)

Key SPY mean-reversion findings:

| Pattern | 5d Hit% | 5d Avg% | n |
|---------|---------|---------|---|
| spy_down_5d | **72.9** | +0.98 | 48 |
| spy_down_4d | **70.3** | +0.82 | 128 |
| spy_up_5d | 71.6 | +0.47 | 155 |
| consecutive_down_3 | 56.4 | +0.45 | 66,664 |
| oversold_rsi_30 | 58.3 | +0.50 | 19,515 |

## Migrations

| Migration | Description |
|-----------|-------------|
| 0001 | Bootstrap schema_migrations |
| 0002 | Core schema (raw_bars, features, labels, predictions, model_registry) |
| 0003 | Transcript pipeline (transcript_sources, chunks, hypotheses, results) |
| 0004 | model_registry unique constraint |
| 0005 | pattern_signals table |
| 0009 | labels return columns (return_1d/5d/10d/20d/60d, positive_5d/20d) |
| 0010 | conditional_patterns + conditional_pattern_results (12 SP500 + 4 SPY seeds) |
| 0011 | hypothesis_tests.backtest_version, posteriors, leaderboard view, transcript_signal_events |

## Gotchas

- **yfinance rate-limiting** — "possibly delisted" for AAPL/NVDA/etc. is rate-limiting, not delisting. Pipeline continues with partial data.
- **ROUND cast** — `ROUND(value::numeric, n)` required; plain `ROUND(double_precision, n)` fails in PostgreSQL.
- **NULL UPSERT** — `conditional_pattern_results` has `UNIQUE (pattern_id, COALESCE(ticker,''), horizon_days)`. The engine's ON CONFLICT must use the same expression.
- **NaN in production_exports** — pipeline.json_export_failed with `Token "NaN" is invalid`. Pre-existing; parquet export still succeeds.
- **test_system.py labels check** — uses `return_5d` (not `label_return_5d`; column was renamed in migration 0009).
- **run_conditional.py uses `get_raw_engine()`** — not `get_connection()` (which is a context manager). The script calls `.connect()` on the result so it needs an Engine, not a generator.
