"""
atlas_research.backtest.outcomes
==================================
Canonical forward-return and path-statistic computation.

All returns are **percentage returns**: (close[t+h] / close[t] - 1) * 100
No log returns.  No DB access.

Public API
----------
    compute_all(df, mask, ticker, horizons, runup_windows) -> list[dict]
    forward_returns(df, signal_idx_or_date, horizons)      -> dict
"""

from __future__ import annotations

import datetime
from typing import Optional, Union

import numpy as np
import pandas as pd

HORIZONS:      list[int] = [1, 3, 5, 10, 20]
RUNUP_WINDOWS: list[int] = [5, 10, 20]


def _pct(start: float, end: float) -> float:
    return (end / start - 1) * 100.0


def compute_event(
    df: pd.DataFrame,
    idx: int,
    horizons: list[int] = HORIZONS,
    runup_windows: list[int] = RUNUP_WINDOWS,
) -> dict:
    """Compute forward returns + path stats for one signal bar (by integer position)."""
    entry_close = float(df["close"].iloc[idx])
    signal_date = df.index[idx]
    if hasattr(signal_date, "date"):
        signal_date = signal_date.date()

    result: dict = {"signal_date": signal_date}

    for h in horizons:
        end_i = idx + h
        if end_i < len(df) and entry_close > 0:
            result[f"ret_{h}d"] = round(_pct(entry_close, float(df["close"].iloc[end_i])), 4)
        else:
            result[f"ret_{h}d"] = None

    for w in runup_windows:
        future_hi = df["high"].iloc[idx + 1 : idx + w + 1]
        future_lo = df["low"].iloc[idx + 1 : idx + w + 1]
        if len(future_hi) > 0 and entry_close > 0:
            result[f"max_runup_{w}d"] = round(_pct(entry_close, float(future_hi.max())), 4)
            result[f"max_dd_{w}d"]    = round(_pct(entry_close, float(future_lo.min())), 4)
        else:
            result[f"max_runup_{w}d"] = None
            result[f"max_dd_{w}d"]    = None

    return result


def compute_all(
    df: pd.DataFrame,
    mask: pd.Series,
    ticker: str = "",
    horizons: list[int] = HORIZONS,
    runup_windows: list[int] = RUNUP_WINDOWS,
) -> list[dict]:
    """Compute outcomes for every True bar in mask."""
    positions = np.where(mask.values)[0]
    events: list[dict] = []
    for i in positions:
        ev = compute_event(df, int(i), horizons, runup_windows)
        ev["ticker"] = ticker
        events.append(ev)
    return events


def forward_returns(
    df: pd.DataFrame,
    signal: Union[int, datetime.date, str],
    horizons: list[int] = HORIZONS,
) -> Optional[dict]:
    """
    Compute forward returns from a signal date or integer position.
    Used by patterns.scanner for retroactive outcome resolution.

    Returns dict of {f"ret_{h}d": float | None} or None if no data.
    """
    if isinstance(signal, int):
        idx = signal
    else:
        date_str = str(signal)[:10]
        matches = [i for i, d in enumerate(df.index) if str(d)[:10] == date_str]
        if not matches:
            return None
        idx = matches[0]

    if idx >= len(df):
        return None

    entry_close = float(df["close"].iloc[idx])
    if entry_close <= 0:
        return None

    result: dict = {}
    for h in horizons:
        end_i = idx + h
        result[f"ret_{h}d"] = (
            round(_pct(entry_close, float(df["close"].iloc[end_i])), 6)
            if end_i < len(df) else None
        )
    return result
