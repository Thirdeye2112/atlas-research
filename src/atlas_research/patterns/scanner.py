"""
atlas_research.patterns.scanner
================================
Daily pattern scanner — runs across the full universe, detects all
candlestick patterns, computes forward outcome statistics, and writes
results to the pattern_signals table.

Run nightly after raw_bars is updated:
    python scripts/run_pattern_scan.py

Or import directly:
    from atlas_research.patterns.scanner import PatternScanner
    scanner = PatternScanner()
    scanner.run(date='2026-06-08')
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import text

from atlas_research.db.connection import get_connection
from atlas_research.patterns.candlestick import detect_patterns, PATTERN_BIAS
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)

# Forward return horizons to compute outcome stats for
OUTCOME_HORIZONS: list[int] = [1, 3, 5, 10, 20]


class PatternScanner:
    """
    Scans raw_bars for all candlestick patterns and writes signal rows
    to the pattern_signals table.

    Each row represents one (ticker, date, pattern) occurrence with:
    - pattern direction bias
    - pattern strength score
    - forward returns at 1/3/5/10/20 days (filled retroactively by
      outcome resolver once the future bars exist)
    """

    def __init__(self, lookback_days: int = 252):
        """
        lookback_days: how many calendar days of bars to load per ticker
                       for pattern detection (needs enough history for
                       avg_range calculation and multi-bar patterns).
        """
        self.lookback_days = lookback_days

    def _load_bars(
        self,
        ticker: str,
        as_of_date: date,
        engine,
    ) -> Optional[pd.DataFrame]:
        """Load raw_bars for one ticker up to as_of_date."""
        start = as_of_date - timedelta(days=self.lookback_days)
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT date, open, high, low, close, volume
                FROM raw_bars
                WHERE ticker = :ticker
                  AND date BETWEEN :start AND :end
                ORDER BY date ASC
            """), {"ticker": ticker, "start": start, "end": as_of_date}).fetchall()

        if not rows or len(rows) < 20:
            return None

        df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").astype(float)
        return df

    def _compute_strength(
        self,
        df: pd.DataFrame,
        pattern_signals: dict[str, pd.Series],
        idx,
    ) -> float:
        """
        Simple pattern strength score [0, 1]:
        - body/range ratio
        - volume confirmation (today vs 20-day avg)
        """
        try:
            bar = df.loc[idx]
            body = abs(bar["close"] - bar["open"])
            rng  = bar["high"] - bar["low"]
            body_ratio = body / rng if rng > 0 else 0.5

            vol_avg = df["volume"].rolling(20).mean().loc[idx]
            vol_ratio = min(bar["volume"] / vol_avg, 3.0) / 3.0 if vol_avg > 0 else 0.5

            return round((body_ratio * 0.6 + vol_ratio * 0.4), 4)
        except Exception:
            return 0.5

    def scan_ticker(
        self,
        ticker: str,
        as_of_date: date,
        engine,
    ) -> list[dict]:
        """
        Detect patterns for one ticker on as_of_date.
        Returns list of signal dicts ready for DB insert.
        """
        df = self._load_bars(ticker, as_of_date, engine)
        if df is None:
            return []

        signals = detect_patterns(df)

        # Only look at signals on the as_of_date bar
        target_idx = pd.Timestamp(as_of_date)
        if target_idx not in df.index:
            # Use the last available date
            target_idx = df.index[-1]
            if target_idx.date() != as_of_date:
                return []

        results = []
        for pattern_name, signal_series in signals.items():
            if signal_series.get(target_idx, False):
                strength = self._compute_strength(df, signals, target_idx)
                results.append({
                    "ticker":          ticker,
                    "signal_date":     as_of_date,
                    "pattern_name":    pattern_name,
                    "pattern_type":    _pattern_type(pattern_name),
                    "direction":       PATTERN_BIAS.get(pattern_name, "neutral"),
                    "strength_score":  strength,
                    # Forward returns filled later by outcome resolver
                    "fwd_return_1d":   None,
                    "fwd_return_3d":   None,
                    "fwd_return_5d":   None,
                    "fwd_return_10d":  None,
                    "fwd_return_20d":  None,
                })
        return results

    def run(
        self,
        scan_date: Optional[date] = None,
        tickers: Optional[list[str]] = None,
    ) -> dict:
        """
        Run the full pattern scan.

        Parameters
        ----------
        scan_date : date, optional
            Date to scan for patterns. Defaults to today.
        tickers : list[str], optional
            Subset of tickers to scan. Defaults to all in raw_bars.

        Returns
        -------
        dict with scan stats: tickers_scanned, signals_found, signals_written
        """
        if scan_date is None:
            scan_date = date.today()

        from sqlalchemy import create_engine as _create_engine
        from config import settings
        engine = _create_engine(settings.DATABASE_URL, future=True)

        # Get ticker list
        if tickers is None:
            with engine.connect() as conn:
                rows = conn.execute(text(
                    "SELECT DISTINCT ticker FROM raw_bars ORDER BY ticker"
                )).fetchall()
            tickers = [r[0] for r in rows]

        log.info("pattern_scan.start", date=str(scan_date), n_tickers=len(tickers))

        all_signals: list[dict] = []
        errors = 0

        for i, ticker in enumerate(tickers):
            try:
                signals = self.scan_ticker(ticker, scan_date, engine)
                all_signals.extend(signals)
            except Exception as exc:
                log.warning("pattern_scan.ticker_error", ticker=ticker, error=str(exc))
                errors += 1

            if (i + 1) % 50 == 0:
                log.info("pattern_scan.progress",
                         done=i + 1, total=len(tickers),
                         signals_so_far=len(all_signals))

        # Write to DB
        written = 0
        if all_signals:
            written = self._write_signals(all_signals, engine)

        # Resolve forward returns for past signals
        resolved = self._resolve_outcomes(scan_date, engine)

        stats = {
            "scan_date":       str(scan_date),
            "tickers_scanned": len(tickers),
            "signals_found":   len(all_signals),
            "signals_written": written,
            "outcomes_resolved": resolved,
            "errors":          errors,
        }
        log.info("pattern_scan.complete", **stats)
        return stats

    def _write_signals(self, signals: list[dict], engine) -> int:
        """Insert pattern signals, skip duplicates."""
        written = 0
        with engine.begin() as conn:
            for s in signals:
                try:
                    conn.execute(text("""
                        INSERT INTO pattern_signals (
                            ticker, signal_date, pattern_name, pattern_type,
                            direction, strength_score,
                            fwd_return_1d, fwd_return_3d, fwd_return_5d,
                            fwd_return_10d, fwd_return_20d
                        ) VALUES (
                            :ticker, :signal_date, :pattern_name, :pattern_type,
                            :direction, :strength_score,
                            :fwd_return_1d, :fwd_return_3d, :fwd_return_5d,
                            :fwd_return_10d, :fwd_return_20d
                        )
                        ON CONFLICT (ticker, signal_date, pattern_name) DO NOTHING
                    """), s)
                    written += 1
                except Exception as exc:
                    log.warning("pattern_scan.write_error", error=str(exc)[:100])
        return written

    def _resolve_outcomes(self, as_of_date: date, engine) -> int:
        """
        Fill forward returns for past signals that have NULL outcome columns
        and where the forward date now has bars available.
        """
        resolved = 0
        with engine.begin() as conn:
            # Find signals with missing 5d return where data should now exist
            pending = conn.execute(text("""
                SELECT id, ticker, signal_date
                FROM pattern_signals
                WHERE fwd_return_5d IS NULL
                  AND signal_date <= :cutoff
                ORDER BY signal_date DESC
                LIMIT 500
            """), {"cutoff": as_of_date - timedelta(days=7)}).fetchall()

            for row_id, ticker, signal_date in pending:
                try:
                    fwd = _compute_forward_returns(ticker, signal_date, engine)
                    if fwd:
                        conn.execute(text("""
                            UPDATE pattern_signals SET
                                fwd_return_1d  = :r1,
                                fwd_return_3d  = :r3,
                                fwd_return_5d  = :r5,
                                fwd_return_10d = :r10,
                                fwd_return_20d = :r20
                            WHERE id = :id
                        """), {**fwd, "id": row_id})
                        resolved += 1
                except Exception:
                    pass
        return resolved


def _pattern_type(name: str) -> str:
    from atlas_research.patterns.candlestick import (
        SINGLE_BAR_PATTERNS, TWO_BAR_PATTERNS, THREE_BAR_PATTERNS
    )
    if name in SINGLE_BAR_PATTERNS:  return "single_bar"
    if name in TWO_BAR_PATTERNS:     return "two_bar"
    if name in THREE_BAR_PATTERNS:   return "three_bar"
    return "other"


def _compute_forward_returns(ticker: str, signal_date: date, engine) -> Optional[dict]:
    """Compute forward returns at 1/3/5/10/20 days from signal_date."""
    import pandas as pd
    from atlas_research.backtest.adapters import compute_forward_returns_for_scanner

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT date, open, high, low, close, volume
            FROM raw_bars
            WHERE ticker = :ticker
              AND date >= :start
            ORDER BY date ASC
            LIMIT 25
        """), {"ticker": ticker, "start": signal_date}).fetchall()

    if not rows or len(rows) < 2:
        return None

    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").astype(float)

    return compute_forward_returns_for_scanner(df, signal_date)
