"""
OMNI proxy and OSCAR oscillator features.

OMNI proxy: 87-period EMA cross-based system (hypothesis: Oscar Carboni's OMNI ≈ 87 EMA).
OSCAR oscillator: smoothed stochastic oscillator at configurable periods.

OSCAR formula (Miner / Carboni formulation):
    A = rolling_max(High, N)
    B = rolling_min(Low, N)
    rough = (Close - B) / (A - B) * 100
    oscar[i] = oscar[i-1] * 2/3 + rough * 1/3

Purity contract: pure functions, no I/O, no global state.
"""

from __future__ import annotations

import numpy as np


# ── Low-level computation ────────────────────────────────────────────────────

def ema(close: np.ndarray, period: int) -> np.ndarray:
    """Exponential moving average. Returns array same length as close, NaN before seed."""
    k = 2.0 / (period + 1.0)
    out = np.full(len(close), np.nan)
    if len(close) < period:
        return out
    out[period - 1] = float(np.mean(close[:period]))
    for i in range(period, len(close)):
        out[i] = close[i] * k + out[i - 1] * (1.0 - k)
    return out


def dema(close: np.ndarray, period: int) -> np.ndarray:
    """Double EMA: 2*EMA(N) - EMA(EMA(N)). Reduces lag vs plain EMA."""
    e1 = ema(close, period)
    e2 = ema(e1[~np.isnan(e1)], period)
    out = np.full(len(close), np.nan)
    valid_mask = ~np.isnan(e1)
    valid_indices = np.where(valid_mask)[0]
    n_e2 = len(e2)
    if n_e2 == 0:
        return out
    start = valid_indices[len(valid_indices) - n_e2]
    for j, i in enumerate(valid_indices[len(valid_indices) - n_e2:]):
        if not np.isnan(e2[j]):
            out[i] = 2.0 * e1[i] - e2[j]
    return out


def oscar(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """
    OSCAR oscillator (0-100 scale).
    Smoothed stochastic: oscar[i] = 2/3 * oscar[i-1] + 1/3 * rough[i]
    """
    n = len(close)
    out = np.full(n, np.nan)
    if n < period:
        return out
    for i in range(period - 1, n):
        A = float(np.max(high[i - period + 1: i + 1]))
        B = float(np.min(low[i - period + 1: i + 1]))
        rng = A - B
        rough = (close[i] - B) / rng * 100.0 if rng > 0 else 50.0
        if i == period - 1 or np.isnan(out[i - 1]):
            out[i] = rough
        else:
            out[i] = out[i - 1] * (2.0 / 3.0) + rough * (1.0 / 3.0)
    return out


# ── Feature factory entry point ──────────────────────────────────────────────

OSCAR_ML_PERIOD = 87


def compute(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
) -> dict[str, float | None]:
    """
    Compute OMNI proxy and OSCAR features for the final bar.

    Returns:
        Dict of feature_name → float | None.
    """
    n = len(close)
    result: dict[str, float | None] = {}

    # ── 87-period EMA OMNI proxy ─────────────────────────────────────────────
    PERIOD = 87
    if n >= PERIOD + 5:
        e87 = ema(close, PERIOD)
        cur_ema = float(e87[-1])
        prev_ema = float(e87[-6])
        result["omni_87_distance"] = (close[-1] - cur_ema) / cur_ema if cur_ema != 0 else None
        result["omni_87_slope"] = (cur_ema - prev_ema) / abs(prev_ema) if prev_ema != 0 and not np.isnan(prev_ema) else None
        result["omni_87_above"] = 1.0 if close[-1] > cur_ema else 0.0
    else:
        result["omni_87_distance"] = None
        result["omni_87_slope"] = None
        result["omni_87_above"] = None

    # ── OSCAR 87-period (ML features only) ──────────────────────────────────
    if n >= OSCAR_ML_PERIOD:
        osc = oscar(high, low, close, OSCAR_ML_PERIOD)
        val = float(osc[-1])
        if not np.isnan(val):
            result["oscar_87_value"] = val
            result["oscar_87_above_50"] = 1.0 if val > 50.0 else 0.0
        else:
            result["oscar_87_value"] = None
            result["oscar_87_above_50"] = None
    else:
        result["oscar_87_value"] = None
        result["oscar_87_above_50"] = None

    return result


def _empty() -> dict[str, None]:
    return {k: None for k in [
        "omni_87_distance", "omni_87_slope", "omni_87_above",
        "oscar_87_value", "oscar_87_above_50",
    ]}


# ── Conditional engine helpers (used by engine.py evaluators) ────────────────

def omni_cross_up_indices(close: np.ndarray, period: int) -> list[int]:
    """Indices where close crosses from below to above the N-period EMA."""
    e = ema(close, period)
    hits = []
    for i in range(period, len(close)):
        if np.isnan(e[i]) or np.isnan(e[i - 1]):
            continue
        if close[i] > e[i] and close[i - 1] <= e[i - 1]:
            hits.append(i)
    return hits


def omni_cross_down_indices(close: np.ndarray, period: int) -> list[int]:
    """Indices where close crosses from above to below the N-period EMA."""
    e = ema(close, period)
    hits = []
    for i in range(period, len(close)):
        if np.isnan(e[i]) or np.isnan(e[i - 1]):
            continue
        if close[i] < e[i] and close[i - 1] >= e[i - 1]:
            hits.append(i)
    return hits


def omni_above_nd_indices(close: np.ndarray, period: int, n_days: int) -> list[int]:
    """Indices where close has been above N-period EMA for n_days consecutive bars."""
    e = ema(close, period)
    hits = []
    for i in range(period + n_days - 1, len(close)):
        if any(np.isnan(e[i - k]) for k in range(n_days)):
            continue
        if all(close[i - k] > e[i - k] for k in range(n_days)):
            hits.append(i)
    return hits


def omni_below_nd_indices(close: np.ndarray, period: int, n_days: int) -> list[int]:
    """Indices where close has been below N-period EMA for n_days consecutive bars."""
    e = ema(close, period)
    hits = []
    for i in range(period + n_days - 1, len(close)):
        if any(np.isnan(e[i - k]) for k in range(n_days)):
            continue
        if all(close[i - k] < e[i - k] for k in range(n_days)):
            hits.append(i)
    return hits


def oscar_cross_up_indices(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int
) -> list[int]:
    """Indices where OSCAR crosses above 50."""
    osc = oscar(high, low, close, period)
    hits = []
    for i in range(period + 1, len(close)):
        if np.isnan(osc[i]) or np.isnan(osc[i - 1]):
            continue
        if osc[i] > 50.0 and osc[i - 1] <= 50.0:
            hits.append(i)
    return hits


def oscar_cross_down_indices(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int
) -> list[int]:
    """Indices where OSCAR crosses below 50."""
    osc = oscar(high, low, close, period)
    hits = []
    for i in range(period + 1, len(close)):
        if np.isnan(osc[i]) or np.isnan(osc[i - 1]):
            continue
        if osc[i] < 50.0 and osc[i - 1] >= 50.0:
            hits.append(i)
    return hits


def oscar_above_50_indices(
    high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int
) -> list[int]:
    """Indices where OSCAR is above 50 (bullish regime)."""
    osc = oscar(high, low, close, period)
    return [i for i in range(period, len(close)) if not np.isnan(osc[i]) and osc[i] > 50.0]


def compare_periods(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    periods: list[int],
    horizon: int = 5,
) -> list[dict]:
    """
    Backtest cross_up_50 for multiple OSCAR periods on one ticker.
    Returns list of dicts with period, n_signals, hit_rate, avg_return.
    """
    import math
    results = []
    for p in periods:
        crosses = oscar_cross_up_indices(high, low, close, p)
        usable = [i for i in crosses if i + horizon < len(close)]
        if len(usable) < 5:
            results.append({"period": p, "n_signals": len(usable), "hit_rate": None, "avg_return_5d": None})
            continue
        returns = []
        for i in usable:
            if close[i] > 0 and close[i + horizon] > 0:
                returns.append(math.log(close[i + horizon] / close[i]))
        hit_rate = sum(1 for r in returns if r > 0) / len(returns) if returns else None
        avg_ret = sum(returns) / len(returns) if returns else None
        results.append({"period": p, "n_signals": len(usable), "hit_rate": hit_rate, "avg_return_5d": avg_ret})
    return results
