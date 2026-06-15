"""
atlas_research.backtest
========================
Canonical backtesting engine.  All condition detection, forward-return
computation, and aggregate statistics flow through this package.

Existing engines (conditional, probability, patterns) are thin adapters
that delegate here while preserving their public interfaces unchanged.

Public API
----------
    from atlas_research.backtest import BacktestEngine, ConditionSpec, BacktestResult
    engine = BacktestEngine()
    result = engine.run(ticker="SPY", condition_type="consecutive_down", params={"n_days": 4})
"""

from .engine import BacktestEngine, ConditionSpec, OutcomeSpec, BacktestResult
from .conditions import evaluate, REGISTRY as CONDITION_REGISTRY
from .outcomes import compute_all, forward_returns
from .metrics import aggregate, permutation_p, binomial_p, yearly_breakdown

__all__ = [
    "BacktestEngine",
    "ConditionSpec",
    "OutcomeSpec",
    "BacktestResult",
    "evaluate",
    "CONDITION_REGISTRY",
    "compute_all",
    "forward_returns",
    "aggregate",
    "permutation_p",
    "binomial_p",
    "yearly_breakdown",
]
