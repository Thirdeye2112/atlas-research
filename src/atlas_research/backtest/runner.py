"""
atlas_research.backtest.runner
================================
Parallel suite execution using ProcessPoolExecutor.

Rules
-----
- Independent specs run in parallel (compute phase).
- DB writes are always sequential (single writer after all workers finish).
- Each worker opens its own DB connection (connections are not picklable).
- Market data is loaded once per ticker per worker process.

Usage
-----
    from atlas_research.backtest.runner import run_suite
    from atlas_research.backtest import ConditionSpec

    specs = [
        ConditionSpec("consecutive_down", {"n_days": 4}, universe="SPY"),
        ConditionSpec("gap_down", {"min_gap_pct": 2.0}, universe="SPY"),
    ]
    results = run_suite(specs, n_workers=4)
"""

from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Callable, Optional

from .engine import BacktestEngine, ConditionSpec, OutcomeSpec, BacktestResult


# ── Worker (module-level so it's picklable on Windows spawn) ─────────────────

def _worker(args: dict) -> dict:
    """
    Runs in a subprocess.  Receives a serialisable spec dict, returns a
    serialisable result dict.  Opens its own DB connection.
    """
    import sys
    from pathlib import Path
    # Ensure src/ is on the path in spawned process
    src = Path(__file__).resolve().parent.parent.parent
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    root = src.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from dotenv import load_dotenv
    load_dotenv(root / ".env")

    spec    = ConditionSpec.from_dict(args["spec"])
    outcome = OutcomeSpec(**args.get("outcome", {}))
    engine  = BacktestEngine()
    result  = engine.run_spec(spec, outcome)
    return result.to_dict()


# ── Public API ────────────────────────────────────────────────────────────────

def run_suite(
    specs: list[ConditionSpec],
    outcome: OutcomeSpec = OutcomeSpec(),
    n_workers: int = 4,
    on_result: Optional[Callable[[BacktestResult], None]] = None,
    verbose: bool = True,
) -> list[BacktestResult]:
    """
    Run a list of ConditionSpecs in parallel and return results.

    Parameters
    ----------
    specs      : list of ConditionSpec to evaluate
    outcome    : shared OutcomeSpec (horizons, runup windows, permutation flag)
    n_workers  : number of worker processes (default 4)
    on_result  : optional callback invoked sequentially for each completed result
                 (use for DB writes — called in the main process)
    verbose    : print progress

    Returns
    -------
    list of BacktestResult in the same order as specs
    """
    if not specs:
        return []

    t0 = time.monotonic()
    outcome_dict = {
        "horizons":      outcome.horizons,
        "runup_windows": outcome.runup_windows,
        "permutation":   outcome.permutation,
        "n_shuffles":    outcome.n_shuffles,
    }

    # Build args list
    args_list = [
        {"spec": s.to_dict(), "outcome": outcome_dict}
        for s in specs
    ]

    results_by_idx: dict[int, BacktestResult] = {}
    n_done = 0

    if n_workers <= 1:
        # Serial fallback (useful for debugging)
        for i, args in enumerate(args_list):
            raw = _worker(args)
            r = BacktestResult.from_dict(raw)
            results_by_idx[i] = r
            n_done += 1
            if verbose:
                _print_progress(n_done, len(specs), r)
            if on_result:
                on_result(r)
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            future_to_idx = {
                pool.submit(_worker, args): i
                for i, args in enumerate(args_list)
            }
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    raw = future.result()
                    r   = BacktestResult.from_dict(raw)
                except Exception as exc:
                    spec = specs[idx]
                    label = spec.name or spec.condition_type
                    print(f"  [runner] FAILED {label}: {exc}")
                    r = BacktestResult(
                        condition_type=spec.condition_type,
                        params=spec.params, tickers=[], horizons=spec.horizons,
                        events=[], stats={}, yearly={}, n_events=0,
                        data_start=None, data_end=None, name=spec.name,
                    )
                results_by_idx[idx] = r
                n_done += 1
                if verbose:
                    _print_progress(n_done, len(specs), r)
                if on_result:
                    on_result(r)  # always sequential

    elapsed = time.monotonic() - t0
    if verbose:
        print(f"\n  Suite complete: {len(specs)} specs in {elapsed:.1f}s")

    return [results_by_idx[i] for i in range(len(specs))]


def _print_progress(done: int, total: int, r: BacktestResult) -> None:
    label = r.name or r.condition_type
    hr5   = r.stats.get(5, {}).get("hit_rate")
    n     = r.n_events
    hr_str = f"{hr5 * 100:.1f}%" if hr5 is not None else "n/a"
    print(f"  [{done:>3}/{total}] {label:<40}  n={n:<6} 5d_hr={hr_str}")
