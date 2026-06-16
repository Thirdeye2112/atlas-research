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

def _to_yahoo_symbol(ticker: str) -> str:
    """Map a canonical ticker to its Yahoo Finance symbol.

    Yahoo encodes share-class / preferred dots as dashes (BRK.B -> BRK-B,
    BF.B -> BF-B). We download under the Yahoo symbol but store rows under the
    canonical ticker so the rest of the pipeline is unaffected.
    """
    return ticker.replace(".", "-")


def _process_batch(
    tickers: list[str],
    start_date: date,
    yf_end_date: date,
) -> tuple[int, list[tuple[str, str]]]:
    # Map canonical -> yahoo symbol; download under yahoo, store under canonical.
    yahoo_to_canonical = {_to_yahoo_symbol(t): t for t in tickers}
    yahoo_tickers = list(yahoo_to_canonical.keys())

    try:
        raw_df = _download_batch(yahoo_tickers, start_date, yf_end_date)
    except Exception as exc:
        log.warning("ingest.download_failed", error=str(exc))
        return 0, [(t, str(exc)) for t in tickers]

    if raw_df is None or raw_df.empty:
        log.warning("ingest.empty_download", tickers=tickers[:3])
        return 0, [(t, "no data returned") for t in tickers]

    # Diagnostic: log the raw DataFrame shape and column structure once per batch
    log.info(
        "ingest.batch_downloaded",
        shape=str(raw_df.shape),
        is_multiindex=isinstance(raw_df.columns, pd.MultiIndex),
        col_levels=raw_df.columns.nlevels if isinstance(raw_df.columns, pd.MultiIndex) else 1,
        col_sample=str(list(raw_df.columns[:6])),
        tickers_in_batch=len(tickers),
    )

    total = 0
    failed = []
    for ticker in tickers:
        try:
            rows = _extract_ticker_rows(_to_yahoo_symbol(ticker), raw_df,
                                        store_as=ticker)
            if rows:
                n = repository.upsert_bars(rows)
                total += len(rows)
                log.debug(
                    "ingest.ticker_ok",
                    ticker=ticker,
                    rows=len(rows),
                    sample_date=str(rows[0]["date"]),
                    sample_adj_close=rows[0]["adjusted_close"],
                )
            else:
                log.warning("ingest.no_rows", ticker=ticker,
                            df_shape=str(raw_df.shape),
                            col_sample=str(list(raw_df.columns[:6])))
                failed.append((ticker, "no rows extracted"))
        except Exception as exc:
            import traceback
            log.warning("ingest.ticker_error", ticker=ticker, error=str(exc),
                        traceback=traceback.format_exc()[-500:])
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
        auto_adjust=False,  # keeps separate Adj Close; we read it explicitly below
        actions=False,
        group_by="ticker",
        progress=False,
    )


def _extract_ticker_rows(ticker: str, raw_df: pd.DataFrame,
                         store_as: str | None = None) -> list[dict]:
    """Pull one ticker's bars out of the batch download DataFrame.

    `ticker` is the symbol to look up inside the downloaded frame (the Yahoo
    symbol); `store_as` is the canonical ticker written to raw_bars (defaults
    to `ticker` when not remapped).

    MultiIndex flattening — exact steps in order:
      1. If ticker in level 0 values → xs(ticker, level=0, axis=1)
         Elif ticker in level 1 values → xs(ticker, level=1, axis=1)
         Else → ticker not in this DataFrame, return []
      2. After xs(), if columns are still MultiIndex → get_level_values(0)
      3. Lowercase all column names
      4. Map adj close / adjclose / adjusted close → adjusted_close
    """
    df: pd.DataFrame | None = None

    if isinstance(raw_df.columns, pd.MultiIndex):
        level0_vals = raw_df.columns.get_level_values(0)
        level1_vals = raw_df.columns.get_level_values(1)

        if ticker in level0_vals:
            df = raw_df.xs(ticker, axis=1, level=0).copy()
        elif ticker in level1_vals:
            df = raw_df.xs(ticker, axis=1, level=1).copy()
        else:
            return []
    else:
        df = raw_df.copy()

    if df is None or df.empty:
        return []

    # Step 2: flatten any residual MultiIndex left by xs()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Step 3: lowercase
    df.columns = [str(c).lower() for c in df.columns]

    # Step 4: normalise adjusted-close column name
    _adj_aliases = ["adj close", "adjclose", "adjusted close"]
    adj_col = next((a for a in _adj_aliases if a in df.columns), None)

    if adj_col is None and "close" not in df.columns:
        log.warning("ingest.missing_close_col", ticker=ticker, cols=list(df.columns))
        return []

    subset = adj_col if adj_col else "close"
    df = df.dropna(subset=[subset])
    if df.empty:
        return []

    canonical = store_as if store_as is not None else ticker
    rows = []
    for idx, row in df.iterrows():
        bar_date = idx.date() if hasattr(idx, "date") else idx
        rows.append({
            "ticker":         canonical,
            "date":           bar_date,
            "open":           _f(row.get("open")),
            "high":           _f(row.get("high")),
            "low":            _f(row.get("low")),
            "close":          _f(row.get("close")),
            "adjusted_close": _f(row.get(adj_col)) if adj_col else _f(row.get("close")),
            "volume":         _i(row.get("volume")),
            "source":         "yahoo",
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
