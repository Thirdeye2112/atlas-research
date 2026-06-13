"""
atlas_research.probability.engine
------------------------------------
Core backtesting orchestration.

Condition types
---------------
  down_streak   — N consecutive closes below prior close  (params: n)
  up_streak     — N consecutive closes above prior close  (params: n)
  gap_down      — open < prior_close * (1 - threshold/100) (params: threshold_pct)
  gap_up        — open > prior_close * (1 + threshold/100) (params: threshold_pct)
  candle        — single named candlestick pattern        (params: pattern)

Candle pattern names (user-facing → internal)
---------------------------------------------
  bullish_engulfing  bearish_engulfing
  hammer             shooting_star
  doji               inside_day       outside_day
  (plus any pattern name from atlas_research.patterns.candlestick)

Entry price: close of the signal bar.
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd
from sqlalchemy import text

from atlas_research.db.connection import get_connection
from atlas_research.patterns.candlestick import detect_patterns

from .outcomes import compute_all_outcomes, stats_by_horizon

# ── Condition type constants ──────────────────────────────────────────────────

STREAK_DOWN = "down_streak"
STREAK_UP   = "up_streak"
GAP_DOWN    = "gap_down"
GAP_UP      = "gap_up"
CANDLE      = "candle"

# User-facing pattern names → internal candlestick module names
_CANDLE_ALIAS: dict[str, str] = {
    "bullish_engulfing": "engulfing_bull",
    "bearish_engulfing": "engulfing_bear",
    "hammer":            "hammer",
    "shooting_star":     "shooting_star",
    "doji":              "doji",
    # inside_day / outside_day handled locally (not in candlestick module)
    "inside_day":        "_inside_day",
    "outside_day":       "_outside_day",
}


# ── Bar loading ───────────────────────────────────────────────────────────────

def load_bars(
    ticker: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> pd.DataFrame:
    sql = "SELECT date, open, high, low, close, volume FROM raw_bars WHERE ticker = :t"
    params: dict[str, Any] = {"t": ticker}
    if start_date:
        sql += " AND date >= :start"
        params["start"] = start_date
    if end_date:
        sql += " AND date <= :end"
        params["end"] = end_date
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


# ── Condition detectors ───────────────────────────────────────────────────────

def detect_consecutive_down(df: pd.DataFrame, n: int) -> pd.Series:
    """True on the bar where close has been lower than prior close for n bars."""
    down = (df["close"] < df["close"].shift(1)).fillna(False).astype(int)
    return (down.rolling(n).sum() == n).fillna(False)


def detect_consecutive_up(df: pd.DataFrame, n: int) -> pd.Series:
    """True on the bar where close has been higher than prior close for n bars."""
    up = (df["close"] > df["close"].shift(1)).fillna(False).astype(int)
    return (up.rolling(n).sum() == n).fillna(False)


def detect_gap_down(df: pd.DataFrame, threshold_pct: float = 0.5) -> pd.Series:
    """True when open gaps down more than threshold_pct% below prior close."""
    gap = (df["open"] / df["close"].shift(1) - 1) * 100
    return (gap < -threshold_pct).fillna(False)


def detect_gap_up(df: pd.DataFrame, threshold_pct: float = 0.5) -> pd.Series:
    """True when open gaps up more than threshold_pct% above prior close."""
    gap = (df["open"] / df["close"].shift(1) - 1) * 100
    return (gap > threshold_pct).fillna(False)


def _detect_inside_day(df: pd.DataFrame) -> pd.Series:
    """Today's high/low range is fully inside yesterday's range."""
    return (
        (df["high"] < df["high"].shift(1)) & (df["low"] > df["low"].shift(1))
    ).fillna(False)


def _detect_outside_day(df: pd.DataFrame) -> pd.Series:
    """Today's high/low range engulfs yesterday's range."""
    return (
        (df["high"] > df["high"].shift(1)) & (df["low"] < df["low"].shift(1))
    ).fillna(False)


def detect_condition(df: pd.DataFrame, condition_type: str, params: dict) -> pd.Series:
    """Dispatch to the correct detector; return a boolean Series aligned to df."""
    if condition_type == STREAK_DOWN:
        return detect_consecutive_down(df, int(params.get("n", 3)))

    if condition_type == STREAK_UP:
        return detect_consecutive_up(df, int(params.get("n", 3)))

    if condition_type == GAP_DOWN:
        return detect_gap_down(df, float(params.get("threshold_pct", 0.5)))

    if condition_type == GAP_UP:
        return detect_gap_up(df, float(params.get("threshold_pct", 0.5)))

    if condition_type == CANDLE:
        pattern = params.get("pattern", "")
        internal = _CANDLE_ALIAS.get(pattern, pattern)

        if internal == "_inside_day":
            return _detect_inside_day(df)
        if internal == "_outside_day":
            return _detect_outside_day(df)

        signals = detect_patterns(df)
        if internal not in signals:
            raise ValueError(
                f"Unknown candle pattern {pattern!r}. "
                f"Available: {sorted(_CANDLE_ALIAS) + sorted(signals)}"
            )
        return signals[internal].fillna(False)

    raise ValueError(
        f"Unknown condition_type {condition_type!r}. "
        f"Valid: down_streak, up_streak, gap_down, gap_up, candle"
    )


# ── DB persistence ────────────────────────────────────────────────────────────

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


# ── Public API ────────────────────────────────────────────────────────────────

def run_backtest(
    ticker: str,
    condition_type: str,
    params: dict,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    spec_id: Optional[int] = None,
    save: bool = True,
) -> dict:
    """
    Run a historical probability study and return results.

    Returns
    -------
    dict with keys:
        ticker, condition_type, params,
        n_events, data_start, data_end,
        events  — list of per-signal dicts
        stats   — {horizon: aggregate_stats_dict}
        run_id  — DB run ID if saved, else None
    """
    df = load_bars(ticker, start_date, end_date)
    if df.empty:
        raise ValueError(f"No bars found for {ticker!r}")

    mask   = detect_condition(df, condition_type, params)
    events = compute_all_outcomes(df, mask, ticker=ticker)
    stats  = stats_by_horizon(events)

    run_id: Optional[int] = None
    if save and spec_id is not None:
        run_id = _save_run(spec_id, df, events, stats)

    return {
        "ticker":         ticker,
        "condition_type": condition_type,
        "params":         params,
        "n_events":       len(events),
        "data_start":     str(df.index[0].date()) if not df.empty else None,
        "data_end":       str(df.index[-1].date()) if not df.empty else None,
        "events":         events,
        "stats":          stats,
        "run_id":         run_id,
    }
