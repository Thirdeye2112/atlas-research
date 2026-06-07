"""
Label factory — computes forward return labels.

Moved from atlas_research/pipeline/labels.py.
Logic unchanged; DB writes now go through repository.upsert_label().

Labels are computed as soon as future bars exist in raw_bars.
Running this nightly progressively fills in labels as time passes.

Labels produced (matching the schema exactly):
    return_1d, return_5d, return_10d, return_20d, return_60d
    max_runup_20d, max_drawdown_20d
    positive_5d, positive_20d
"""

from __future__ import annotations

import math
from datetime import date

import pandas as pd

from atlas_research.db import repository
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)

# Horizons we compute, in days.
# Must match LABEL_HORIZONS_DAYS in config/settings.py.
HORIZONS = [1, 5, 10, 20, 60]
EXCURSION_HORIZON = 20   # max_runup / max_drawdown window


def build_labels_for_universe(tickers: list[str], as_of: date) -> int:
    """
    Attempt to compute and upsert labels for every ticker in the list.
    Only writes a row when enough future bars exist.

    Returns:
        Number of label rows upserted.
    """
    total = 0
    for ticker in tickers:
        n = _build_labels_for_ticker(ticker, as_of)
        total += n
    log.info("labels.built", total=total, tickers=len(tickers), as_of=str(as_of))
    return total


def _build_labels_for_ticker(ticker: str, as_of: date) -> int:
    """
    Load all bars for a ticker and backfill any label rows that can now
    be computed (i.e., sufficient future bars are available).

    Returns the number of rows upserted.
    """
    # Load the full bar history for this ticker
    bars = repository.get_bars(ticker)
    if bars.empty or len(bars) < 2:
        return 0

    bars = bars.sort_values("date").reset_index(drop=True)
    prices = bars["adjusted_close"].values
    dates  = bars["date"].dt.date.tolist()
    highs  = bars["high"].values
    lows   = bars["low"].values
    n      = len(bars)

    rows_upserted = 0

    for i, snap_date in enumerate(dates):
        # Only process dates on or before as_of
        if snap_date > as_of:
            break

        # Check we have enough future bars for the longest horizon
        max_horizon = max(HORIZONS)
        if i + max_horizon >= n:
            # Can't compute all labels for this date — skip partial
            # (we could write partial rows; for now we skip)
            continue

        row = _compute_label_row(ticker, snap_date, i, prices, highs, lows, dates)
        if row is not None:
            repository.upsert_label(row)
            rows_upserted += 1

    return rows_upserted


def _compute_label_row(
    ticker: str,
    snap_date: date,
    idx: int,
    prices,
    highs,
    lows,
    dates,
) -> dict | None:
    """Compute all label fields for one (ticker, snap_date) row."""
    entry = float(prices[idx])
    if entry <= 0:
        return None

    n = len(prices)
    row: dict = {"ticker": ticker, "date": snap_date}

    # --- Forward returns ---
    for horizon, key in [
        (1,  "return_1d"),
        (5,  "return_5d"),
        (10, "return_10d"),
        (20, "return_20d"),
        (60, "return_60d"),
    ]:
        future_idx = idx + horizon
        if future_idx < n:
            exit_price = float(prices[future_idx])
            if exit_price > 0:
                row[key] = math.log(exit_price / entry)
            else:
                row[key] = None
        else:
            row[key] = None

    # --- Binary labels ---
    r5  = row.get("return_5d")
    r20 = row.get("return_20d")
    row["positive_5d"]  = bool(r5  > 0) if r5  is not None else None
    row["positive_20d"] = bool(r20 > 0) if r20 is not None else None

    # --- Max runup / drawdown over 20-day window ---
    end_idx = idx + EXCURSION_HORIZON
    if end_idx < n:
        window_highs = highs[idx + 1 : end_idx + 1]
        window_lows  = lows[idx  + 1 : end_idx + 1]
        best_high  = float(max(window_highs))
        worst_low  = float(min(window_lows))
        row["max_runup_20d"]    = (best_high - entry) / entry
        row["max_drawdown_20d"] = (worst_low - entry) / entry
    else:
        row["max_runup_20d"]    = None
        row["max_drawdown_20d"] = None

    # Fill missing required keys with None
    for key in ["return_1d","return_5d","return_10d","return_20d","return_60d",
                "max_runup_20d","max_drawdown_20d","positive_5d","positive_20d"]:
        if key not in row:
            row[key] = None

    return row
