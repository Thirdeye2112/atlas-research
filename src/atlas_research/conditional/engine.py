"""
Conditional probability backtesting engine.

Public interface preserved — delegates computation to atlas_research.backtest.
Existing callers (run_conditional.py, API routes) require no changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from atlas_research.db.connection import get_raw_engine
from atlas_research.backtest.adapters import (
    run_conditional_pattern,
    run_conditional_for_ticker,
)
from atlas_research.backtest.conditions import REGISTRY as CONDITION_REGISTRY


# ── Pattern data class (unchanged public shape) ───────────────────────────────

@dataclass
class Pattern:
    id:               int
    name:             str
    condition_type:   str
    universe:         str
    condition_params: dict
    horizons:         list[int]
    min_sample_size:  int


# ── ConditionalEngine ─────────────────────────────────────────────────────────

class ConditionalEngine:
    def __init__(self) -> None:
        self._engine = get_raw_engine()

    # ── Pattern / ticker loading ──────────────────────────────────────────────

    def _load_patterns(self, name: str | None = None) -> list[Pattern]:
        q = """
            SELECT id, name, condition_type, universe,
                   condition_params, horizons, min_sample_size
            FROM conditional_patterns
        """
        params: dict = {}
        if name:
            q += " WHERE name = :name"
            params["name"] = name
        q += " ORDER BY id"
        with self._engine.connect() as conn:
            rows = conn.execute(text(q), params).fetchall()
        return [
            Pattern(
                id=r[0], name=r[1], condition_type=r[2], universe=r[3],
                condition_params=r[4] or {}, horizons=list(r[5] or [1, 5, 10, 20]),
                min_sample_size=r[6] or 30,
            )
            for r in rows
        ]

    def _load_tickers(self, universe: str) -> list[str]:
        upper = universe.upper() if universe else ""
        if upper and len(upper) <= 5 and upper not in ("SP500", "ALL", "US"):
            with self._engine.connect() as conn:
                row = conn.execute(
                    text("SELECT COUNT(*) FROM raw_bars WHERE ticker = :t"),
                    {"t": upper},
                ).fetchone()
            if row and row[0] > 0:
                return [upper]
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("SELECT DISTINCT ticker FROM raw_bars ORDER BY ticker")
            ).fetchall()
        return [r[0] for r in rows]

    # ── DB persistence (unchanged) ────────────────────────────────────────────

    def _upsert_result(
        self, pattern_id: int, ticker: str | None, horizon: int, stats: dict
    ) -> None:
        if not stats:
            return
        with self._engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO conditional_pattern_results
                    (pattern_id, ticker, horizon_days, sample_size, hit_rate,
                     avg_return, median_return, std_return, sharpe, p_value, evaluated_at)
                VALUES
                    (:pid, :ticker, :horizon, :n, :hr, :avg, :med, :std, :sh, :pv, now())
                ON CONFLICT (pattern_id, COALESCE(ticker,''), horizon_days)
                DO UPDATE SET
                    sample_size   = EXCLUDED.sample_size,
                    hit_rate      = EXCLUDED.hit_rate,
                    avg_return    = EXCLUDED.avg_return,
                    median_return = EXCLUDED.median_return,
                    std_return    = EXCLUDED.std_return,
                    sharpe        = EXCLUDED.sharpe,
                    p_value       = EXCLUDED.p_value,
                    evaluated_at  = now()
            """), {
                "pid":    pattern_id,
                "ticker": ticker,
                "horizon": horizon,
                "n":      stats.get("sample_size"),
                "hr":     stats.get("hit_rate"),
                "avg":    stats.get("avg_return"),
                "med":    stats.get("median_return"),
                "std":    stats.get("std_return"),
                "sh":     stats.get("sharpe"),
                "pv":     stats.get("p_value"),
            })

    # ── Execution (delegates to canonical engine) ─────────────────────────────

    def run_pattern(self, pattern_name: str) -> int:
        patterns = self._load_patterns(pattern_name)
        if not patterns:
            raise ValueError(f"Pattern not found: {pattern_name}")
        pattern = patterns[0]
        tickers = self._load_tickers(pattern.universe)

        # Per-ticker results
        for ticker in tickers:
            per_ticker = run_conditional_for_ticker(
                ticker=ticker,
                condition_type=pattern.condition_type,
                params=pattern.condition_params,
                horizons=pattern.horizons,
                min_sample_size=pattern.min_sample_size,
            )
            for horizon, stats in per_ticker.items():
                self._upsert_result(pattern.id, ticker, horizon, stats)

        # Aggregate result (ticker=None)
        agg = run_conditional_pattern(
            condition_type=pattern.condition_type,
            params=pattern.condition_params,
            tickers=tickers,
            horizons=pattern.horizons,
            min_sample_size=pattern.min_sample_size,
            name=pattern.name,
        )
        total_signals = 0
        for horizon, stats in agg.items():
            self._upsert_result(pattern.id, None, horizon, stats)
            total_signals += stats.get("sample_size", 0)

        return total_signals // max(len(pattern.horizons), 1)

    def run_all(self) -> dict:
        patterns = self._load_patterns()
        run = failed = total_signals = 0
        for pattern in patterns:
            try:
                n = self.run_pattern(pattern.name)
                total_signals += n
                run += 1
            except Exception as exc:
                print(f"  [engine] pattern '{pattern.name}' failed: {exc}")
                failed += 1
        return {"run": run, "failed": failed, "total_signals": total_signals}
