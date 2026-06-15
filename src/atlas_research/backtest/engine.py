"""
atlas_research.backtest.engine
================================
Canonical backtest engine — orchestrates condition evaluation, outcome
computation, and metric aggregation for a single (ticker, condition) pair
or a multi-ticker aggregate.

Usage
-----
    from atlas_research.backtest import BacktestEngine, ConditionSpec

    engine = BacktestEngine()
    result = engine.run(
        ticker="SPY",
        condition_type="consecutive_down",
        params={"n_days": 4},
    )
    print(result.stats[5]["hit_rate"])   # 5-day hit rate
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
from sqlalchemy import text

from .conditions import evaluate
from .outcomes import compute_all, HORIZONS, RUNUP_WINDOWS
from .metrics import aggregate, aggregate_all_horizons, yearly_breakdown, permutation_p


# ── Spec / result data classes ────────────────────────────────────────────────

@dataclass
class ConditionSpec:
    condition_type: str
    params:         dict = field(default_factory=dict)
    universe:       str  = "SPY"           # "SPY", "ALL", or a ticker
    horizons:       list[int] = field(default_factory=lambda: list(HORIZONS))
    min_sample_size: int = 30
    name:           Optional[str] = None   # human-readable label

    def to_dict(self) -> dict:
        return {
            "condition_type":  self.condition_type,
            "params":          self.params,
            "universe":        self.universe,
            "horizons":        self.horizons,
            "min_sample_size": self.min_sample_size,
            "name":            self.name,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConditionSpec":
        return cls(**d)


@dataclass
class OutcomeSpec:
    horizons:      list[int] = field(default_factory=lambda: list(HORIZONS))
    runup_windows: list[int] = field(default_factory=lambda: list(RUNUP_WINDOWS))
    permutation:   bool      = False
    n_shuffles:    int       = 500


@dataclass
class BacktestResult:
    condition_type: str
    params:         dict
    tickers:        list[str]
    horizons:       list[int]
    events:         list[dict]        # raw per-signal events
    stats:          dict[int, dict]   # horizon -> aggregate stats dict
    yearly:         dict[int, list]   # horizon -> yearly breakdown
    n_events:       int
    data_start:     Optional[str]
    data_end:       Optional[str]
    name:           Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "condition_type": self.condition_type,
            "params":         self.params,
            "tickers":        self.tickers,
            "horizons":       self.horizons,
            "events":         self.events,
            "stats":          self.stats,
            "yearly":         self.yearly,
            "n_events":       self.n_events,
            "data_start":     self.data_start,
            "data_end":       self.data_end,
            "name":           self.name,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BacktestResult":
        return cls(**d)


# ── Engine ────────────────────────────────────────────────────────────────────

class BacktestEngine:
    """Stateless engine — creates its own DB connection on construction."""

    def __init__(self) -> None:
        from atlas_research.db.connection import get_raw_engine
        self._engine = get_raw_engine()

    # ── Bar loading ───────────────────────────────────────────────────────────

    def load_bars(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date:   Optional[str] = None,
    ) -> pd.DataFrame:
        sql    = "SELECT date, open, high, low, close, volume FROM raw_bars WHERE ticker = :t"
        params: dict = {"t": ticker}
        if start_date:
            sql += " AND date >= :start"; params["start"] = start_date
        if end_date:
            sql += " AND date <= :end";   params["end"]   = end_date
        sql += " ORDER BY date ASC"

        with self._engine.connect() as conn:
            rows = conn.execute(text(sql), params).fetchall()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
        for col in ("open", "high", "low", "close"):
            df[col] = df[col].astype(float)
        df["volume"] = df["volume"].astype(float)
        return df

    def load_universe_tickers(self, universe: str) -> list[str]:
        """Resolve universe string to a list of tickers."""
        upper = universe.upper()
        # Single-ticker universe
        if len(upper) <= 5 and upper not in ("SP500", "ALL", "US"):
            with self._engine.connect() as conn:
                row = conn.execute(
                    text("SELECT COUNT(*) FROM raw_bars WHERE ticker = :t"),
                    {"t": upper},
                ).fetchone()
            if row and row[0] > 0:
                return [upper]
        # Full universe
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("SELECT DISTINCT ticker FROM raw_bars ORDER BY ticker")
            ).fetchall()
        return [r[0] for r in rows]

    # ── Single-ticker run ─────────────────────────────────────────────────────

    def run(
        self,
        ticker: str,
        condition_type: str,
        params: dict,
        horizons: list[int] = HORIZONS,
        runup_windows: list[int] = RUNUP_WINDOWS,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_sample_size: int = 1,
        name: Optional[str] = None,
    ) -> BacktestResult:
        df = self.load_bars(ticker, start_date, end_date)
        if df.empty:
            return BacktestResult(
                condition_type=condition_type, params=params,
                tickers=[ticker], horizons=horizons,
                events=[], stats={}, yearly={}, n_events=0,
                data_start=None, data_end=None, name=name,
            )

        mask   = evaluate(df, condition_type, params)
        events = compute_all(df, mask, ticker=ticker,
                             horizons=horizons, runup_windows=runup_windows)
        # Trim events that lack enough forward bars
        max_h  = max(horizons)
        events = [e for e in events if e.get(f"ret_{max_h}d") is not None]

        stats  = aggregate_all_horizons(events, horizons)
        yearly = {h: yearly_breakdown(events, h) for h in horizons}

        return BacktestResult(
            condition_type=condition_type,
            params=params,
            tickers=[ticker],
            horizons=horizons,
            events=events,
            stats=stats,
            yearly=yearly,
            n_events=len(events),
            data_start=str(df.index[0].date()) if not df.empty else None,
            data_end=str(df.index[-1].date())  if not df.empty else None,
            name=name,
        )

    # ── Multi-ticker aggregate run ────────────────────────────────────────────

    def run_aggregate(
        self,
        tickers: list[str],
        condition_type: str,
        params: dict,
        horizons: list[int] = HORIZONS,
        runup_windows: list[int] = RUNUP_WINDOWS,
        min_sample_size: int = 30,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        name: Optional[str] = None,
    ) -> BacktestResult:
        all_events:  list[dict] = []
        data_starts: list[str]  = []
        data_ends:   list[str]  = []
        max_h = max(horizons)

        for ticker in tickers:
            df = self.load_bars(ticker, start_date, end_date)
            if df.empty or len(df) < 30:
                continue
            try:
                mask   = evaluate(df, condition_type, params)
                events = compute_all(df, mask, ticker=ticker,
                                     horizons=horizons, runup_windows=runup_windows)
                events = [e for e in events if e.get(f"ret_{max_h}d") is not None]
                all_events.extend(events)
                data_starts.append(str(df.index[0].date()))
                data_ends.append(str(df.index[-1].date()))
            except Exception:
                continue

        stats  = aggregate_all_horizons(all_events, horizons)
        yearly = {h: yearly_breakdown(all_events, h) for h in horizons}

        return BacktestResult(
            condition_type=condition_type,
            params=params,
            tickers=tickers,
            horizons=horizons,
            events=all_events,
            stats=stats,
            yearly=yearly,
            n_events=len(all_events),
            data_start=min(data_starts) if data_starts else None,
            data_end=max(data_ends)     if data_ends   else None,
            name=name,
        )

    # ── Spec-driven convenience ───────────────────────────────────────────────

    def run_spec(
        self,
        spec: ConditionSpec,
        outcome: OutcomeSpec = OutcomeSpec(),
    ) -> BacktestResult:
        tickers = self.load_universe_tickers(spec.universe)
        if len(tickers) == 1:
            result = self.run(
                ticker=tickers[0],
                condition_type=spec.condition_type,
                params=spec.params,
                horizons=spec.horizons,
                runup_windows=outcome.runup_windows,
                min_sample_size=spec.min_sample_size,
                name=spec.name,
            )
        else:
            result = self.run_aggregate(
                tickers=tickers,
                condition_type=spec.condition_type,
                params=spec.params,
                horizons=spec.horizons,
                runup_windows=outcome.runup_windows,
                min_sample_size=spec.min_sample_size,
                name=spec.name,
            )
        return result
