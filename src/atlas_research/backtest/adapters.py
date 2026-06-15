"""
atlas_research.backtest.adapters
===================================
Thin compatibility shims so existing engines can delegate to the canonical
backtest package without changing their public interfaces.

These are called FROM the existing engines (conditional, probability, patterns).
They should not be called directly by application code.
"""

from __future__ import annotations

import datetime
from typing import Optional

import pandas as pd

from .engine import BacktestEngine, ConditionSpec, OutcomeSpec
from .outcomes import forward_returns as _forward_returns, HORIZONS


# ── Shared engine instance ────────────────────────────────────────────────────
# Each process has its own engine (DB connection is per-process).

_engine: Optional[BacktestEngine] = None


def _get_engine() -> BacktestEngine:
    global _engine
    if _engine is None:
        _engine = BacktestEngine()
    return _engine


# ── ConditionalEngine adapter ─────────────────────────────────────────────────

def run_conditional_pattern(
    condition_type: str,
    params: dict,
    tickers: list[str],
    horizons: list[int],
    min_sample_size: int = 30,
    name: Optional[str] = None,
) -> dict:
    """
    Drop-in replacement for conditional/engine.py's _run_pattern_aggregate.

    Returns stats dict compatible with the old engine's _upsert_result calls:
        {horizon: {"sample_size", "hit_rate", "avg_return", "median_return",
                   "std_return", "sharpe", "p_value"}}
    """
    engine = _get_engine()
    result = engine.run_aggregate(
        tickers=tickers,
        condition_type=condition_type,
        params=params,
        horizons=horizons,
        min_sample_size=min_sample_size,
        name=name,
    )
    # Reformat to match old _upsert_result expectations
    out: dict[int, dict] = {}
    for h, s in result.stats.items():
        if s.get("n", 0) >= min_sample_size:
            out[h] = {
                "sample_size":   s["n"],
                "hit_rate":      s["hit_rate"],
                "avg_return":    s["avg_return"],
                "median_return": s["median_return"],
                "std_return":    s.get("std_return"),
                "sharpe":        s.get("sharpe"),
                "p_value":       s.get("p_value"),
            }
    return out


def run_conditional_for_ticker(
    ticker: str,
    condition_type: str,
    params: dict,
    horizons: list[int],
    min_sample_size: int = 30,
) -> dict:
    """
    Drop-in for conditional/engine.py's _run_pattern_for_ticker.
    Returns same stats dict keyed by horizon.
    """
    engine = _get_engine()
    result = engine.run(
        ticker=ticker,
        condition_type=condition_type,
        params=params,
        horizons=horizons,
        min_sample_size=min_sample_size,
    )
    out: dict[int, dict] = {}
    for h, s in result.stats.items():
        if s.get("n", 0) >= min_sample_size:
            out[h] = {
                "sample_size":   s["n"],
                "hit_rate":      s["hit_rate"],
                "avg_return":    s["avg_return"],
                "median_return": s["median_return"],
                "std_return":    s.get("std_return"),
                "sharpe":        s.get("sharpe"),
                "p_value":       s.get("p_value"),
            }
    return out


# ── ProbabilityEngine adapter ─────────────────────────────────────────────────

def run_probability_backtest(
    ticker: str,
    condition_type: str,
    params: dict,
    start_date: Optional[str] = None,
    end_date:   Optional[str] = None,
) -> dict:
    """
    Drop-in for probability/engine.py's run_backtest().

    Returns the same structure:
        {ticker, condition_type, params, n_events, data_start, data_end,
         events, stats, run_id=None}
    """
    engine = _get_engine()
    result = engine.run(
        ticker=ticker,
        condition_type=condition_type,
        params=params,
        start_date=start_date,
        end_date=end_date,
    )

    # Reformat stats to match old probability engine shape
    stats_compat: dict[int, dict] = {}
    for h, s in result.stats.items():
        stats_compat[h] = {
            "n":             s.get("n", 0),
            "hit_rate":      s.get("hit_rate"),
            "avg_return":    s.get("avg_return"),
            "median_return": s.get("median_return"),
            "p25_return":    s.get("p25_return"),
            "p75_return":    s.get("p75_return"),
            "avg_max_runup": s.get("avg_max_runup"),
            "avg_max_dd":    s.get("avg_max_dd"),
        }

    return {
        "ticker":         ticker,
        "condition_type": condition_type,
        "params":         params,
        "n_events":       result.n_events,
        "data_start":     result.data_start,
        "data_end":       result.data_end,
        "events":         result.events,
        "stats":          stats_compat,
        "run_id":         None,  # caller handles DB persistence
    }


# ── PatternScanner adapter ────────────────────────────────────────────────────

def compute_forward_returns_for_scanner(
    df: pd.DataFrame,
    signal_date: datetime.date,
) -> Optional[dict]:
    """
    Drop-in for patterns/scanner.py's _compute_forward_returns().

    Accepts an already-loaded DataFrame (scanner loads bars itself).
    Returns {"r1": float|None, "r3": ..., "r5": ..., "r10": ..., "r20": ...}
    or None if no data.
    """
    result = _forward_returns(df, signal_date, horizons=[1, 3, 5, 10, 20])
    if result is None:
        return None
    return {
        "r1":  result.get("ret_1d"),
        "r3":  result.get("ret_3d"),
        "r5":  result.get("ret_5d"),
        "r10": result.get("ret_10d"),
        "r20": result.get("ret_20d"),
    }
