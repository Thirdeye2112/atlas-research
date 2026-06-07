"""
Yahoo Finance ingest — moved from atlas_research/pipeline/ingest.py.

Core download logic unchanged (yfinance, batched, retried).
Writes now go through repository.upsert_bars() instead of inline SQL.
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from atlas_research.db import repository
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)


def download_universe(
    tickers: list[str],
    start_date: date,
    end_date: date,
    *,
    batch_size: int = 50,
    batch_delay: float = 2.0,
) -> tuple[int, list[tuple[str, str]]]:
    """
    Download OHLCV for all tickers and upsert to raw_bars.

    Args:
        tickers:     List of ticker symbols.
        start_date:  First bar date (inclusive).
        end_date:    Last bar date (inclusive; yfinance end is exclusive so +1d internally).
        batch_size:  Tickers per yfinance download call.
        batch_delay: Seconds to sleep between batches.

    Returns:
        (total_bars_inserted, [(ticker, error_message), ...])
    """
    yf_end = end_date + timedelta(days=1)  # yfinance end is exclusive

    batches = [tickers[i:i + batch_size] for i in range(0, len(tickers), batch_size)]
    total_bars = 0
    failed: list[tuple[str, str]] = []

    for batch_num, batch in enumerate(batches, 1):
        log.debug("ingest.batch", batch=batch_num, of=len(batches), size=len(batch))
        bars, errs = _process_batch(batch, start_date, yf_end)
        total_bars += bars
        failed.extend(errs)
        if batch_num < len(batches):
            time.sleep(batch_delay)

    log.info("ingest.done", total_bars=total_bars, failed=len(failed))
    return total_bars, failed


def download_ticker(
    ticker: str,
    start_date: date,
    end_date: date,
) -> int:
    """Download and upsert a single ticker. Returns bars inserted."""
    bars, errs = _process_batch([ticker], start_date, end_date + timedelta(days=1))
    if errs:
        raise RuntimeError(errs[0][1])
    return bars


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _process_batch(
    tickers: list[str],
    start_date: date,
    yf_end_date: date,
) -> tuple[int, list[tuple[str, str]]]:
    try:
        raw_df = _download_batch(tickers, start_date, yf_end_date)
    except Exception as exc:
        return 0, [(t, str(exc)) for t in tickers]

    if raw_df is None or raw_df.empty:
        return 0, [(t, "no data returned") for t in tickers]

    total = 0
    failed = []
    for ticker in tickers:
        try:
            rows = _extract_ticker_rows(ticker, raw_df)
            if rows:
                repository.upsert_bars(rows)
                total += len(rows)
            else:
                failed.append((ticker, "no rows extracted"))
        except Exception as exc:
            log.warning("ingest.ticker_error", ticker=ticker, error=str(exc))
            failed.append((ticker, str(exc)))

    return total, failed


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=30),
    reraise=True,
)
def _download_batch(tickers: list[str], start: date, end: date) -> pd.DataFrame:
    return yf.download(
        tickers=tickers,
        start=str(start),
        end=str(end),
        interval="1d",
        auto_adjust=True,   # Close == adjusted_close
        actions=False,
        group_by="ticker",
        threads=True,
        progress=False,
        show_errors=False,
    )


def _extract_ticker_rows(ticker: str, raw_df: pd.DataFrame) -> list[dict]:
    """Pull one ticker's bars out of the batch download DataFrame."""
    if isinstance(raw_df.columns, pd.MultiIndex):
        try:
            df = raw_df.xs(ticker, axis=1, level=1).copy()
        except KeyError:
            return []
    else:
        df = raw_df.copy()

    if df.empty:
        return []

    df.columns = [c.lower().replace(" ", "_") for c in df.columns]

    # auto_adjust=True → Close is adjusted; no separate Adj Close column
    if "close" not in df.columns:
        return []

    df = df.dropna(subset=["close"])
    if df.empty:
        return []

    rows = []
    for idx, row in df.iterrows():
        bar_date = idx.date() if hasattr(idx, "date") else idx
        rows.append({
            "ticker": ticker,
            "date": bar_date,
            "open": _f(row.get("open")),
            "high": _f(row.get("high")),
            "low": _f(row.get("low")),
            "close": _f(row.get("close")),
            "adjusted_close": _f(row.get("close")),  # same when auto_adjust=True
            "volume": _i(row.get("volume")),
            "source": "yahoo",
        })
    return rows


def _f(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if (np.isnan(f) or np.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _i(val: Any) -> int | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if np.isnan(f) else int(f)
    except (TypeError, ValueError):
        return None
