#!/usr/bin/env python
"""
build_gaps.py — Detect price gaps and FVGs, write to gaps table.

Reads: raw_bars (daily classic gaps + daily FVGs), intraday_bars (5m FVGs).
Writes: ONLY to gaps table (new, isolated). No other table is touched.

Gap types built:
  classic/daily  — today.open > prior.high (up) or < prior.low (down)
  fvg/daily      — 3-bar imbalance on daily bars
  fvg/5m         — 3-bar imbalance on 5m bars

Usage
-----
    # Smoke test — 5 tickers:
    python scripts/build_gaps.py --limit 5

    # Full run (resumable):
    python scripts/build_gaps.py

    # Only daily processing:
    python scripts/build_gaps.py --daily-only

    # Only 5m FVGs:
    python scripts/build_gaps.py --fivemin-only

    # Specific tickers:
    python scripts/build_gaps.py --tickers SPY QQQ AAPL

    # Dry-run (compute, no writes):
    python scripts/build_gaps.py --limit 5 --dry-run

    # Force-recompute (overwrite existing):
    python scripts/build_gaps.py --tickers AAPL --no-skip

Design
------
- Universe for daily: clean_universe.csv (raw_bars).
- Universe for 5m: tickers in intraday_bars (timeframe='5m').
- Resumable: by default skips tickers with (ticker, timeframe) already in gaps.
- Per-ticker watchdog: exceeding --timeout seconds logs and skips.
- One commit per ticker per timeframe.
- Log to reports/validity/gaps.log.
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
from atlas_research.ta.gaps import compute_classic_gaps, compute_fvgs

LOG_PATH = ROOT / "reports" / "validity" / "gaps.log"
WATCHDOG_S = 300
BAR_CAP = 600_000    # pathological guard

_GAP_COLS = [
    "ticker", "ts", "timeframe", "gap_type", "direction",
    "zone_top", "zone_bottom", "size_pct",
    "detect_close_ts", "bar1_ts", "bar3_ts",
]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _log(msg: str, fh=None) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    if fh:
        fh.write(line + "\n")
        fh.flush()


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def load_daily_bars(ticker: str, engine) -> pd.DataFrame:
    """Load all daily bars for ticker from raw_bars (read-only)."""
    sql = text("""
        SELECT ticker, date, open, high, low, close
        FROM raw_bars
        WHERE ticker = :tk
        ORDER BY date ASC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"tk": ticker}).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["ticker", "date", "open", "high", "low", "close"])
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_5m_bars(ticker: str, engine) -> pd.DataFrame:
    """Load all 5m bars for ticker from intraday_bars (read-only)."""
    sql = text("""
        SELECT ticker, ts, open, high, low, close
        FROM intraday_bars
        WHERE ticker = :tk AND timeframe = '5m'
        ORDER BY ts ASC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql, {"tk": ticker}).fetchall()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["ticker", "ts", "open", "high", "low", "close"])
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def already_done(engine) -> dict[str, set[str]]:
    """Return {timeframe: set_of_tickers} already in gaps table."""
    sql = text("SELECT DISTINCT timeframe, ticker FROM gaps")
    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()
    result: dict[str, set[str]] = {}
    for tf, tk in rows:
        result.setdefault(tf, set()).add(tk)
    return result


def upsert_gaps(df: pd.DataFrame, engine) -> int:
    """
    Bulk-upsert gap rows into gaps via COPY staging.
    ON CONFLICT (ticker, ts, timeframe, gap_type, direction) DO UPDATE overwrites.
    """
    if df.empty:
        return 0

    payload = df[_GAP_COLS].copy()
    # Format timestamps for COPY — always emit explicit UTC offset (+0000) to avoid
    # PostgreSQL interpreting naive strings in the session timezone.
    def _ts_str(v) -> str:
        if v is None or (not isinstance(v, pd.Timestamp) and pd.isna(v)):
            return ""
        ts = pd.Timestamp(v)
        ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        return ts.strftime("%Y-%m-%d %H:%M:%S+0000")

    for col in ["ts", "detect_close_ts", "bar1_ts", "bar3_ts"]:
        if col in payload.columns:
            payload[col] = payload[col].apply(_ts_str)

    buf = io.StringIO()
    payload.to_csv(buf, index=False, header=False)
    buf.seek(0)

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("""
            CREATE TEMP TABLE _stage_gaps (
                ticker          TEXT,
                ts              TIMESTAMPTZ,
                timeframe       TEXT,
                gap_type        TEXT,
                direction       TEXT,
                zone_top        DOUBLE PRECISION,
                zone_bottom     DOUBLE PRECISION,
                size_pct        DOUBLE PRECISION,
                detect_close_ts TIMESTAMPTZ,
                bar1_ts         TIMESTAMPTZ,
                bar3_ts         TIMESTAMPTZ
            ) ON COMMIT DROP
        """)
        cur.copy_expert(
            "COPY _stage_gaps (ticker, ts, timeframe, gap_type, direction, "
            "zone_top, zone_bottom, size_pct, detect_close_ts, bar1_ts, bar3_ts) "
            "FROM STDIN WITH (FORMAT csv, NULL '')",
            buf,
        )
        cur.execute("""
            INSERT INTO gaps
                (ticker, ts, timeframe, gap_type, direction,
                 zone_top, zone_bottom, size_pct, detect_close_ts, bar1_ts, bar3_ts)
            SELECT ticker, ts, timeframe, gap_type, direction,
                   zone_top, zone_bottom, size_pct, detect_close_ts, bar1_ts, bar3_ts
            FROM _stage_gaps
            ON CONFLICT (ticker, ts, timeframe, gap_type, direction) DO UPDATE SET
                zone_top        = EXCLUDED.zone_top,
                zone_bottom     = EXCLUDED.zone_bottom,
                size_pct        = EXCLUDED.size_pct,
                detect_close_ts = EXCLUDED.detect_close_ts,
                bar1_ts         = EXCLUDED.bar1_ts,
                bar3_ts         = EXCLUDED.bar3_ts,
                computed_at     = now()
        """)
        raw.commit()
    finally:
        raw.close()
    return len(df)


# ---------------------------------------------------------------------------
# Per-ticker processing
# ---------------------------------------------------------------------------

def process_daily(ticker: str, engine, dry_run: bool) -> dict:
    """Classic gaps + daily FVGs for one ticker."""
    result = {"ticker": ticker, "bars": 0, "rows": 0, "error": None, "skipped": False}

    try:
        bars = load_daily_bars(ticker, engine)
    except Exception as e:
        result["error"] = f"load_daily:{e!r}"
        return result

    if bars.empty:
        result["skipped"] = True
        return result

    if len(bars) > BAR_CAP:
        result["error"] = f"pathological:{len(bars)}"
        return result

    result["bars"] = len(bars)

    try:
        classic = compute_classic_gaps(bars)
        # For daily FVGs, convert date to ts (UTC midnight)
        bars_ts = bars.copy()
        bars_ts["ts"] = bars_ts["date"].apply(
            lambda d: pd.Timestamp(d).normalize().tz_localize("UTC")
        )
        fvgs = compute_fvgs(bars_ts, timeframe="daily")
        combined = pd.concat([classic, fvgs], ignore_index=True) if not (classic.empty and fvgs.empty) \
                   else (classic if not classic.empty else fvgs)
    except Exception as e:
        result["error"] = f"compute_daily:{e!r}"
        return result

    result["rows"] = len(combined)

    if not dry_run and not combined.empty:
        try:
            upsert_gaps(combined, engine)
        except Exception as e:
            result["error"] = f"upsert_daily:{e!r}"
    return result


def process_5m(ticker: str, engine, dry_run: bool) -> dict:
    """5m FVGs for one ticker."""
    result = {"ticker": ticker, "bars": 0, "rows": 0, "error": None, "skipped": False}

    try:
        bars = load_5m_bars(ticker, engine)
    except Exception as e:
        result["error"] = f"load_5m:{e!r}"
        return result

    if bars.empty:
        result["skipped"] = True
        return result

    if len(bars) > BAR_CAP:
        result["error"] = f"pathological:{len(bars)}"
        return result

    result["bars"] = len(bars)

    try:
        fvgs = compute_fvgs(bars, timeframe="5m")
    except Exception as e:
        result["error"] = f"compute_5m:{e!r}"
        return result

    result["rows"] = len(fvgs)

    if not dry_run and not fvgs.empty:
        try:
            upsert_gaps(fvgs, engine)
        except Exception as e:
            result["error"] = f"upsert_5m:{e!r}"
    return result


def _safe(fn, *args) -> dict:
    try:
        return fn(*args)
    except Exception as e:
        return {"ticker": args[0], "bars": 0, "rows": 0, "error": repr(e), "skipped": False}


# ---------------------------------------------------------------------------
# Universe helpers
# ---------------------------------------------------------------------------

def daily_universe(limit: int | None) -> list[str]:
    """Tickers from clean_universe.csv."""
    tickers = (
        pd.read_csv(settings.CLEAN_UNIVERSE_CSV)["ticker"]
        .astype(str).str.upper().tolist()
    )
    return tickers[:limit] if limit else tickers


def fivemin_universe(engine, limit: int | None) -> list[str]:
    """Tickers in intraday_bars 5m, ordered by bar count desc."""
    sql = text("""
        SELECT ticker, COUNT(*) AS n
        FROM intraday_bars WHERE timeframe = '5m'
        GROUP BY ticker ORDER BY n DESC
    """)
    with engine.connect() as conn:
        rows = conn.execute(sql).fetchall()
    tickers = [r[0] for r in rows]
    return tickers[:limit] if limit else tickers


# ---------------------------------------------------------------------------
# Main loop helper
# ---------------------------------------------------------------------------

def run_pass(
    tickers: list[str],
    process_fn,
    label: str,
    timeout: int,
    dry_run: bool,
    fh,
) -> tuple[int, int, int, int, int]:
    """Run a processing pass, return (done, skipped, errors, total_bars, total_rows)."""
    M = len(tickers)
    done_n = skipped = errors = total_bars = total_rows = 0
    times: list[float] = []

    for i, tk in enumerate(tickers, 1):
        t0 = time.time()
        box: dict = {}
        th = threading.Thread(
            target=lambda: box.update(_safe(process_fn, tk, engine_ref[0], dry_run)),
            daemon=True,
        )
        th.start()
        th.join(timeout=timeout)
        elapsed = time.time() - t0

        if th.is_alive():
            _log(f"[{label}][{i}/{M}] {tk} TIMEOUT >{timeout}s — skipped", fh)
            errors += 1
            continue

        res = box or {"ticker": tk, "bars": 0, "rows": 0, "error": "thread_empty", "skipped": False}

        if res.get("error"):
            errors += 1
            _log(f"[{label}][{i}/{M}] {tk} ERROR {str(res['error'])[:100]}", fh)
            continue

        if res.get("skipped"):
            skipped += 1
        else:
            total_bars += res["bars"]
            total_rows += res["rows"]
            done_n += 1
            times.append(elapsed)

        avg = sum(times) / len(times) if times else 0
        eta_h = avg * (M - i) / 3600

        _log(
            f"[{label}][{i}/{M} {100*i/M:.1f}%] {tk} bars={res['bars']:,} "
            f"rows={res['rows']:,} {elapsed:.1f}s | avg={avg:.1f}s ETA={eta_h:.2f}h "
            f"total_rows={total_rows:,} skip={skipped} err={errors}",
            fh,
        )

    return done_n, skipped, errors, total_bars, total_rows


# Module-level engine ref for thread closure (set in main)
engine_ref: list = [None]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Detect price gaps / FVGs, write to gaps table"
    )
    parser.add_argument("--tickers", nargs="+", default=None)
    parser.add_argument("--limit", type=int, default=None,
                        help="Cap universe size for smoke tests")
    parser.add_argument("--timeout", type=int, default=WATCHDOG_S)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-skip", action="store_true",
                        help="Reprocess tickers already in gaps table")
    parser.add_argument("--daily-only", action="store_true")
    parser.add_argument("--fivemin-only", action="store_true")
    args = parser.parse_args()

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fh = open(LOG_PATH, "a", encoding="utf-8")

    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=3, max_overflow=5, pool_pre_ping=True,
    )
    engine_ref[0] = engine

    do_daily = not args.fivemin_only
    do_5m = not args.daily_only

    # Build done-sets for resume
    done_sets: dict[str, set[str]] = {}
    if not args.no_skip and not args.dry_run:
        done_sets = already_done(engine)

    # Daily pass
    if do_daily:
        if args.tickers:
            daily_tickers = [t.upper() for t in args.tickers]
        else:
            daily_tickers = daily_universe(args.limit)

        if not args.no_skip:
            done_daily = done_sets.get("daily", set())
            before = len(daily_tickers)
            daily_tickers = [t for t in daily_tickers if t not in done_daily]
            if before != len(daily_tickers):
                _log(f"daily resume: skipping {before-len(daily_tickers)} done "
                     f"({len(daily_tickers)} remaining)", fh)

        _log(f"=== build_gaps DAILY START === universe={len(daily_tickers)} "
             f"dry_run={args.dry_run}", fh)
        d, s, e, b, r = run_pass(daily_tickers, process_daily, "daily",
                                  args.timeout, args.dry_run, fh)
        _log(f"=== build_gaps DAILY END === done={d} skip={s} err={e} "
             f"bars={b:,} rows={r:,}", fh)

    # 5m pass
    if do_5m:
        if args.tickers:
            tickers_5m = [t.upper() for t in args.tickers]
        else:
            tickers_5m = fivemin_universe(engine, args.limit)

        if not args.no_skip:
            done_5m = done_sets.get("5m", set())
            before = len(tickers_5m)
            tickers_5m = [t for t in tickers_5m if t not in done_5m]
            if before != len(tickers_5m):
                _log(f"5m resume: skipping {before-len(tickers_5m)} done "
                     f"({len(tickers_5m)} remaining)", fh)

        _log(f"=== build_gaps 5M START === universe={len(tickers_5m)} "
             f"dry_run={args.dry_run}", fh)
        d, s, e, b, r = run_pass(tickers_5m, process_5m, "5m",
                                  args.timeout, args.dry_run, fh)
        _log(f"=== build_gaps 5M END === done={d} skip={s} err={e} "
             f"bars={b:,} rows={r:,}", fh)

    fh.close()


if __name__ == "__main__":
    main()
