"""
atlas_research.probability.outcomes
--------------------------------------
Pure-pandas outcome computation.
No DB access — takes a DataFrame and a boolean mask, returns dicts.

Forward returns use close[t+h] / close[t].
Max runup uses high[t+1:t+w+1] / close[t]  (best intrabar price in window).
Max drawdown uses  low[t+1:t+w+1] / close[t] (worst intrabar price).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

HORIZONS: list[int] = [1, 3, 5, 10, 20]
RUNUP_WINDOWS: list[int] = [5, 10, 20]


def compute_event_outcomes(df: pd.DataFrame, entry_idx: int) -> dict:
    """Compute forward returns + path stats for one signal occurrence."""
    entry_close = float(df["close"].iloc[entry_idx])
    signal_date = df.index[entry_idx]
    # Convert Timestamp → date for clean DB insert
    if hasattr(signal_date, "date"):
        signal_date = signal_date.date()

    result: dict = {"signal_date": signal_date}

    for h in HORIZONS:
        end_i = entry_idx + h
        if end_i < len(df) and entry_close > 0:
            fwd = float(df["close"].iloc[end_i])
            result[f"ret_{h}d"] = round((fwd / entry_close - 1) * 100, 4)
        else:
            result[f"ret_{h}d"] = None

    for w in RUNUP_WINDOWS:
        hi = df["high"].iloc[entry_idx + 1 : entry_idx + w + 1]
        lo = df["low"].iloc[entry_idx + 1 : entry_idx + w + 1]
        if len(hi) > 0 and entry_close > 0:
            result[f"max_runup_{w}d"] = round((float(hi.max()) / entry_close - 1) * 100, 4)
            result[f"max_dd_{w}d"]    = round((float(lo.min()) / entry_close - 1) * 100, 4)
        else:
            result[f"max_runup_{w}d"] = None
            result[f"max_dd_{w}d"]    = None

    return result


def compute_all_outcomes(df: pd.DataFrame, mask: pd.Series, ticker: str = "") -> list[dict]:
    """Compute outcomes for every True position in mask."""
    positions = np.where(mask.values)[0]
    events: list[dict] = []
    for i in positions:
        ev = compute_event_outcomes(df, int(i))
        ev["ticker"] = ticker
        events.append(ev)
    return events


def aggregate_stats(events: list[dict], horizon: int) -> dict:
    """Aggregate cross-event statistics for one forward horizon."""
    key = f"ret_{horizon}d"
    rets = [e[key] for e in events if e.get(key) is not None]

    if not rets:
        return {
            "n": 0, "hit_rate": None, "avg_return": None,
            "median_return": None, "p25_return": None, "p75_return": None,
            "avg_max_runup": None, "avg_max_dd": None,
        }

    arr = np.array(rets, dtype=float)

    # Pick the runup/dd window closest to (but not exceeding) the horizon
    if horizon >= max(RUNUP_WINDOWS):
        w = max(RUNUP_WINDOWS)
    else:
        w = max((x for x in RUNUP_WINDOWS if x <= horizon), default=RUNUP_WINDOWS[0])

    runups = [e.get(f"max_runup_{w}d") for e in events if e.get(f"max_runup_{w}d") is not None]
    dds    = [e.get(f"max_dd_{w}d")    for e in events if e.get(f"max_dd_{w}d")    is not None]

    return {
        "n":             len(arr),
        "hit_rate":      round(float(np.mean(arr > 0)), 4),
        "avg_return":    round(float(np.mean(arr)), 4),
        "median_return": round(float(np.median(arr)), 4),
        "p25_return":    round(float(np.percentile(arr, 25)), 4),
        "p75_return":    round(float(np.percentile(arr, 75)), 4),
        "avg_max_runup": round(float(np.mean(runups)), 4) if runups else None,
        "avg_max_dd":    round(float(np.mean(dds)), 4)    if dds    else None,
    }


def stats_by_horizon(events: list[dict]) -> dict[int, dict]:
    return {h: aggregate_stats(events, h) for h in HORIZONS}
