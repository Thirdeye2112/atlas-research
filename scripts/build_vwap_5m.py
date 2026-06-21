#!/usr/bin/env python
"""
build_vwap_5m.py — Compute and store session-anchored VWAP features for 5m bars.

Reads intraday_bars (READ-ONLY), writes ONLY to vwap_5m (new table).
Does NOT touch pattern_memory, intraday_setups, or any other table.

VWAP = cumsum(typical_price * volume) / cumsum(volume), reset each ET session.
typical_price = (high + low + close) / 3  (HLC3 standard).

Features stored per bar:
  vwap           — session-anchored VWAP (float)
  dist_from_vwap — (close - vwap) / vwap, signed (float, null if vwap=0)
  above_vwap     — close > vwap (bool)
  session_date   — ET trading date (date)

Usage
-----
    # Smoke test — 3 tickers only:
    python scripts/build_vwap_5m.py --limit 3

    # Full run (resumable — skips tickers already fully in vwap_5m):
    python scripts/build_vwap_5m.py

    # Specific tickers:
    python scripts/build_vwap_5m.py --tickers SPY QQQ AAPL

    # Dry-run (print counts, no writes):
    python scripts/build_vwap_5m.py --limit 3 --dry-run

    # Force-recompute a ticker (overwrite existing rows):
    python scripts/build_vwap_5m.py --tickers AAPL --no-skip

Design
------
- Resumable: by default skips tickers already present in vwap_5m.
- Per-ticker watchdog: any ticker exceeding --timeout seconds is logged and skipped.
- One commit per ticker (like run_5m_fullpass.py pattern).
- Log written to reports/validity/vwap_5m.log (timestamped lines, same style as 5m_fullpass).
- Uses clean_universe.csv as universe source (same as other full-pass scripts).
"""
from __future__ import annotations

import argparse
import io
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

import pandas as pd
from sqlalchemy import create_engine, text

from config import settings
from atlas_research.ta.vwap import compute_vwap_features

LOG_PATH = ROOT / "reports" / "validity" / "vwap_5m.log"
WATCHDOG_S = 300      # seconds per ticker before skip
BAR_CAP = 500_000     # pathological guard; no ticker should approach this


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _log(msg: str, fh) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    if fh:
        fh.write(line + "\n")
        fh.flush()


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def load_bars(ticker: str, engine) -> pd.DataFrame:
    """Load all 5m bars for one ticker from intraday_bars (read-only)."""
    sql = text("""
        SELECT ticker, ts, open, high, low, close, volume
        FROM intraday_bars
        WHERE ticker = :tk AND timeframe = '5m'
        ORDER BY ts ASC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"tk": ticker}).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["ticker", "ts", "open", "high", "low", "close", "volume"])
    # Ensure ts is tz-aware UTC
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def already_done(engine) -> set[str]:
    """Tickers that already have rows in vwap_5m (for resume logic)."""
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT DISTINCT ticker FROM vwap_5m")).fetchall()
    return {r[0] for r in rows}


def upsert_vwap(df: pd.DataFrame, engine) -> int:
    """
    Bulk-upsert VWAP rows into vwap_5m via COPY staging table.
    ON CONFLICT (ticker, ts) DO UPDATE so re-runs overwrite stale rows.
    Returns number of rows written.
    """
    if df.empty:
        return 0

    # Prepare CSV payload
    payload = df[["ticker", "ts", "vwap", "dist_from_vwap", "above_vwap", "session_date"]].copy()
    # Ensure ts is ISO-formatted with timezone for COPY
    payload["ts"] = payload["ts"].dt.strftime("%Y-%m-%d %H:%M:%S%z")
    payload["above_vwap"] = payload["above_vwap"].map({True: "t", False: "f"})

    buf = io.StringIO()
    payload.to_csv(buf, index=False, header=False)
    buf.seek(0)

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("""
            CREATE TEMP TABLE _stage_vwap (
                ticker          TEXT,
                ts              TIMESTAMPTZ,
                vwap            DOUBLE PRECISION,
                dist_from_vwap  DOUBLE PRECISION,
                above_vwap      BOOLEAN,
                session_date    DATE
            ) ON COMMIT DROP
        """)
        cur.copy_expert(
            "COPY _stage_vwap (ticker, ts, vwap, dist_from_vwap, above_vwap, session_date) "
            "FROM STDIN WITH (FORMAT csv, NULL '')",
            buf,
        )
        cur.execute("""
            INSERT INTO vwap_5m (ticker, ts, vwap, dist_from_vwap, above_vwap, session_date)
            SELECT ticker, ts, vwap, dist_from_vwap, above_vwap, session_date
            FROM _stage_vwap
            ON CONFLICT (ticker, ts) DO UPDATE SET
                vwap           = EXCLUDED.vwap,
                dist_from_vwap = EXCLUDED.dist_from_vwap,
                above_vwap     = EXCLUDED.above_vwap,
                session_date   = EXCLUDED.session_date,
                computed_at    = now()
        """)
        raw.commit()
    finally:
        raw.close()
    return len(df)


# ---------------------------------------------------------------------------
# Per-ticker processing
# ---------------------------------------------------------------------------

def process_ticker(ticker: str, engine, dry_run: bool) -> dict:
    result = {"ticker": ticker, "bars": 0, "rows": 0, "error": None, "skipped": False}

    # 1. Load bars
    try:
        bars = load_bars(ticker, engine)
    except Exception as e:
        result["error"] = f"load_failed:{e!r}"
        return result

    if bars.empty:
        result["skipped"] = True
        return result

    if len(bars) > BAR_CAP:
        result["error"] = f"pathological_bar_count:{len(bars)}"
        return result

    result["bars"] = len(bars)

    # 2. Compute VWAP features
    try:
        feat = compute_vwap_features(bars)
    except Exception as e:
        result["error"] = f"compute_failed:{e!r}"
        return result

    result["rows"] = len(feat)

    # 3. Write
    if not dry_run:
        try:
            upsert_vwap(feat, engine)
        except Exception as e:
            result["error"] = f"upsert_failed:{e!r}"
    return result


def _safe_process(fn, *args) -> dict:
    try:
        return fn(*args)
    except Exception as e:
        return {"ticker": args[0], "bars": 0, "rows": 0, "error": repr(e), "skipped": False}


# ---------------------------------------------------------------------------
# Universe helpers
# ---------------------------------------------------------------------------

def get_universe_from_db(engine, limit: int | None) -> list[str]:
    """All distinct tickers in intraday_bars with timeframe='5m', ordered by bar count desc."""
    sql = text("""
        SELECT ticker, count(*) AS n
        FROM intraday_bars
        WHERE timeframe = '5m'
        GROUP BY ticker
        ORDER BY n DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()
    tickers = [r[0] for r in rows]
    return tickers[:limit] if limit else tickers


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute and store session-anchored VWAP for 5m bars → vwap_5m table"
    )
    parser.add_argument("--tickers", nargs="+", default=None,
                        help="Explicit ticker list (default: all in intraday_bars 5m)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process only first N tickers of the universe (smoke test)")
    parser.add_argument("--timeout", type=int, default=WATCHDOG_S,
                        help=f"Per-ticker watchdog timeout in seconds (default {WATCHDOG_S})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute features but do not write to DB")
    parser.add_argument("--no-skip", action="store_true",
                        help="Reprocess and overwrite tickers already in vwap_5m")
    args = parser.parse_args()

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fh = open(LOG_PATH, "a", encoding="utf-8")

    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=3, max_overflow=5, pool_pre_ping=True
    )

    # Build ticker list
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        tickers = get_universe_from_db(engine, args.limit)

    # Resume: skip tickers already computed (unless --no-skip)
    skip_set: set[str] = set()
    if not args.no_skip and not args.dry_run:
        skip_set = already_done(engine)
        before = len(tickers)
        tickers = [t for t in tickers if t not in skip_set]
        if before != len(tickers):
            _log(f"resume: skipping {before - len(tickers)} tickers already in vwap_5m "
                 f"({len(tickers)} remaining)", fh)

    if args.limit and not args.tickers:
        tickers = tickers[:args.limit]

    M = len(tickers)
    _log(
        f"=== build_vwap_5m START === universe={M} "
        f"timeout={args.timeout}s dry_run={args.dry_run}",
        fh,
    )

    if M == 0:
        _log("Nothing to process — all tickers already in vwap_5m or universe empty.", fh)
        fh.close()
        return

    total_bars = total_rows = done_n = errors = no_data = 0
    wall_times: list[float] = []

    for i, tk in enumerate(tickers, 1):
        t0 = time.time()
        box: dict = {}

        th = threading.Thread(
            target=lambda: box.update(_safe_process(process_ticker, tk, engine, args.dry_run)),
            daemon=True,
        )
        th.start()
        th.join(timeout=args.timeout)
        elapsed = time.time() - t0

        if th.is_alive():
            _log(f"[{i}/{M}] {tk} TIMEOUT >{args.timeout}s — skipped", fh)
            errors += 1
            continue

        res = box if box else {"ticker": tk, "bars": 0, "rows": 0, "error": "thread_empty", "skipped": False}

        if res.get("error"):
            errors += 1
            _log(f"[{i}/{M}] {tk} ERROR {str(res['error'])[:120]}", fh)
            continue

        if res.get("skipped"):
            no_data += 1
        else:
            total_bars += res["bars"]
            total_rows += res["rows"]
            done_n += 1
            wall_times.append(elapsed)

        avg = sum(wall_times) / len(wall_times) if wall_times else 0
        eta_h = avg * (M - i) / 3600
        _log(
            f"[{i}/{M} {100*i/M:.1f}%] {tk} bars={res['bars']:,} rows={res['rows']:,} "
            f"{elapsed:.1f}s | avg={avg:.1f}s ETA={eta_h:.2f}h "
            f"total_rows={total_rows:,} no_data={no_data} err={errors}",
            fh,
        )

    _log(
        f"=== build_vwap_5m END === processed={done_n} no_data={no_data} errors={errors} "
        f"total_bars={total_bars:,} total_rows={total_rows:,}",
        fh,
    )
    fh.close()


if __name__ == "__main__":
    main()
