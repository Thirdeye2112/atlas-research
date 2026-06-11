"""
OMNI proxy and OSCAR oscillator features.

Key insight: Oscar Carboni's OMNI appears to track candle LOWS, not closes.
This module implements and compares multiple lows-tracking MA variants.

Variants tested:
  ema_lows_N   — EMA applied to daily LOW prices
  wma_lows_N   — Weighted MA of lows
  dema_lows_N  — Double EMA of lows (less lag)
  ema_median_N — EMA of (High+Low)/2
  ema_typical_N— EMA of (High+Low+Close)/3
  hma_N        — Hull MA of closes (2*WMA(n/2) - WMA(n) → WMA(sqrt(n)))

OSCAR formula (smoothed stochastic):
  A = rolling_max(High, N); B = rolling_min(Low, N)
  rough = (Close - B) / (A - B) * 100
  oscar[i] = oscar[i-1] * 2/3 + rough * 1/3

Purity contract: pure functions, no I/O, no global state.
"""

from __future__ import annotations

import math

import numpy as np


# ── Low-level MA functions ───────────────────────────────────────────────────

def ema(values: np.ndarray, period: int) -> np.ndarray:
    """Exponential moving average. NaN before period-1 seed bar."""
    k = 2.0 / (period + 1.0)
    out = np.full(len(values), np.nan)
    if len(values) < period:
        return out
    out[period - 1] = float(np.mean(values[:period]))
    for i in range(period, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1.0 - k)
    return out


def dema(values: np.ndarray, period: int) -> np.ndarray:
    """Double EMA: 2*EMA(N) - EMA(EMA(N)). Reduces lag vs plain EMA."""
    e1 = ema(values, period)
    valid = ~np.isnan(e1)
    valid_vals = e1[valid]
    e2_compact = ema(valid_vals, period)
    out = np.full(len(values), np.nan)
    valid_idx = np.where(valid)[0]
    n2 = len(e2_compact)
    if n2 == 0:
        return out
    start = len(valid_idx) - n2
    for j in range(n2):
        i = valid_idx[start + j]
        if not np.isnan(e2_compact[j]):
            out[i] = 2.0 * e1[i] - e2_compact[j]
    return out


def wma(values: np.ndarray, period: int) -> np.ndarray:
    """Linearly-weighted moving average. Weight of bar k (oldest=1, newest=period)."""
    n = len(values)
    out = np.full(n, np.nan)
    if n < period:
        return out
    weights = np.arange(1, period + 1, dtype=np.float64)
    w_sum = weights.sum()
    for i in range(period - 1, n):
        out[i] = np.dot(values[i - period + 1: i + 1], weights) / w_sum
    return out


def hma(close: np.ndarray, period: int) -> np.ndarray:
    """Hull MA: WMA(2*WMA(close, n/2) − WMA(close, n), sqrt(n))."""
    half = max(period // 2, 2)
    sqrtn = max(int(round(period ** 0.5)), 2)
    w_half = wma(close, half)
    w_full = wma(close, period)
    diff = 2.0 * w_half - w_full
    return wma(diff, sqrtn)


def oscar(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    """OSCAR oscillator (0–100). Smoothed stochastic: 2/3 * prev + 1/3 * rough."""
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


# ── Convenience constructors ─────────────────────────────────────────────────

def ema_lows(low: np.ndarray, period: int) -> np.ndarray:
    return ema(low, period)


def wma_lows(low: np.ndarray, period: int) -> np.ndarray:
    return wma(low, period)


def dema_lows(low: np.ndarray, period: int) -> np.ndarray:
    return dema(low, period)


def ema_median(high: np.ndarray, low: np.ndarray, period: int) -> np.ndarray:
    return ema((high + low) / 2.0, period)


def ema_typical(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> np.ndarray:
    return ema((high + low + close) / 3.0, period)


# ── Candle-bottom tracking metrics ──────────────────────────────────────────

def candle_bottom_stats(
    indicator: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    open_: np.ndarray,
) -> dict:
    """
    Compute how well an indicator tracks candle bottoms.

    Returns:
        above_lows_pct   — % bars where indicator >= bar low (stays above candle floor)
        inside_candle_pct— % bars where low <= indicator <= high (within candle range)
        avg_dist_low_pct — mean (indicator - low) / low * 100 (lower = hugs lows better)
        false_break_pct  — % bars where close < indicator (price breaks through from above)
    """
    n = len(indicator)
    valid = ~np.isnan(indicator)
    idx = np.where(valid)[0]
    if len(idx) == 0:
        return {"above_lows_pct": None, "inside_candle_pct": None,
                "avg_dist_low_pct": None, "false_break_pct": None}

    ind = indicator[idx]
    h = high[idx]; l = low[idx]; c = close[idx]

    above = np.sum(ind >= l) / len(idx) * 100
    inside = np.sum((ind >= l) & (ind <= h)) / len(idx) * 100
    avg_dist = float(np.mean((ind - l) / np.where(l > 0, l, 1) * 100))
    false_brk = np.sum(c < ind) / len(idx) * 100

    return {
        "above_lows_pct":    float(above),
        "inside_candle_pct": float(inside),
        "avg_dist_low_pct":  float(avg_dist),
        "false_break_pct":   float(false_brk),
    }


# ── Cross-signal statistics ──────────────────────────────────────────────────

def _log_ret(a: float, b: float) -> float | None:
    return math.log(b / a) if a > 0 and b > 0 else None


def cross_stats(
    indicator: np.ndarray,
    close: np.ndarray,
    horizon: int = 5,
    min_n: int = 5,
) -> dict:
    """
    Compute cross-up and cross-down forward-return statistics for an indicator
    where the signal is defined as close crossing the indicator.
    """
    n = len(close)
    up_rets, dn_rets = [], []
    for i in range(1, n - horizon):
        if np.isnan(indicator[i]) or np.isnan(indicator[i - 1]):
            continue
        r = _log_ret(close[i], close[i + horizon])
        if r is None:
            continue
        # Cross up: close[i] > indicator[i] and close[i-1] <= indicator[i-1]
        if close[i] > indicator[i] and close[i - 1] <= indicator[i - 1]:
            up_rets.append(r)
        # Cross down: close[i] < indicator[i] and close[i-1] >= indicator[i-1]
        elif close[i] < indicator[i] and close[i - 1] >= indicator[i - 1]:
            dn_rets.append(r)

    def _s(rets: list) -> dict:
        if len(rets) < min_n:
            return {"n": len(rets), "hit_rate": None, "avg_ret_pct": None}
        hr = sum(1 for r in rets if r > 0) / len(rets)
        avg = sum(rets) / len(rets)
        return {"n": len(rets), "hit_rate": hr * 100, "avg_ret_pct": avg * 100}

    return {"cross_up": _s(up_rets), "cross_down": _s(dn_rets)}


# ── Full variant comparison ──────────────────────────────────────────────────

VARIANTS = [
    ("ema_lows_55",    55),
    ("ema_lows_82",    82),
    ("ema_lows_87",    87),
    ("ema_lows_89",    89),
    ("wma_lows_87",    87),
    ("dema_lows_87",   87),
    ("ema_median_87",  87),
    ("ema_typical_87", 87),
    ("hma_82",         82),
    ("hma_87",         87),
    # baseline: original close-based EMA
    ("ema_close_87",   87),
]


def compute_variants(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    open_: np.ndarray,
    horizon: int = 5,
) -> list[dict]:
    """
    Compute all OMNI candidate variants on one ticker.
    Returns list of result dicts sorted by above_lows_pct descending.
    """
    results = []
    for name, period in VARIANTS:
        if name.startswith("ema_lows"):
            ind = ema_lows(low, period)
        elif name.startswith("wma_lows"):
            ind = wma_lows(low, period)
        elif name.startswith("dema_lows"):
            ind = dema_lows(low, period)
        elif name.startswith("ema_median"):
            ind = ema_median(high, low, period)
        elif name.startswith("ema_typical"):
            ind = ema_typical(high, low, close, period)
        elif name.startswith("hma"):
            ind = hma(close, period)
        elif name.startswith("ema_close"):
            ind = ema(close, period)
        else:
            continue

        stats = candle_bottom_stats(ind, high, low, close, open_)
        cs = cross_stats(ind, close, horizon=horizon)
        results.append({
            "variant": name,
            "period": period,
            **stats,
            "cross_up_n":       cs["cross_up"]["n"],
            "cross_up_hit":     cs["cross_up"]["hit_rate"],
            "cross_up_avg":     cs["cross_up"]["avg_ret_pct"],
            "cross_down_n":     cs["cross_down"]["n"],
            "cross_down_hit":   cs["cross_down"]["hit_rate"],
            "cross_down_avg":   cs["cross_down"]["avg_ret_pct"],
        })

    results.sort(key=lambda x: x["above_lows_pct"] or 0, reverse=True)
    return results


def print_variant_table(results: list[dict]) -> None:
    """Print a ranked comparison table of all variants."""
    print(f"\n{'Variant':<20} {'Per':>3} {'AbvLow%':>8} {'InCndl%':>8} {'DistLow%':>9} {'FalsBrk%':>9} {'XUp_n':>6} {'XUp_Hit%':>9} {'XDn_Hit%':>9}")
    print("─" * 95)
    for r in results:
        def _f(v, fmt=".1f"):
            return f"{v:{fmt}}" if v is not None else "  N/A"
        print(
            f"  {r['variant']:<18} {r['period']:>3}"
            f" {_f(r['above_lows_pct']):>8}"
            f" {_f(r['inside_candle_pct']):>8}"
            f" {_f(r['avg_dist_low_pct']):>9}"
            f" {_f(r['false_break_pct']):>9}"
            f" {r['cross_up_n']:>6}"
            f" {_f(r['cross_up_hit']):>9}"
            f" {_f(r['cross_down_hit']):>9}"
        )

    best_bottom = max(results, key=lambda x: (x["above_lows_pct"] or 0))
    best_hu = [r for r in results if r["cross_up_hit"] is not None]
    if best_hu:
        best_cross = max(best_hu, key=lambda x: x["cross_up_hit"])
        print(f"\nBest candle-bottom tracker : {best_bottom['variant']} (above_lows={best_bottom['above_lows_pct']:.1f}%)")
        print(f"Best cross-up signal       : {best_cross['variant']} (hit={best_cross['cross_up_hit']:.1f}%, n={best_cross['cross_up_n']})")


# ── Feature factory entry point ──────────────────────────────────────────────

def compute(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    open_: np.ndarray | None = None,
) -> dict[str, float | None]:
    """
    Compute OMNI proxy and OSCAR features for the final bar.

    Primary OMNI: EMA(Low, 82) — confirmed as Oscar Carboni's OMNI indicator.
    Secondary: EMA(Low, 87), HMA(87), OSCAR(87).
    """
    n = len(close)
    result: dict[str, float | None] = {}

    # ── Primary OMNI: EMA of lows, period 82 (confirmed) ────────────────────
    P82 = 82
    if n >= P82 + 6:
        e82 = ema_lows(low, P82)
        cur82 = float(e82[-1])
        prev82 = float(e82[-6])
        result["omni_82_value"]    = cur82
        result["omni_82_above"]    = 1.0 if close[-1] > cur82 else 0.0
        result["omni_82_distance"] = (close[-1] - cur82) / cur82 if cur82 != 0 else None
        # slope: fractional change over 5 bars (scale-invariant)
        result["omni_82_slope"]    = (cur82 - prev82) / abs(prev82) if prev82 != 0 and not np.isnan(prev82) else None
        # bounce: low within 0.5% of OMNI and today closed bullish
        if open_ is not None:
            dist = abs(low[-1] - cur82) / cur82 if cur82 > 0 else float("inf")
            result["omni_82_bounce"] = 1.0 if dist <= 0.005 and close[-1] > open_[-1] else 0.0
        else:
            result["omni_82_bounce"] = None
    else:
        result["omni_82_value"]    = None
        result["omni_82_above"]    = None
        result["omni_82_distance"] = None
        result["omni_82_slope"]    = None
        result["omni_82_bounce"]   = None

    # ── EMA of lows, period 87 (secondary) ──────────────────────────────────
    P87 = 87
    if n >= P87 + 6:
        e87 = ema_lows(low, P87)
        cur87 = float(e87[-1])
        prev87 = float(e87[-6])
        result["omni_87_distance"] = (close[-1] - cur87) / cur87 if cur87 != 0 else None
        result["omni_87_slope"]    = (cur87 - prev87) / abs(prev87) if prev87 != 0 and not np.isnan(prev87) else None
        result["omni_87_above"]    = 1.0 if close[-1] > cur87 else 0.0
        result["omni_87_value"]    = cur87
    else:
        result["omni_87_distance"] = None
        result["omni_87_slope"]    = None
        result["omni_87_above"]    = None
        result["omni_87_value"]    = None

    # ── HMA 87 (lower lag) ───────────────────────────────────────────────────
    if n >= P87 + 15:
        h87 = hma(close, P87)
        hval = float(h87[-1])
        result["hma_87_distance"] = (close[-1] - hval) / hval if hval != 0 and not np.isnan(hval) else None
        result["hma_87_above"]    = 1.0 if (not np.isnan(hval) and close[-1] > hval) else 0.0
    else:
        result["hma_87_distance"] = None
        result["hma_87_above"]    = None

    # ── OSCAR 87-period ──────────────────────────────────────────────────────
    if n >= P87:
        osc = oscar(high, low, close, P87)
        val = float(osc[-1])
        if not np.isnan(val):
            result["oscar_87_value"]    = val
            result["oscar_87_above_50"] = 1.0 if val > 50.0 else 0.0
        else:
            result["oscar_87_value"]    = None
            result["oscar_87_above_50"] = None
    else:
        result["oscar_87_value"]    = None
        result["oscar_87_above_50"] = None

    return result


def _empty() -> dict[str, None]:
    return {k: None for k in [
        "omni_82_value", "omni_82_above", "omni_82_distance", "omni_82_slope", "omni_82_bounce",
        "omni_87_distance", "omni_87_slope", "omni_87_above", "omni_87_value",
        "hma_87_distance", "hma_87_above",
        "oscar_87_value", "oscar_87_above_50",
    ]}


# ── Conditional engine helpers ────────────────────────────────────────────────

def ema_lows_cross_up_indices(low: np.ndarray, close: np.ndarray, period: int) -> list[int]:
    """Indices where close crosses above EMA(low, period)."""
    ind = ema_lows(low, period)
    hits = []
    for i in range(period, len(close)):
        if np.isnan(ind[i]) or np.isnan(ind[i - 1]):
            continue
        if close[i] > ind[i] and close[i - 1] <= ind[i - 1]:
            hits.append(i)
    return hits


def ema_lows_cross_down_indices(low: np.ndarray, close: np.ndarray, period: int) -> list[int]:
    """Indices where close crosses below EMA(low, period)."""
    ind = ema_lows(low, period)
    hits = []
    for i in range(period, len(close)):
        if np.isnan(ind[i]) or np.isnan(ind[i - 1]):
            continue
        if close[i] < ind[i] and close[i - 1] >= ind[i - 1]:
            hits.append(i)
    return hits


def ema_lows_support_indices(
    low: np.ndarray, close: np.ndarray, open_: np.ndarray, period: int,
    touch_pct: float = 0.005,
) -> list[int]:
    """
    Indices where: bar low touches EMA(low) within touch_pct AND bar closes bullish.
    Models a price bounce off the OMNI support line.
    """
    ind = ema_lows(low, period)
    hits = []
    for i in range(period, len(close)):
        if np.isnan(ind[i]) or ind[i] <= 0:
            continue
        dist = abs(low[i] - ind[i]) / ind[i]
        if dist <= touch_pct and close[i] > open_[i]:
            hits.append(i)
    return hits


def hma_cross_up_indices(close: np.ndarray, period: int) -> list[int]:
    """Indices where close crosses above HMA(close, period)."""
    ind = hma(close, period)
    sqrtn = max(int(round(period ** 0.5)), 2)
    hits = []
    for i in range(period + sqrtn, len(close)):
        if np.isnan(ind[i]) or np.isnan(ind[i - 1]):
            continue
        if close[i] > ind[i] and close[i - 1] <= ind[i - 1]:
            hits.append(i)
    return hits


def hma_cross_down_indices(close: np.ndarray, period: int) -> list[int]:
    """Indices where close crosses below HMA(close, period)."""
    ind = hma(close, period)
    sqrtn = max(int(round(period ** 0.5)), 2)
    hits = []
    for i in range(period + sqrtn, len(close)):
        if np.isnan(ind[i]) or np.isnan(ind[i - 1]):
            continue
        if close[i] < ind[i] and close[i - 1] >= ind[i - 1]:
            hits.append(i)
    return hits


# Legacy aliases (used by existing patterns in migration 0013)

def omni_cross_up_indices(close: np.ndarray, period: int) -> list[int]:
    """Close crosses above EMA(close, period) — original close-based variant."""
    return ema_lows_cross_up_indices(close, close, period)


def omni_cross_down_indices(close: np.ndarray, period: int) -> list[int]:
    return ema_lows_cross_down_indices(close, close, period)


def omni_above_nd_indices(close: np.ndarray, period: int, n_days: int) -> list[int]:
    e = ema(close, period)
    hits = []
    for i in range(period + n_days - 1, len(close)):
        if any(np.isnan(e[i - k]) for k in range(n_days)):
            continue
        if all(close[i - k] > e[i - k] for k in range(n_days)):
            hits.append(i)
    return hits


def omni_below_nd_indices(close: np.ndarray, period: int, n_days: int) -> list[int]:
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
    osc = oscar(high, low, close, period)
    return [i for i in range(period, len(close)) if not np.isnan(osc[i]) and osc[i] > 50.0]


def ema_lows_above_nd_indices(
    low: np.ndarray, close: np.ndarray, period: int, n_days: int
) -> list[int]:
    """Indices where close > EMA(low, period) for n_days consecutive bars."""
    ind = ema_lows(low, period)
    hits = []
    for i in range(period + n_days - 1, len(close)):
        if any(np.isnan(ind[i - k]) for k in range(n_days)):
            continue
        if all(close[i - k] > ind[i - k] for k in range(n_days)):
            hits.append(i)
    return hits


def ema_lows_green_slope_indices(
    low: np.ndarray, close: np.ndarray, period: int, slope_bars: int = 5
) -> list[int]:
    """Indices where close > EMA(low, period) AND indicator slope is positive."""
    ind = ema_lows(low, period)
    hits = []
    for i in range(period + slope_bars, len(close)):
        if np.isnan(ind[i]) or np.isnan(ind[i - slope_bars]):
            continue
        if close[i] > ind[i] and ind[i] > ind[i - slope_bars]:
            hits.append(i)
    return hits


def compare_periods(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    periods: list[int],
    horizon: int = 5,
) -> list[dict]:
    """Backtest OSCAR cross_up_50 across multiple periods on one ticker."""
    results = []
    for p in periods:
        crosses = oscar_cross_up_indices(high, low, close, p)
        usable = [i for i in crosses if i + horizon < len(close)]
        if len(usable) < 5:
            results.append({"period": p, "n_signals": len(usable), "hit_rate": None, "avg_return_5d": None})
            continue
        returns = [_log_ret(close[i], close[i + horizon]) for i in usable]
        returns = [r for r in returns if r is not None]
        hit_rate = sum(1 for r in returns if r > 0) / len(returns) if returns else None
        avg_ret = sum(returns) / len(returns) if returns else None
        results.append({"period": p, "n_signals": len(usable), "hit_rate": hit_rate, "avg_return_5d": avg_ret})
    return results
