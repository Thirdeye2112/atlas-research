"""
atlas_research.patterns.candlestick
=====================================
Pure-pandas candlestick pattern detection on daily OHLCV bars.
No TA-Lib dependency — all patterns computed from OHLCV directly.

Patterns detected
-----------------
Single-bar:
  doji                — open ≈ close, body < 10% of range
  hammer              — small body at top, long lower wick (bullish reversal)
  inverted_hammer     — small body at bottom, long upper wick
  shooting_star       — small body at top, long upper wick (bearish reversal)
  hanging_man         — hammer shape in uptrend (bearish)
  marubozu_bull       — full bull body, no wicks
  marubozu_bear       — full bear body, no wicks
  spinning_top        — small body, equal wicks
  long_bull           — large bull body (> 1.5× avg range)
  long_bear           — large bear body (> 1.5× avg range)

Two-bar:
  engulfing_bull      — bull bar fully engulfs prior bear bar
  engulfing_bear      — bear bar fully engulfs prior bull bar
  harami_bull         — small bull bar inside prior bear bar
  harami_bear         — small bear bar inside prior bull bar
  piercing_line       — bull bar closes above midpoint of prior bear bar
  dark_cloud_cover    — bear bar closes below midpoint of prior bull bar
  tweezer_bottom      — two bars with equal lows (support)
  tweezer_top         — two bars with equal highs (resistance)

Three-bar:
  morning_star        — bear, small doji/spinning top, bull (bullish reversal)
  evening_star        — bull, small doji/spinning top, bear (bearish reversal)
  three_white_soldiers — three consecutive long bull bars
  three_black_crows   — three consecutive long bear bars
  three_inside_up     — harami_bull + confirming bull bar
  three_inside_down   — harami_bear + confirming bear bar

Usage
-----
    from atlas_research.patterns.candlestick import detect_patterns
    import pandas as pd

    df = pd.DataFrame(...)  # must have: open, high, low, close, volume
    signals = detect_patterns(df)
    # signals: dict of {pattern_name: pd.Series(bool, index=df.index)}
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ── Body / wick helpers ───────────────────────────────────────────────────────

def _body(o: pd.Series, c: pd.Series) -> pd.Series:
    return (c - o).abs()

def _range(h: pd.Series, l: pd.Series) -> pd.Series:
    return h - l

def _upper_wick(o: pd.Series, h: pd.Series, c: pd.Series) -> pd.Series:
    return h - pd.concat([o, c], axis=1).max(axis=1)

def _lower_wick(o: pd.Series, l: pd.Series, c: pd.Series) -> pd.Series:
    return pd.concat([o, c], axis=1).min(axis=1) - l

def _avg_range(h: pd.Series, l: pd.Series, n: int = 14) -> pd.Series:
    return _range(h, l).rolling(n).mean()

def _is_bull(o: pd.Series, c: pd.Series) -> pd.Series:
    return c > o

def _is_bear(o: pd.Series, c: pd.Series) -> pd.Series:
    return c < o


# ── Single-bar patterns ───────────────────────────────────────────────────────

def _doji(o, h, l, c, threshold: float = 0.1) -> pd.Series:
    body  = _body(o, c)
    rng   = _range(h, l).replace(0, np.nan)
    return (body / rng) < threshold

def _hammer(o, h, l, c) -> pd.Series:
    body  = _body(o, c)
    rng   = _range(h, l).replace(0, np.nan)
    lower = _lower_wick(o, l, c)
    upper = _upper_wick(o, h, c)
    return (
        (body / rng < 0.35) &
        (lower / rng > 0.60) &
        (upper / rng < 0.10)
    )

def _inverted_hammer(o, h, l, c) -> pd.Series:
    body  = _body(o, c)
    rng   = _range(h, l).replace(0, np.nan)
    lower = _lower_wick(o, l, c)
    upper = _upper_wick(o, h, c)
    return (
        (body / rng < 0.35) &
        (upper / rng > 0.60) &
        (lower / rng < 0.10)
    )

def _shooting_star(o, h, l, c) -> pd.Series:
    # Same shape as inverted hammer but bearish context handled by caller
    return _inverted_hammer(o, h, l, c) & _is_bear(o, c)

def _hanging_man(o, h, l, c) -> pd.Series:
    return _hammer(o, h, l, c) & _is_bear(o, c)

def _marubozu_bull(o, h, l, c, threshold: float = 0.02) -> pd.Series:
    rng   = _range(h, l).replace(0, np.nan)
    lower = _lower_wick(o, l, c)
    upper = _upper_wick(o, h, c)
    return (
        _is_bull(o, c) &
        (lower / rng < threshold) &
        (upper / rng < threshold)
    )

def _marubozu_bear(o, h, l, c, threshold: float = 0.02) -> pd.Series:
    rng   = _range(h, l).replace(0, np.nan)
    lower = _lower_wick(o, l, c)
    upper = _upper_wick(o, h, c)
    return (
        _is_bear(o, c) &
        (lower / rng < threshold) &
        (upper / rng < threshold)
    )

def _spinning_top(o, h, l, c) -> pd.Series:
    body  = _body(o, c)
    rng   = _range(h, l).replace(0, np.nan)
    lower = _lower_wick(o, l, c)
    upper = _upper_wick(o, h, c)
    return (
        (body / rng < 0.30) &
        (lower / rng > 0.25) &
        (upper / rng > 0.25)
    )

def _long_bull(o, h, l, c, avg_rng: pd.Series, multiplier: float = 1.5) -> pd.Series:
    return _is_bull(o, c) & (_body(o, c) > multiplier * avg_rng)

def _long_bear(o, h, l, c, avg_rng: pd.Series, multiplier: float = 1.5) -> pd.Series:
    return _is_bear(o, c) & (_body(o, c) > multiplier * avg_rng)


# ── Two-bar patterns ──────────────────────────────────────────────────────────

def _engulfing_bull(o, h, l, c) -> pd.Series:
    p_o, p_c = o.shift(1), c.shift(1)
    return (
        _is_bear(p_o, p_c) &   # prior bar bearish
        _is_bull(o, c) &        # current bar bullish
        (o <= p_c) &            # open below prior close
        (c >= p_o)              # close above prior open
    )

def _engulfing_bear(o, h, l, c) -> pd.Series:
    p_o, p_c = o.shift(1), c.shift(1)
    return (
        _is_bull(p_o, p_c) &
        _is_bear(o, c) &
        (o >= p_c) &
        (c <= p_o)
    )

def _harami_bull(o, h, l, c) -> pd.Series:
    p_o, p_c = o.shift(1), c.shift(1)
    return (
        _is_bear(p_o, p_c) &
        _is_bull(o, c) &
        (o > p_c) &
        (c < p_o)
    )

def _harami_bear(o, h, l, c) -> pd.Series:
    p_o, p_c = o.shift(1), c.shift(1)
    return (
        _is_bull(p_o, p_c) &
        _is_bear(o, c) &
        (o < p_c) &
        (c > p_o)
    )

def _piercing_line(o, h, l, c) -> pd.Series:
    p_o, p_c = o.shift(1), c.shift(1)
    midpoint = (p_o + p_c) / 2
    return (
        _is_bear(p_o, p_c) &
        _is_bull(o, c) &
        (o < p_c) &
        (c > midpoint) &
        (c < p_o)
    )

def _dark_cloud_cover(o, h, l, c) -> pd.Series:
    p_o, p_c = o.shift(1), c.shift(1)
    midpoint = (p_o + p_c) / 2
    return (
        _is_bull(p_o, p_c) &
        _is_bear(o, c) &
        (o > p_c) &
        (c < midpoint) &
        (c > p_o)
    )

def _tweezer_bottom(o, h, l, c, tolerance: float = 0.001) -> pd.Series:
    p_l = l.shift(1)
    return (l - p_l).abs() / l.replace(0, np.nan) < tolerance

def _tweezer_top(o, h, l, c, tolerance: float = 0.001) -> pd.Series:
    p_h = h.shift(1)
    return (h - p_h).abs() / h.replace(0, np.nan) < tolerance


# ── Three-bar patterns ────────────────────────────────────────────────────────

def _morning_star(o, h, l, c, avg_rng: pd.Series) -> pd.Series:
    # bar -2: large bear; bar -1: small body (star); bar 0: large bull
    o2, c2 = o.shift(2), c.shift(2)
    o1, c1 = o.shift(1), c.shift(1)
    return (
        _is_bear(o2, c2) & (_body(o2, c2) > 0.6 * avg_rng.shift(2)) &
        (_body(o1, c1) < 0.3 * avg_rng.shift(1)) &
        _is_bull(o, c) & (_body(o, c) > 0.6 * avg_rng) &
        (c > (o2 + c2) / 2)
    )

def _evening_star(o, h, l, c, avg_rng: pd.Series) -> pd.Series:
    o2, c2 = o.shift(2), c.shift(2)
    o1, c1 = o.shift(1), c.shift(1)
    return (
        _is_bull(o2, c2) & (_body(o2, c2) > 0.6 * avg_rng.shift(2)) &
        (_body(o1, c1) < 0.3 * avg_rng.shift(1)) &
        _is_bear(o, c) & (_body(o, c) > 0.6 * avg_rng) &
        (c < (o2 + c2) / 2)
    )

def _three_white_soldiers(o, h, l, c, avg_rng: pd.Series) -> pd.Series:
    o2, c2 = o.shift(2), c.shift(2)
    o1, c1 = o.shift(1), c.shift(1)
    return (
        _is_bull(o2, c2) & (_body(o2, c2) > 0.5 * avg_rng.shift(2)) &
        _is_bull(o1, c1) & (_body(o1, c1) > 0.5 * avg_rng.shift(1)) &
        _is_bull(o,  c)  & (_body(o,  c)  > 0.5 * avg_rng) &
        (o1 > o2) & (c1 > c2) &
        (o  > o1) & (c  > c1)
    )

def _three_black_crows(o, h, l, c, avg_rng: pd.Series) -> pd.Series:
    o2, c2 = o.shift(2), c.shift(2)
    o1, c1 = o.shift(1), c.shift(1)
    return (
        _is_bear(o2, c2) & (_body(o2, c2) > 0.5 * avg_rng.shift(2)) &
        _is_bear(o1, c1) & (_body(o1, c1) > 0.5 * avg_rng.shift(1)) &
        _is_bear(o,  c)  & (_body(o,  c)  > 0.5 * avg_rng) &
        (o1 < o2) & (c1 < c2) &
        (o  < o1) & (c  < c1)
    )

def _three_inside_up(o, h, l, c) -> pd.Series:
    return _harami_bull(o, h, l, c).shift(1) & _is_bull(o, c) & (c > c.shift(1))

def _three_inside_down(o, h, l, c) -> pd.Series:
    return _harami_bear(o, h, l, c).shift(1) & _is_bear(o, c) & (c < c.shift(1))


# ── Public API ────────────────────────────────────────────────────────────────

SINGLE_BAR_PATTERNS = [
    "doji", "hammer", "inverted_hammer", "shooting_star", "hanging_man",
    "marubozu_bull", "marubozu_bear", "spinning_top", "long_bull", "long_bear",
]

TWO_BAR_PATTERNS = [
    "engulfing_bull", "engulfing_bear", "harami_bull", "harami_bear",
    "piercing_line", "dark_cloud_cover", "tweezer_bottom", "tweezer_top",
]

THREE_BAR_PATTERNS = [
    "morning_star", "evening_star",
    "three_white_soldiers", "three_black_crows",
    "three_inside_up", "three_inside_down",
]

ALL_PATTERNS = SINGLE_BAR_PATTERNS + TWO_BAR_PATTERNS + THREE_BAR_PATTERNS

# Directional bias for each pattern (used for outcome analysis)
PATTERN_BIAS: dict[str, str] = {
    "doji":                "neutral",
    "hammer":              "bullish",
    "inverted_hammer":     "bullish",
    "shooting_star":       "bearish",
    "hanging_man":         "bearish",
    "marubozu_bull":       "bullish",
    "marubozu_bear":       "bearish",
    "spinning_top":        "neutral",
    "long_bull":           "bullish",
    "long_bear":           "bearish",
    "engulfing_bull":      "bullish",
    "engulfing_bear":      "bearish",
    "harami_bull":         "bullish",
    "harami_bear":         "bearish",
    "piercing_line":       "bullish",
    "dark_cloud_cover":    "bearish",
    "tweezer_bottom":      "bullish",
    "tweezer_top":         "bearish",
    "morning_star":        "bullish",
    "evening_star":        "bearish",
    "three_white_soldiers": "bullish",
    "three_black_crows":   "bearish",
    "three_inside_up":     "bullish",
    "three_inside_down":   "bearish",
}


def detect_patterns(
    df: pd.DataFrame,
    avg_range_period: int = 14,
) -> dict[str, pd.Series]:
    """
    Detect all candlestick patterns in a OHLCV DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: open, high, low, close, volume
        Index should be DatetimeIndex or date-sortable.
        Must be sorted ascending by date.

    avg_range_period : int
        Rolling window for average range calculation (default 14).

    Returns
    -------
    dict[str, pd.Series]
        Keys are pattern names (see ALL_PATTERNS).
        Values are boolean Series aligned to df.index.
        True = pattern detected on that bar.
    """
    o = df["open"].astype(float)
    h = df["high"].astype(float)
    l = df["low"].astype(float)
    c = df["close"].astype(float)
    avg_rng = _avg_range(h, l, avg_range_period)

    return {
        # Single-bar
        "doji":                _doji(o, h, l, c),
        "hammer":              _hammer(o, h, l, c),
        "inverted_hammer":     _inverted_hammer(o, h, l, c),
        "shooting_star":       _shooting_star(o, h, l, c),
        "hanging_man":         _hanging_man(o, h, l, c),
        "marubozu_bull":       _marubozu_bull(o, h, l, c),
        "marubozu_bear":       _marubozu_bear(o, h, l, c),
        "spinning_top":        _spinning_top(o, h, l, c),
        "long_bull":           _long_bull(o, h, l, c, avg_rng),
        "long_bear":           _long_bear(o, h, l, c, avg_rng),
        # Two-bar
        "engulfing_bull":      _engulfing_bull(o, h, l, c),
        "engulfing_bear":      _engulfing_bear(o, h, l, c),
        "harami_bull":         _harami_bull(o, h, l, c),
        "harami_bear":         _harami_bear(o, h, l, c),
        "piercing_line":       _piercing_line(o, h, l, c),
        "dark_cloud_cover":    _dark_cloud_cover(o, h, l, c),
        "tweezer_bottom":      _tweezer_bottom(o, h, l, c),
        "tweezer_top":         _tweezer_top(o, h, l, c),
        # Three-bar
        "morning_star":        _morning_star(o, h, l, c, avg_rng),
        "evening_star":        _evening_star(o, h, l, c, avg_rng),
        "three_white_soldiers": _three_white_soldiers(o, h, l, c, avg_rng),
        "three_black_crows":   _three_black_crows(o, h, l, c, avg_rng),
        "three_inside_up":     _three_inside_up(o, h, l, c),
        "three_inside_down":   _three_inside_down(o, h, l, c),
    }


def patterns_as_dataframe(df: pd.DataFrame, **kwargs) -> pd.DataFrame:
    """
    Return detected patterns as a boolean DataFrame.
    Columns = pattern names, index = df.index.
    """
    signals = detect_patterns(df, **kwargs)
    return pd.DataFrame(signals, index=df.index).fillna(False)
