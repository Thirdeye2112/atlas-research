"""
atlas_research.backtest.metrics
=================================
Canonical aggregate statistics, significance testing, and year-by-year breakdowns.

All inputs use percentage returns (as produced by outcomes.py).

Public API
----------
    aggregate(events, horizon)                 -> dict
    yearly_breakdown(events, horizon)          -> list[dict]
    binomial_p(n, k, p0)                       -> float
    permutation_p(df, mask, horizon, n_shuffles, seed) -> float
    tstat_p(returns)                           -> float
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


# ── Single-horizon aggregate ──────────────────────────────────────────────────

def aggregate(events: list[dict], horizon: int) -> dict:
    """
    Aggregate cross-event statistics for one forward horizon.

    Returns dict with keys:
        n, hit_rate, avg_return, median_return, std_return,
        p25_return, p75_return, sharpe,
        avg_max_runup, avg_max_dd,
        p_value (t-stat approximation)
    """
    key  = f"ret_{horizon}d"
    rets = [e[key] for e in events if e.get(key) is not None]

    if not rets:
        return {
            "n": 0, "hit_rate": None, "avg_return": None,
            "median_return": None, "std_return": None,
            "p25_return": None, "p75_return": None, "sharpe": None,
            "avg_max_runup": None, "avg_max_dd": None, "p_value": None,
        }

    arr = np.array(rets, dtype=float)
    n   = len(arr)
    mu  = float(np.mean(arr))
    std = float(np.std(arr, ddof=1)) if n > 1 else 0.0

    # Sharpe: annualised (trading days)
    sharpe = (mu / std * math.sqrt(252 / horizon)) if std > 0 else None

    # t-stat p-value (two-tailed)
    p_value = tstat_p(arr) if n >= 2 and std > 0 else None

    # Pick closest runup/dd window ≤ horizon
    from .outcomes import RUNUP_WINDOWS
    w = max((x for x in RUNUP_WINDOWS if x <= horizon), default=RUNUP_WINDOWS[0])
    runups = [e.get(f"max_runup_{w}d") for e in events if e.get(f"max_runup_{w}d") is not None]
    dds    = [e.get(f"max_dd_{w}d")    for e in events if e.get(f"max_dd_{w}d")    is not None]

    return {
        "n":             n,
        "hit_rate":      round(float(np.mean(arr > 0)), 4),
        "avg_return":    round(mu, 4),
        "median_return": round(float(np.median(arr)), 4),
        "std_return":    round(std, 4),
        "p25_return":    round(float(np.percentile(arr, 25)), 4),
        "p75_return":    round(float(np.percentile(arr, 75)), 4),
        "sharpe":        round(sharpe, 4) if sharpe is not None else None,
        "avg_max_runup": round(float(np.mean(runups)), 4) if runups else None,
        "avg_max_dd":    round(float(np.mean(dds)), 4)    if dds    else None,
        "p_value":       round(p_value, 4)               if p_value is not None else None,
    }


def aggregate_all_horizons(events: list[dict], horizons: list[int]) -> dict[int, dict]:
    """Return {horizon: aggregate_stats} for every horizon in list."""
    return {h: aggregate(events, h) for h in horizons}


# ── Year-by-year breakdown ───────────────────────────────────────────────────

def yearly_breakdown(events: list[dict], horizon: int) -> list[dict]:
    """
    Split events by signal year and compute per-year hit rate + avg return.
    Returns list of {year, n, hit_rate, avg_return} sorted ascending.
    """
    key = f"ret_{horizon}d"
    by_year: dict[int, list[float]] = {}
    for e in events:
        ret = e.get(key)
        if ret is None:
            continue
        sd = e.get("signal_date")
        if sd is None:
            continue
        year = int(str(sd)[:4])
        by_year.setdefault(year, []).append(ret)

    rows = []
    for year in sorted(by_year):
        arr = np.array(by_year[year], dtype=float)
        rows.append({
            "year":       year,
            "n":          len(arr),
            "hit_rate":   round(float(np.mean(arr > 0)), 4),
            "avg_return": round(float(np.mean(arr)), 4),
        })
    return rows


# ── Significance tests ────────────────────────────────────────────────────────

def tstat_p(returns) -> float:
    """
    Two-tailed p-value from t-statistic (large-sample normal approximation).
    Uses Abramowitz & Stegun CDF approximation.
    """
    arr = np.asarray(returns, dtype=float)
    n   = len(arr)
    if n < 2:
        return 1.0
    mu  = float(np.mean(arr))
    std = float(np.std(arr, ddof=1))
    if std == 0:
        return 1.0 if mu == 0 else 0.0
    t = mu / (std / math.sqrt(n))
    z = abs(t)
    b = 1.0 / (1.0 + 0.2316419 * z)
    poly = b * (0.319381530 + b * (-0.356563782 + b * (1.781477937 + b * (-1.821255978 + b * 1.330274429))))
    pdf = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
    return min(1.0, 2.0 * pdf * poly)


def binomial_p(n: int, k: int, p0: float = 0.5) -> float:
    """
    One-tailed p-value: P(X >= k) under Binomial(n, p0).
    Normal approximation with continuity correction.
    """
    if n == 0:
        return 1.0
    mu    = n * p0
    sigma = math.sqrt(n * p0 * (1.0 - p0))
    if sigma == 0:
        return 1.0
    z = (k - 0.5 - mu) / sigma
    if z < 0:
        return 1.0
    b = 1.0 / (1.0 + 0.2316419 * z)
    poly = b * (0.319381530 + b * (-0.356563782 + b * (1.781477937 + b * (-1.821255978 + b * 1.330274429))))
    pdf = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)
    return min(1.0, pdf * poly)


def permutation_p(
    df: pd.DataFrame,
    mask: pd.Series,
    horizon: int,
    n_shuffles: int = 500,
    seed: int = 42,
    burn_in: int = 200,
) -> dict:
    """
    Permutation (shuffle) test: do signal dates beat random same-size samples?

    Returns dict with:
        n_signals, real_hit_rate, real_avg_return,
        shuffle_mean_hit, shuffle_p95_hit, shuffle_std_hit,
        n_shuffles, horizon, passed, p_value
    """
    closes  = df["close"].to_numpy(dtype=float)
    highs   = df["high"].to_numpy(dtype=float)
    lows    = df["low"].to_numpy(dtype=float)
    n_total = len(closes)

    # Signal positions with enough forward bars
    signal_idx = np.where(mask.values)[0]
    usable     = signal_idx[signal_idx + horizon < n_total]
    n_signals  = len(usable)

    if n_signals < 10:
        return {
            "n_signals": n_signals, "horizon": horizon,
            "error": f"too few events (n={n_signals}, need >=10)",
            "passed": False,
        }

    # Real hit rate
    real_rets = np.array([
        (closes[i + horizon] / closes[i] - 1) * 100.0 for i in usable
    ], dtype=float)
    real_hit = float(np.mean(real_rets > 0))
    real_avg = float(np.mean(real_rets))

    # Valid pool for shuffle (skip burn-in and tail)
    valid = np.arange(burn_in, n_total - horizon - 1)
    if len(valid) < n_signals:
        return {
            "n_signals": n_signals, "horizon": horizon,
            "error": "insufficient valid positions for shuffle",
            "passed": False,
        }

    rng           = np.random.RandomState(seed)
    shuffled_hits = np.empty(n_shuffles, dtype=float)
    for k in range(n_shuffles):
        idx  = rng.choice(valid, size=n_signals, replace=False)
        rets = (closes[idx + horizon] / closes[idx] - 1) * 100.0
        shuffled_hits[k] = float(np.mean(rets > 0))

    shuffle_mean = float(np.mean(shuffled_hits))
    shuffle_p95  = float(np.percentile(shuffled_hits, 95))
    shuffle_std  = float(np.std(shuffled_hits))
    passed       = real_hit > shuffle_p95
    # p-value: fraction of shuffles that beat real hit rate
    p_value      = float(np.mean(shuffled_hits >= real_hit))

    return {
        "n_signals":        n_signals,
        "horizon":          horizon,
        "real_hit_rate":    round(real_hit, 4),
        "real_avg_return":  round(real_avg, 4),
        "shuffle_mean_hit": round(shuffle_mean, 4),
        "shuffle_p95_hit":  round(shuffle_p95, 4),
        "shuffle_std_hit":  round(shuffle_std, 4),
        "n_shuffles":       n_shuffles,
        "passed":           passed,
        "p_value":          round(p_value, 4),
        "error":            None,
    }
