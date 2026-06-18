"""
Atlas Intraday 5-Minute Learning Engine v1 -- Data Ingestion
=============================================================
Downloads 5-minute bars for the configured universe, computes features,
detects setups, computes outcomes, attaches daily context, and writes to DB.

Usage:
    python scripts/ingest_intraday_5m.py
    python scripts/ingest_intraday_5m.py --tickers SPY QQQ AAPL
    python scripts/ingest_intraday_5m.py --period 30d
    python scripts/ingest_intraday_5m.py --dry-run

Vendor abstraction: currently Yahoo Finance (free, ~60d lookback).
Interface is designed for Polygon/Databento/Alpaca drop-in.

Does NOT auto-trade. Does NOT modify daily signals.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from atlas_research.intraday.features import compute_features
from atlas_research.intraday.setups   import detect_all_setups
from atlas_research.intraday.outcomes import compute_outcomes, DEFAULT_HORIZONS

DATABASE_URL = os.environ["DATABASE_URL"]

UNIVERSE_DEFAULT = [
    "SPY", "QQQ",
    "AAPL", "MSFT", "NVDA", "TSLA", "AMD", "META", "AMZN", "GOOGL",
]

TIMEFRAME = "5m"
ANALYSIS_ONLY = True


# ---------------------------------------------------------------------------
# Vendor abstraction
# ---------------------------------------------------------------------------

class IntradayVendor:
    """Base class. Swap subclass to change data source."""

    def fetch(self, ticker: str, period: str) -> pd.DataFrame:
        raise NotImplementedError


class YahooVendor(IntradayVendor):
    """
    Yahoo Finance via yfinance.
    Free tier: ~60 days of 5-min bars (sometimes 30 days, depending on ticker).
    """

    def fetch(self, ticker: str, period: str = "60d") -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError:
            raise ImportError("pip install yfinance")

        # Download single ticker (not multi-ticker) to avoid MultiIndex
        raw = yf.download(
            ticker,
            period=period,
            interval="5m",
            auto_adjust=True,
            progress=False,
        )
        if raw is None or raw.empty:
            return pd.DataFrame()

        # Flatten columns (yfinance sometimes returns MultiIndex even for one ticker)
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = [c[0].lower() for c in raw.columns]
        else:
            raw.columns = [c.lower() for c in raw.columns]

        raw = raw.reset_index()
        # Rename index column (Datetime or Date)
        for possible in ["Datetime", "datetime", "Date", "date"]:
            if possible in raw.columns:
                raw = raw.rename(columns={possible: "ts"})
                break

        # Drop 'adj close' if present (auto_adjust=True already adjusts)
        raw = raw.drop(columns=[c for c in raw.columns if "adj" in c.lower()], errors="ignore")

        raw["ticker"]    = ticker
        raw["timeframe"] = TIMEFRAME
        raw["source"]    = "yahoo"

        # Coerce types
        for col in ["open", "high", "low", "close"]:
            if col in raw.columns:
                raw[col] = pd.to_numeric(raw[col], errors="coerce")
        if "volume" in raw.columns:
            raw["volume"] = pd.to_numeric(raw["volume"], errors="coerce").fillna(0).astype(int)

        # Normalize timestamp to UTC
        if not pd.api.types.is_datetime64_any_dtype(raw["ts"]):
            raw["ts"] = pd.to_datetime(raw["ts"])
        if raw["ts"].dt.tz is None:
            raw["ts"] = raw["ts"].dt.tz_localize("America/New_York", ambiguous="NaT", nonexistent="NaT")
        raw["ts"] = raw["ts"].dt.tz_convert("UTC")

        # Filter to regular market hours (9:30–16:00 ET)
        local = raw["ts"].dt.tz_convert("America/New_York")
        tod   = local.dt.hour * 60 + local.dt.minute
        raw   = raw[(tod >= 570) & (tod < 960)].copy()   # 9:30 <= t < 16:00

        # Drop rows with bad prices
        raw = raw.dropna(subset=["open", "high", "low", "close"])
        raw = raw[raw["close"] > 0]

        return raw[["ticker", "ts", "timeframe", "open", "high", "low", "close", "volume", "source"]]


class AlpacaVendor(IntradayVendor):
    """
    Alpaca market data (alpaca-py). Free tier = IEX feed, multi-year 5m history
    (far deeper than Yahoo's ~60 days). One request per ticker pulls the whole
    [start, end] range (alpaca-py paginates internally). RTH-filtered to match
    the Yahoo path so downstream code is vendor-agnostic.
    """

    def __init__(self, key: str, secret: str, start, end=None, feed: str = "iex"):
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.enums import DataFeed
        self._client = StockHistoricalDataClient(key, secret)
        self._start = start
        self._end = end
        self._feed = DataFeed.SIP if feed == "sip" else DataFeed.IEX

    def fetch(self, ticker: str, period: str = None) -> pd.DataFrame:  # period ignored
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
        req = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame(5, TimeFrameUnit.Minute),
            start=self._start, end=self._end, feed=self._feed,
        )
        df = self._client.get_stock_bars(req).df
        if df is None or len(df) == 0:
            return pd.DataFrame()
        df = df.reset_index()                      # symbol, timestamp, o/h/l/c/volume, ...
        df = df.rename(columns={"timestamp": "ts"})
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
        # Regular trading hours only (9:30–16:00 ET)
        local = df["ts"].dt.tz_convert("America/New_York")
        tod = local.dt.hour * 60 + local.dt.minute
        df = df[(tod >= 570) & (tod < 960)].copy()
        for col in ["open", "high", "low", "close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(int)
        df = df.dropna(subset=["open", "high", "low", "close"])
        df = df[df["close"] > 0]
        df["ticker"] = ticker
        df["timeframe"] = TIMEFRAME
        df["source"] = "alpaca_iex" if self._feed.value == "iex" else "alpaca_sip"
        return df[["ticker", "ts", "timeframe", "open", "high", "low", "close", "volume", "source"]]


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

_BAR_COLS = ["ticker", "ts", "timeframe", "open", "high", "low", "close", "volume", "source"]


def upsert_bars(df: pd.DataFrame, engine) -> int:
    """
    Bulk-load via COPY into a TEMP staging table, then one INSERT...SELECT
    ...ON CONFLICT DO NOTHING into intraday_bars. Orders of magnitude faster
    than per-row/batched INSERTs for the ~86k-bars-per-ticker deep history.
    """
    if df.empty:
        return 0
    buf = io.StringIO()
    df[_BAR_COLS].to_csv(buf, index=False, header=False)
    buf.seek(0)

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("""
            CREATE TEMP TABLE _stage_bars (
                ticker text, ts timestamptz, timeframe text,
                open double precision, high double precision, low double precision,
                close double precision, volume bigint, source text
            ) ON COMMIT DROP
        """)
        cur.copy_expert(
            "COPY _stage_bars (ticker, ts, timeframe, open, high, low, close, volume, source) "
            "FROM STDIN WITH (FORMAT csv)",
            buf,
        )
        cur.execute("""
            INSERT INTO intraday_bars
                (ticker, ts, timeframe, open, high, low, close, volume, source)
            SELECT ticker, ts, timeframe, open, high, low, close, volume, source
            FROM _stage_bars
            ON CONFLICT (ticker, ts, timeframe) DO NOTHING
        """)
        raw.commit()
    finally:
        raw.close()
    return len(df)


def upsert_setups(rows: list[dict], engine) -> int:
    if not rows:
        return 0
    sql = text("""
    INSERT INTO intraday_setups
        (setup_id, ticker, ts, timeframe, setup_type, direction,
         confidence_inputs, daily_conviction, daily_regime, daily_vix_regime,
         daily_ml_rank, daily_confluence, daily_jarvis)
    VALUES
        (:setup_id, :ticker, :ts, :timeframe, :setup_type, :direction,
         :confidence_inputs, :daily_conviction, :daily_regime, :daily_vix_regime,
         :daily_ml_rank, :daily_confluence, :daily_jarvis)
    ON CONFLICT (setup_id) DO NOTHING
    """)
    BATCH = 500
    total = 0
    for start in range(0, len(rows), BATCH):
        batch = rows[start:start + BATCH]
        with engine.begin() as conn:
            conn.execute(sql, batch)
        total += len(batch)
    return total


def upsert_outcomes(rows: list[dict], engine) -> int:
    if not rows:
        return 0
    sql = text("""
    INSERT INTO intraday_outcomes
        (setup_id, horizon_bars, future_return, mfe, mae,
         hit_target, hit_stop, time_to_target, time_to_stop)
    VALUES
        (:setup_id, :horizon_bars, :future_return, :mfe, :mae,
         :hit_target, :hit_stop, :time_to_target, :time_to_stop)
    ON CONFLICT (setup_id, horizon_bars) DO NOTHING
    """)
    BATCH = 1000
    total = 0
    for start in range(0, len(rows), BATCH):
        batch = rows[start:start + BATCH]
        with engine.begin() as conn:
            conn.execute(sql, batch)
        total += len(batch)
    return total


# ---------------------------------------------------------------------------
# Daily context attachment
# ---------------------------------------------------------------------------

def load_daily_context(tickers: list[str], engine) -> pd.DataFrame:
    """Load most recent daily prediction context per ticker from prediction_outcomes."""
    ticker_list = ",".join(f"'{t}'" for t in tickers)
    sql = f"""
    SELECT DISTINCT ON (ticker)
        ticker,
        prediction_date::date   AS context_date,
        conviction_level,
        sector_regime,
        vix_regime,
        ml_signal_strength,
        confluence_score,
        jarvis_green
    FROM prediction_outcomes
    WHERE ticker IN ({ticker_list})
    ORDER BY ticker, prediction_date DESC
    """
    try:
        return pd.read_sql(sql, engine)
    except Exception:
        return pd.DataFrame()


def attach_daily_context(setups_df: pd.DataFrame, context_df: pd.DataFrame) -> pd.DataFrame:
    """Join daily context to setups by ticker (latest context per ticker)."""
    if context_df.empty or setups_df.empty:
        for col in ["daily_conviction", "daily_regime", "daily_vix_regime",
                    "daily_ml_rank", "daily_confluence", "daily_jarvis"]:
            setups_df[col] = None
        return setups_df

    ctx = context_df.rename(columns={
        "conviction_level":  "daily_conviction",
        "sector_regime":     "daily_regime",
        "vix_regime":        "daily_vix_regime",
        "ml_signal_strength": "daily_ml_rank",
        "confluence_score":  "daily_confluence",
        "jarvis_green":      "daily_jarvis",
    })[["ticker", "daily_conviction", "daily_regime", "daily_vix_regime",
        "daily_ml_rank", "daily_confluence", "daily_jarvis"]]

    return setups_df.merge(ctx, on="ticker", how="left")


# ---------------------------------------------------------------------------
# Pipeline for a single ticker
# ---------------------------------------------------------------------------

def get_db_universe(engine, min_dvol: float, limit: int | None) -> list[str]:
    """All tickers in raw_bars, ordered by recent dollar volume (liquid first)."""
    sql = text("""
        WITH recent AS (
            SELECT ticker, avg(close * volume) AS dvol
            FROM raw_bars
            WHERE date >= (SELECT max(date) - 60 FROM raw_bars)
            GROUP BY ticker
        )
        SELECT ticker FROM recent
        WHERE dvol >= :min_dvol
        ORDER BY dvol DESC NULLS LAST
    """)
    with engine.begin() as conn:
        rows = conn.execute(sql, {"min_dvol": min_dvol}).fetchall()
    tickers = [r[0] for r in rows]
    return tickers[:limit] if limit else tickers


def already_ingested(engine, source_prefix: str | None = None) -> set[str]:
    """
    Tickers that already have 5m bars (for --resume).

    When source_prefix is given (e.g. 'alpaca'), only count tickers already
    pulled from THAT source — so a deep Alpaca pull doesn't skip tickers that
    only have shallow 60-day Yahoo bars.
    """
    sql = "SELECT DISTINCT ticker FROM intraday_bars WHERE timeframe = :tf"
    params = {"tf": TIMEFRAME}
    if source_prefix:
        sql += " AND source LIKE :sp"
        params["sp"] = f"{source_prefix}%"
    with engine.begin() as conn:
        rows = conn.execute(text(sql), params).fetchall()
    return {r[0] for r in rows}


def process_ticker(
    ticker: str,
    vendor: IntradayVendor,
    period: str,
    daily_ctx: pd.DataFrame,
    dry_run: bool,
    engine,
    bars_only: bool = False,
) -> dict:
    result = {"ticker": ticker, "bars": 0, "setups": 0, "outcomes": 0, "error": None}

    # 1. Download bars
    try:
        bars_df = vendor.fetch(ticker, period)
    except Exception as e:
        result["error"] = f"download_failed: {e}"
        return result

    if bars_df.empty:
        result["error"] = "no_bars"
        return result

    result["bars"] = len(bars_df)

    if not dry_run:
        upsert_bars(bars_df, engine)

    # Bars-only fast path: skip features/setups/outcomes (derive later).
    if bars_only:
        return result

    # 2. Compute features
    try:
        feat_df = compute_features(bars_df)
    except Exception as e:
        result["error"] = f"features_failed: {e}"
        return result

    # 3. Detect setups
    try:
        setups_df = detect_all_setups(feat_df, ticker)
    except Exception as e:
        result["error"] = f"setups_failed: {e}"
        return result

    if setups_df.empty:
        return result

    result["setups"] = len(setups_df)

    # 4. Compute outcomes
    try:
        outcomes_df = compute_outcomes(bars_df, setups_df, DEFAULT_HORIZONS)
    except Exception as e:
        result["error"] = f"outcomes_failed: {e}"
        return result

    result["outcomes"] = len(outcomes_df)

    if dry_run:
        return result

    # 5. Attach daily context
    ticker_ctx = daily_ctx[daily_ctx["ticker"] == ticker] if not daily_ctx.empty else pd.DataFrame()
    setups_with_ctx = attach_daily_context(setups_df.copy(), ticker_ctx)

    # 6. Prepare and upsert setups
    setup_rows = []
    for _, row in setups_with_ctx.iterrows():
        def _sf(v):
            if v is None:
                return None
            try:
                f = float(v)
                return None if f != f else f
            except (TypeError, ValueError):
                return None

        setup_rows.append({
            "setup_id":          row.get("setup_id"),
            "ticker":            ticker,
            "ts":                row.get("ts"),
            "timeframe":         TIMEFRAME,
            "setup_type":        row.get("setup_type"),
            "direction":         row.get("direction"),
            "confidence_inputs": row.get("confidence_inputs"),
            "daily_conviction":  row.get("daily_conviction"),
            "daily_regime":      row.get("daily_regime"),
            "daily_vix_regime":  row.get("daily_vix_regime"),
            "daily_ml_rank":     _sf(row.get("daily_ml_rank")),
            "daily_confluence":  _sf(row.get("daily_confluence")),
            "daily_jarvis":      bool(row["daily_jarvis"]) if row.get("daily_jarvis") is not None else None,
        })
    upsert_setups(setup_rows, engine)

    # 7. Upsert outcomes
    if not outcomes_df.empty:
        outcome_rows = []
        for _, row in outcomes_df.iterrows():
            def _sf2(v):
                if v is None:
                    return None
                try:
                    f = float(v)
                    return None if f != f else f
                except (TypeError, ValueError):
                    return None
            def _si(v):
                if v is None:
                    return None
                try:
                    f = float(v)
                    return None if f != f else int(f)
                except (TypeError, ValueError):
                    return None

            outcome_rows.append({
                "setup_id":       row.get("setup_id"),
                "horizon_bars":   int(row.get("horizon_bars", 0)),
                "future_return":  _sf2(row.get("future_return")),
                "mfe":            _sf2(row.get("mfe")),
                "mae":            _sf2(row.get("mae")),
                "hit_target":     bool(row["hit_target"]) if row.get("hit_target") is not None else None,
                "hit_stop":       bool(row["hit_stop"])   if row.get("hit_stop")   is not None else None,
                "time_to_target": _si(row.get("time_to_target")),
                "time_to_stop":   _si(row.get("time_to_stop")),
            })
        upsert_outcomes(outcome_rows, engine)

    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", nargs="+", default=None,
                        help="Tickers to ingest (default: 10-ticker watchlist)")
    parser.add_argument("--all", action="store_true",
                        help="Ingest every ticker in raw_bars (ordered by recent liquidity)")
    parser.add_argument("--min-dvol", type=float, default=0.0,
                        help="With --all: skip tickers below this recent avg dollar volume")
    parser.add_argument("--limit", type=int, default=None,
                        help="With --all: cap number of tickers (most liquid first)")
    parser.add_argument("--resume", action="store_true",
                        help="Skip tickers that already have 5m bars")
    parser.add_argument("--bars-only", action="store_true",
                        help="Ingest bars only; skip features/setups/outcomes (fast bulk pull)")
    parser.add_argument("--workers", type=int, default=1,
                        help="Concurrent download workers (network-bound; try 5-8 for Alpaca bulk)")
    parser.add_argument("--vendor", choices=["yahoo", "alpaca"], default="yahoo",
                        help="Data vendor (alpaca = multi-year IEX 5m history)")
    parser.add_argument("--start", default=None,
                        help="Alpaca: history start YYYY-MM-DD (default ~3 years ago)")
    parser.add_argument("--feed", choices=["iex", "sip"], default="iex",
                        help="Alpaca feed (iex=free, sip=paid)")
    parser.add_argument("--period",  default="60d",
                        help="Yahoo lookback period (e.g. 30d, 60d)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Download and process but do not write to DB")
    args = parser.parse_args()

    period  = args.period
    dry_run = args.dry_run

    engine = create_engine(DATABASE_URL, pool_size=max(5, args.workers + 2),
                            max_overflow=10, pool_pre_ping=True)
    if args.vendor == "alpaca":
        start = (datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                 if args.start else datetime.now(timezone.utc) - timedelta(days=365 * 3))
        vendor = AlpacaVendor(os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"],
                              start=start, feed=args.feed)
        print(f"Vendor: Alpaca ({args.feed}) from {start.date()}")
    else:
        vendor = YahooVendor()
        print("Vendor: Yahoo (60d cap)")

    if args.tickers:
        tickers = args.tickers
    elif args.all:
        tickers = get_db_universe(engine, args.min_dvol, args.limit)
    else:
        tickers = UNIVERSE_DEFAULT

    if args.resume:
        # For Alpaca, only skip tickers already pulled from Alpaca (not shallow Yahoo).
        done = already_ingested(engine, "alpaca" if args.vendor == "alpaca" else None)
        before = len(tickers)
        tickers = [t for t in tickers if t not in done]
        print(f"--resume: skipping {before - len(tickers)} tickers already ingested")

    print("=== Atlas Intraday 5-Minute Learning Engine v1 -- Ingestion ===")
    print(f"Universe: {len(tickers)} tickers   period={period}   "
          f"bars_only={args.bars_only}   dry_run={dry_run}")
    print("ANALYSIS ONLY -- no live trading state modified")
    print()

    # Load daily context once (skipped for bars-only bulk pulls)
    if args.bars_only:
        daily_ctx = pd.DataFrame()
    else:
        print("[pre] Loading daily prediction context...")
        daily_ctx = load_daily_context(tickers, engine)
        print(f"  Context rows: {len(daily_ctx)}" if not daily_ctx.empty
              else "  No daily context available")

    total_bars = total_setups = total_outcomes = 0
    errors = no_data = 0
    n = len(tickers)
    lock = threading.Lock()
    done = 0

    def _tally(res):
        nonlocal total_bars, total_setups, total_outcomes, errors, no_data, done
        with lock:
            total_bars     += res["bars"]
            total_setups   += res["setups"]
            total_outcomes += res["outcomes"]
            if res["error"] == "no_bars":
                no_data += 1
            elif res["error"]:
                errors += 1
            done += 1
            if done % 50 == 0 or done == n:
                print(f"[{done}/{n}] bars={total_bars:,} setups={total_setups:,} "
                      f"no_data={no_data} errors={errors}", flush=True)

    if args.workers > 1:
        # Network-bound concurrent fetch (each worker uses its own DB connection
        # from the pool and its own HTTP request; COPY upsert is thread-safe).
        def work(tk):
            return process_ticker(tk, vendor, period, daily_ctx, dry_run, engine,
                                  bars_only=args.bars_only)
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            for fut in as_completed(ex.submit(work, tk) for tk in tickers):
                _tally(fut.result())
    else:
        for ticker in tickers:
            res = process_ticker(ticker, vendor, period, daily_ctx, dry_run, engine,
                                 bars_only=args.bars_only)
            _tally(res)
            time.sleep(0.5)   # be polite (sequential / Yahoo)

    print()
    print("=== Summary ===")
    print(f"  Tickers attempted:  {len(tickers):,}")
    print(f"  Bars ingested:      {total_bars:,}")
    print(f"  Setups detected:    {total_setups:,}")
    print(f"  Outcomes computed:  {total_outcomes:,}")
    print(f"  No data (skipped):  {no_data:,}")
    print(f"  Errors:             {errors:,}")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
