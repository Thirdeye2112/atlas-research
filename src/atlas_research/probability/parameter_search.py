"""
atlas_research.probability.parameter_search
---------------------------------------------
Grid-search over parameter spaces for probability engine conditions.

Usage
-----
    from atlas_research.probability.parameter_search import (
        run_parameter_search,
        print_search_table,
        PARAM_GRIDS,
    )

    results = run_parameter_search("SPY", "down_streak",
                                   PARAM_GRIDS["down_streak"])
    print_search_table("SPY", "down_streak", results)
"""

from __future__ import annotations

import math
from typing import Optional

from .engine import load_bars, detect_condition, _save_run
from .outcomes import compute_all_outcomes, stats_by_horizon
from .robustness import check_robustness, RobustnessReport
from .registry import get_or_create_spec

# ── Default parameter grids ───────────────────────────────────────────────────

PARAM_GRIDS: dict[str, list[dict]] = {
    "down_streak": [{"n": n} for n in range(2, 7)],
    "up_streak":   [{"n": n} for n in range(2, 7)],
    "gap_down":    [{"threshold_pct": t} for t in [0.5, 1.0, 2.0, 3.0]],
    "gap_up":      [{"threshold_pct": t} for t in [0.5, 1.0, 2.0, 3.0]],
}


# ── Scoring ───────────────────────────────────────────────────────────────────

def _edge_score(stats_5d: dict, n_events: int) -> float:
    """
    Composite score: higher is better.
    Rewards hit rate, average return magnitude, and penalizes small N.
    Formula: avg_ret * hit_pct * log2(n+1) where hit_pct is (hit_rate * 100).
    """
    avg  = stats_5d.get("avg_return") or 0.0
    hr   = stats_5d.get("hit_rate")   or 0.0
    if avg <= 0 or n_events < 5:
        return 0.0
    return round(avg * hr * 100 * math.log2(n_events + 1), 3)


def _param_label(condition_type: str, params: dict) -> str:
    if condition_type in ("down_streak", "up_streak"):
        return f"N={params['n']}"
    if condition_type in ("gap_down", "gap_up"):
        return f"{params['threshold_pct']}%"
    return str(params)


# ── Core search ───────────────────────────────────────────────────────────────

def run_parameter_search(
    ticker: str,
    condition_type: str,
    param_grid: list[dict],
    save: bool = True,
) -> list[dict]:
    """
    Run a condition backtest for each parameter set in param_grid.

    Loads bars ONCE, runs condition detection + outcome computation for
    every param set in-memory.  Optionally persists specs + run records
    to the probability engine DB tables.

    Returns list of result dicts sorted by 5d edge score (descending).
    Each dict has:
        label, params, n_events, stats, robustness, score, spec_id, run_id
    """
    df = load_bars(ticker)
    if df.empty:
        raise ValueError(f"No bars found for {ticker!r}")

    results: list[dict] = []

    for params in param_grid:
        label = _param_label(condition_type, params)
        try:
            mask   = detect_condition(df, condition_type, params)
            events = compute_all_outcomes(df, mask, ticker=ticker)
            stats  = stats_by_horizon(events)
            robust = check_robustness(events, horizon=5)
            score  = _edge_score(stats.get(5, {}), len(events))

            spec_id: Optional[int] = None
            run_id:  Optional[int] = None

            if save and len(events) > 0:
                spec_id = get_or_create_spec(ticker, condition_type, params)
                run_id  = _save_run(spec_id, df, events, stats)

            results.append({
                "label":      label,
                "params":     params,
                "n_events":   len(events),
                "stats":      stats,
                "robustness": robust,
                "score":      score,
                "spec_id":    spec_id,
                "run_id":     run_id,
                "error":      None,
            })

        except Exception as exc:
            results.append({
                "label":      label,
                "params":     params,
                "n_events":   0,
                "stats":      {},
                "robustness": None,
                "score":      0.0,
                "spec_id":    None,
                "run_id":     None,
                "error":      str(exc),
            })

    return sorted(results, key=lambda r: r["score"], reverse=True)


# ── Console output ────────────────────────────────────────────────────────────

def _pct(v: Optional[float], sign: bool = True) -> str:
    if v is None:
        return "  N/A"
    s = "+" if sign and v > 0 else ""
    return f"{s}{v:.1f}%"


def _hr(v: Optional[float]) -> str:
    if v is None:
        return " N/A"
    return f"{v*100:.1f}%"


def print_search_table(
    ticker: str,
    condition_type: str,
    results: list[dict],
    *,
    param_header: Optional[str] = None,
) -> None:
    """Print a formatted parameter-search results table."""
    bar = "=" * 72

    grid_labels = ", ".join(r["label"] for r in results)
    print()
    print(bar)
    ctype_pretty = condition_type.replace("_", " ").upper()
    print(f"  {ticker} — {ctype_pretty} PARAMETER SEARCH")
    print(f"  Grid: {grid_labels}")
    print(bar)

    ph = param_header or ("N" if "streak" in condition_type else "Thr")
    print(
        f"  {ph:<5}  {'Events':>6}  "
        f"{'Hit5d':>6}  {'Avg5d':>6}  "
        f"{'Hit20d':>6}  {'Avg20d':>7}  "
        f"{'Robust':>7}  {'Score':>7}"
    )
    print("  " + "-" * 66)

    # Sort for display by param value (not score) for readability
    display = sorted(results, key=lambda r: list(r["params"].values())[0])

    best_score = max((r["score"] for r in results if r["error"] is None), default=0)

    for r in display:
        if r["error"]:
            print(f"  {r['label']:<5}  ERROR: {r['error'][:50]}")
            continue

        s5  = r["stats"].get(5,  {})
        s20 = r["stats"].get(20, {})
        rob: Optional[RobustnessReport] = r["robustness"]

        if rob is None:
            rob_str = "  N/A"
        elif not rob.passed:
            first_reason = rob.reasons_failed[0] if rob.reasons_failed else "failed"
            short = first_reason[:18]
            rob_str = f"NO ({short})"
        else:
            rob_str = "YES"

        marker = " *" if r["score"] >= best_score and r["score"] > 0 else ""

        print(
            f"  {r['label']:<5}  {r['n_events']:>6}  "
            f"{_hr(s5.get('hit_rate')):>6}  "
            f"{_pct(s5.get('avg_return')):>6}  "
            f"{_hr(s20.get('hit_rate')):>6}  "
            f"{_pct(s20.get('avg_return')):>7}  "
            f"{rob_str:<13}  "
            f"{r['score']:>7.1f}{marker}"
        )

    print()
