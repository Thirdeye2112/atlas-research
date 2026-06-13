"""
atlas_research.probability.sanity
-----------------------------------
Leakage and sanity checks for backtest results.

Shuffle test (permutation test)
--------------------------------
Null hypothesis: any N random dates in the same series produce the same
hit rate as the detected signal dates.

Method:
  1. Detect real signal positions (N total).
  2. For each of K shuffles, randomly select N positions from the valid
     range (skipping the first 200 bars for SMA burn-in and last
     `horizon` bars for forward-return availability).
  3. Compute hit rate for each shuffle.
  4. PASS if real_hit > p95 of shuffled distribution (p < 0.05).

Usage
-----
    from atlas_research.probability.sanity import run_shuffle_test, print_sanity_result

    result = run_shuffle_test("SPY", "down_streak", {"n": 4})
    print_sanity_result(result)
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from .engine import load_bars, detect_condition
from .outcomes import compute_all_outcomes

SHUFFLE_SEED      = 42     # deterministic across runs
BURN_IN_BARS      = 200    # skip first N bars (SMA warm-up)
DEFAULT_SHUFFLES  = 200    # number of permutations
DEFAULT_HORIZON   = 5      # forward-return horizon to test


def run_shuffle_test(
    ticker: str,
    condition_type: str,
    params: dict,
    n_shuffles: int = DEFAULT_SHUFFLES,
    horizon: int = DEFAULT_HORIZON,
) -> dict:
    """
    Permutation test: do signal dates have higher returns than random dates?

    Returns dict with keys:
        ticker, condition_type, params,
        n_events, real_hit_rate, real_avg_return,
        shuffle_mean_hit, shuffle_p95_hit, shuffle_std_hit,
        n_shuffles, horizon, passed, error (str or None)
    """
    df = load_bars(ticker)
    if df.empty:
        return {"error": f"no bars for {ticker!r}", "passed": False}

    mask   = detect_condition(df, condition_type, params)
    events = compute_all_outcomes(df, mask, ticker=ticker)

    ret_key  = f"ret_{horizon}d"
    real_rets = np.array(
        [e[ret_key] for e in events if e.get(ret_key) is not None],
        dtype=float,
    )
    n_signals = len(real_rets)

    if n_signals < 10:
        return {
            "ticker": ticker, "condition_type": condition_type, "params": params,
            "n_events": n_signals, "horizon": horizon, "n_shuffles": 0,
            "error": f"too few events (n={n_signals}, need ≥10)",
            "passed": False,
        }

    real_hit = float(np.mean(real_rets > 0))
    real_avg = float(np.mean(real_rets))

    # ── Build valid position pool ─────────────────────────────────────────────
    # Positions must have enough lookback AND enough forward bars.
    total = len(df)
    valid = np.arange(BURN_IN_BARS, total - horizon - 1)

    if len(valid) < n_signals:
        return {
            "ticker": ticker, "condition_type": condition_type, "params": params,
            "n_events": n_signals, "horizon": horizon, "n_shuffles": 0,
            "error": "insufficient valid positions for shuffle",
            "passed": False,
        }

    # ── Shuffles ──────────────────────────────────────────────────────────────
    closes = df["close"].to_numpy(dtype=float)
    rng    = np.random.RandomState(SHUFFLE_SEED)
    shuffled_hits: list[float] = []

    for _ in range(n_shuffles):
        idx   = rng.choice(valid, size=n_signals, replace=False)
        rets  = (closes[idx + horizon] / closes[idx] - 1) * 100
        shuffled_hits.append(float(np.mean(rets > 0)))

    arr          = np.array(shuffled_hits, dtype=float)
    shuffle_mean = float(np.mean(arr))
    shuffle_p95  = float(np.percentile(arr, 95))
    shuffle_std  = float(np.std(arr))

    passed = real_hit > shuffle_p95

    return {
        "ticker":           ticker,
        "condition_type":   condition_type,
        "params":           params,
        "n_events":         n_signals,
        "horizon":          horizon,
        "real_hit_rate":    real_hit,
        "real_avg_return":  real_avg,
        "shuffle_mean_hit": shuffle_mean,
        "shuffle_p95_hit":  shuffle_p95,
        "shuffle_std_hit":  shuffle_std,
        "n_shuffles":       n_shuffles,
        "passed":           passed,
        "error":            None,
    }


# ── Console output ────────────────────────────────────────────────────────────

def print_sanity_result(result: dict) -> None:
    """Print a formatted sanity-check verdict."""
    ticker = result.get("ticker", "?")
    ctype  = result.get("condition_type", "?")
    params = result.get("params", {})
    h      = result.get("horizon", 5)

    param_str = " ".join(f"{k}={v}" for k, v in params.items())
    label     = f"{ticker} {ctype} [{param_str}]"

    print()
    print("=" * 66)
    print(f"  SANITY CHECK — {label}")
    print("=" * 66)

    if result.get("error"):
        print(f"  ERROR: {result['error']}")
        print()
        return

    n        = result["n_events"]
    real_hit = result["real_hit_rate"] * 100
    real_avg = result["real_avg_return"]
    sh_mean  = result["shuffle_mean_hit"] * 100
    sh_p95   = result["shuffle_p95_hit"]  * 100
    sh_std   = result["shuffle_std_hit"]  * 100
    k        = result["n_shuffles"]

    print(f"  Signal dates:         n={n}")
    print(f"  Horizon:              {h}d forward return")
    print(f"  Shuffles:             {k}")
    print()
    print(f"  Real hit rate:        {real_hit:.1f}%   (avg return {real_avg:+.2f}%)")
    print(f"  Shuffle mean:         {sh_mean:.1f}%   ± {sh_std:.1f}%")
    print(f"  Shuffle p95:          {sh_p95:.1f}%")
    print()

    if result["passed"]:
        lift = real_hit - sh_mean
        print(f"  PASS  — real hit ({real_hit:.1f}%) exceeds shuffled p95 ({sh_p95:.1f}%)")
        print(f"          Edge lift vs baseline: +{lift:.1f}pp")
        print(f"          Edge is NOT spurious (p < 0.05 by permutation).")
    else:
        print(f"  FAIL  — real hit ({real_hit:.1f}%) is within shuffled range (≤{sh_p95:.1f}%)")
        print(f"          WARNING: edge may be spurious — investigate further.")

    print()
