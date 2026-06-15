"""
atlas_research.probability.engine
------------------------------------
Core backtesting orchestration.

Public interface preserved — delegates to atlas_research.backtest.
Existing callers (API routes, scripts, sanity.py) require no changes.

Condition types (unchanged)
---------------------------
  down_streak   — N consecutive closes below prior close  (params: n)
  up_streak     — N consecutive closes above prior close  (params: n)
  gap_down      — open < prior_close * (1 - threshold/100) (params: threshold_pct)
  gap_up        — open > prior_close * (1 + threshold/100) (params: threshold_pct)
  candle        — single named candlestick pattern         (params: pattern)

Candle pattern names (unchanged)
---------------------------------
  bullish_engulfing  bearish_engulfing
  hammer             shooting_star
  doji               inside_day       outside_day
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd
from sqlalchemy import text

from atlas_research.db.connection import get_connection
from atlas_research.backtest.conditions import evaluate as _evaluate
from atlas_research.backtest.adapters import run_probability_backtest as _run

from .outcomes import compute_all_outcomes, stats_by_horizon


# ── Condition constants (kept for any callers that import them) ───────────────

STREAK_DOWN = "down_streak"
STREAK_UP   = "up_streak"
GAP_DOWN    = "gap_down"
GAP_UP      = "gap_up"
CANDLE      = "candle"


# ── Bar loading (unchanged public API) ───────────────────────────────────────

def load_bars(
    ticker: str,
    start_date: Optional[str] = None,
    end_date:   Optional[str] = None,
) -> pd.DataFrame:
    sql = "SELECT date, open, high, low, close, volume FROM raw_bars WHERE ticker = :t"
    params: dict[str, Any] = {"t": ticker}
    if start_date:
        sql += " AND date >= :start"; params["start"] = start_date
    if end_date:
        sql += " AND date <= :end";   params["end"]   = end_date
    sql += " ORDER BY date ASC"

    with get_connection() as conn:
        rows = conn.execute(text(sql), params).fetchall()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    for col in ("open", "high", "low", "close"):
        df[col] = df[col].astype(float)
    return df


# ── Condition detection (public — used by sanity.py) ─────────────────────────

def detect_condition(df: pd.DataFrame, condition_type: str, params: dict) -> pd.Series:
    """Dispatch to canonical conditions.  Returns boolean Series aligned to df."""
    return _evaluate(df, condition_type, params)


# Kept for backward compatibility — sanity.py imports these directly
def detect_consecutive_down(df: pd.DataFrame, n: int) -> pd.Series:
    return _evaluate(df, "consecutive_down", {"n_days": n})

def detect_consecutive_up(df: pd.DataFrame, n: int) -> pd.Series:
    return _evaluate(df, "consecutive_up", {"n_days": n})

def detect_gap_down(df: pd.DataFrame, threshold_pct: float = 0.5) -> pd.Series:
    return _evaluate(df, "gap_down", {"threshold_pct": threshold_pct})

def detect_gap_up(df: pd.DataFrame, threshold_pct: float = 0.5) -> pd.Series:
    return _evaluate(df, "gap_up", {"threshold_pct": threshold_pct})


# ── DB persistence (unchanged) ────────────────────────────────────────────────

def _save_run(
    spec_id: int,
    df: pd.DataFrame,
    events: list[dict],
    stats: dict[int, dict],
) -> int:
    data_start = str(df.index[0].date()) if not df.empty else None
    data_end   = str(df.index[-1].date()) if not df.empty else None

    with get_connection() as conn:
        run_id = conn.execute(text("""
            INSERT INTO backtest_runs (spec_id, data_start, data_end, n_events, status)
            VALUES (:sid, :start, :end, :n, 'complete')
            RETURNING id
        """), {"sid": spec_id, "start": data_start, "end": data_end,
               "n": len(events)}).fetchone()[0]

        for h, s in stats.items():
            if s["n"] == 0:
                continue
            conn.execute(text("""
                INSERT INTO backtest_results
                    (run_id, horizon_days, n, hit_rate, avg_return, median_return,
                     p25_return, p75_return, avg_max_runup, avg_max_dd)
                VALUES (:rid, :h, :n, :hr, :avg, :med, :p25, :p75, :ru, :dd)
                ON CONFLICT (run_id, horizon_days) DO NOTHING
            """), {
                "rid": run_id, "h": h,
                "n": s["n"], "hr": s["hit_rate"], "avg": s["avg_return"],
                "med": s["median_return"], "p25": s["p25_return"], "p75": s["p75_return"],
                "ru": s["avg_max_runup"], "dd": s["avg_max_dd"],
            })

        for e in events:
            conn.execute(text("""
                INSERT INTO backtest_events
                    (run_id, ticker, signal_date,
                     ret_1d, ret_3d, ret_5d, ret_10d, ret_20d,
                     max_runup_5d, max_runup_10d, max_runup_20d,
                     max_dd_5d, max_dd_10d, max_dd_20d)
                VALUES
                    (:run_id, :ticker, :signal_date,
                     :ret_1d, :ret_3d, :ret_5d, :ret_10d, :ret_20d,
                     :max_runup_5d, :max_runup_10d, :max_runup_20d,
                     :max_dd_5d, :max_dd_10d, :max_dd_20d)
                ON CONFLICT (run_id, ticker, signal_date) DO NOTHING
            """), {
                "run_id":       run_id,
                "ticker":       e["ticker"],
                "signal_date":  e["signal_date"],
                "ret_1d":       e.get("ret_1d"),
                "ret_3d":       e.get("ret_3d"),
                "ret_5d":       e.get("ret_5d"),
                "ret_10d":      e.get("ret_10d"),
                "ret_20d":      e.get("ret_20d"),
                "max_runup_5d":  e.get("max_runup_5d"),
                "max_runup_10d": e.get("max_runup_10d"),
                "max_runup_20d": e.get("max_runup_20d"),
                "max_dd_5d":    e.get("max_dd_5d"),
                "max_dd_10d":   e.get("max_dd_10d"),
                "max_dd_20d":   e.get("max_dd_20d"),
            })

    return int(run_id)


# ── Public API (unchanged) ────────────────────────────────────────────────────

def run_backtest(
    ticker: str,
    condition_type: str,
    params: dict,
    start_date: Optional[str] = None,
    end_date:   Optional[str] = None,
    spec_id:    Optional[int] = None,
    save:       bool = True,
) -> dict:
    """
    Run a historical probability study and return results.

    Delegates computation to atlas_research.backtest (canonical engine).
    DB persistence via _save_run() is unchanged.
    """
    result = _run(ticker, condition_type, params, start_date, end_date)

    # Re-derive events/stats in probability engine's expected format for _save_run
    if save and spec_id is not None:
        df     = load_bars(ticker, start_date, end_date)
        events = result["events"]
        stats  = result["stats"]
        run_id = _save_run(spec_id, df, events, stats)
        result["run_id"] = run_id

    return result
