"""
structure.py — the "eyes": market structure from price.

Everything a technical trader reads visually before naming a pattern:
  - swing pivots (the peaks and troughs)
  - trend (higher-highs/higher-lows = up, etc.)
  - support / resistance levels (clusters of pivots)
  - trendlines (lines connecting swings)

Pure functions on numpy arrays so they work on weekly, daily, or 5-min bars.
Pivots use the fractal / rolling-window method (a swing high is the highest
high within +/-`width` bars), then are de-duplicated to strictly alternate
High, Low, High, Low...  This is the standard, robust foundation for chart
pattern recognition.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass
class Pivot:
    idx: int          # bar index
    price: float      # pivot price (high for 'H', low for 'L')
    kind: str         # 'H' or 'L'


def swing_pivots(high: np.ndarray, low: np.ndarray, width: int = 3) -> list[Pivot]:
    """
    Fractal swing pivots. A bar i is a swing HIGH if high[i] is the strict max
    of the window [i-width, i+width]; a swing LOW if low[i] is the strict min.
    Then enforce strict H/L alternation, keeping the more extreme pivot when two
    of the same kind occur in a row (the ZigZag clean-up).
    """
    n = len(high)
    raw: list[Pivot] = []
    for i in range(width, n - width):
        win_hi = high[i-width:i+width+1]
        win_lo = low[i-width:i+width+1]
        is_high = high[i] == win_hi.max() and (high[i] > high[i-width:i]).all() and (high[i] >= high[i+1:i+width+1]).all()
        is_low  = low[i]  == win_lo.min() and (low[i]  < low[i-width:i]).all()  and (low[i]  <= low[i+1:i+width+1]).all()
        if is_high and not is_low:
            raw.append(Pivot(i, float(high[i]), 'H'))
        elif is_low and not is_high:
            raw.append(Pivot(i, float(low[i]), 'L'))

    # Enforce alternation: collapse consecutive same-kind pivots to the extreme.
    out: list[Pivot] = []
    for p in raw:
        if not out or out[-1].kind != p.kind:
            out.append(p)
        else:
            prev = out[-1]
            if (p.kind == 'H' and p.price >= prev.price) or (p.kind == 'L' and p.price <= prev.price):
                out[-1] = p
    return out


def classify_trend(pivots: list[Pivot], lookback: int = 4) -> str:
    """
    Trend from the last `lookback` pivots:
      up    = higher highs AND higher lows
      down  = lower highs  AND lower lows
      range = otherwise
    """
    if len(pivots) < lookback:
        return "range"
    last = pivots[-lookback:]
    highs = [p.price for p in last if p.kind == 'H']
    lows  = [p.price for p in last if p.kind == 'L']
    if len(highs) < 2 or len(lows) < 2:
        return "range"
    hh = highs[-1] > highs[0]; hl = lows[-1] > lows[0]
    lh = highs[-1] < highs[0]; ll = lows[-1] < lows[0]
    if hh and hl: return "up"
    if lh and ll: return "down"
    return "range"


def support_resistance(pivots: list[Pivot], price: float, tol_pct: float = 0.015,
                       min_touches: int = 2) -> list[dict]:
    """
    Cluster pivot prices into S/R levels (levels touched >= min_touches).
    Returns levels sorted by distance from `price`, each with touch count and side.
    """
    levels: list[list[float]] = []
    for p in sorted(pivots, key=lambda x: x.price):
        if levels and abs(p.price - np.mean(levels[-1])) / np.mean(levels[-1]) <= tol_pct:
            levels[-1].append(p.price)
        else:
            levels.append([p.price])
    out = []
    for grp in levels:
        if len(grp) >= min_touches:
            lvl = float(np.mean(grp))
            out.append({"level": lvl, "touches": len(grp),
                        "side": "resistance" if lvl >= price else "support",
                        "dist_pct": (lvl - price) / price})
    return sorted(out, key=lambda d: abs(d["dist_pct"]))


def trendline(pivots: list[Pivot], kind: str, n: int = 3):
    """
    Fit a line (slope, intercept) through the last `n` pivots of a given kind
    ('H' for the resistance line down the highs, 'L' for the support line).
    Returns (slope_per_bar, intercept, [pivot_indices]) or None.
    """
    pts = [p for p in pivots if p.kind == kind][-n:]
    if len(pts) < 2:
        return None
    xs = np.array([p.idx for p in pts], float); ys = np.array([p.price for p in pts], float)
    slope, intercept = np.polyfit(xs, ys, 1)
    return float(slope), float(intercept), [p.idx for p in pts]


def structure_summary(high, low, close, width: int = 3) -> dict:
    """One call: pivots + trend + nearest S/R + up/down trendlines."""
    piv = swing_pivots(high, low, width)
    price = float(close[-1])
    return {
        "pivots": piv,
        "trend": classify_trend(piv),
        "levels": support_resistance(piv, price),
        "res_line": trendline(piv, 'H'),
        "sup_line": trendline(piv, 'L'),
        "last_price": price,
    }
