"""
candlesticks.py — the 19 named single / multi-bar candlestick patterns.

Pure functions over OHLC numpy arrays (work on daily OR 5-min bars), built to
sit alongside the chart patterns in patterns.py and log into the SAME
pattern_memory table. Each detected instance is a `Candle` carrying a
confirm_idx (the completing bar = no-lookahead entry timing), a direction, and
the bar span [start_idx, confirm_idx].

Context-dependent shapes are disambiguated by the prior trend (the same idea a
trader uses): a small-body / long-lower-wick bar is a HAMMER after a downtrend
but a HANGING MAN after an uptrend; a long-upper-wick bar is an INVERTED HAMMER
after a downtrend but a SHOOTING STAR after an uptrend.

Patterns (19):
  single : doji, spinning_top, marubozu, hammer, hanging_man,
           inverted_hammer, shooting_star
  two-bar: bullish_engulfing, bearish_engulfing, bullish_harami,
           bearish_harami, piercing, dark_cloud_cover,
           tweezer_top, tweezer_bottom
  three  : morning_star, evening_star, three_white_soldiers,
           three_black_crows

Shares the single-bar vocabulary of structure.candle_label() (doji / hammer /
shooting_star / marubozu / spinning_top) but adds the multi-bar reversals and
trend context that candle_label() deliberately omits.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Geometry thresholds (fractions of the bar range unless noted).
DOJI_BODY     = 0.10
SMALL_BODY    = 0.40
MARUBOZU_BODY = 0.90
WICK_MULT     = 2.0      # long wick >= WICK_MULT * body
HARAMI_INNER  = 0.60     # inner body must be < this * prior body
STRONG_BODY   = 0.50     # soldiers/crows need decent bodies
EQ_TOL        = 0.003    # tweezer high/low equality tolerance


@dataclass
class Candle:
    name: str
    direction: str            # 'long' | 'short' | 'neutral'
    confirm_idx: int          # completing bar (entry-timing, no lookahead)
    start_idx: int            # first bar of the pattern
    entry: float
    stop: float
    extra: dict = field(default_factory=dict)


def _sma(a: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(a), np.nan)
    if len(a) >= n:
        cs = np.cumsum(np.insert(a, 0, 0.0))
        out[n - 1:] = (cs[n:] - cs[:-n]) / n
    return out


def prior_trend(close: np.ndarray, sma_n: int = 20) -> np.ndarray:
    """+1 if close is above its SMA(sma_n), else -1. Cheap, robust trend proxy."""
    s = _sma(close, sma_n)
    return np.where(np.isnan(s), 0, np.where(close > s, 1, -1)).astype(int)


def detect_all_candles(o, h, l, c, trend: np.ndarray | None = None,
                       eq_tol: float = EQ_TOL, skip_neutral: bool = False) -> list[Candle]:
    """Detect the 19 patterns. `skip_neutral=True` drops the high-frequency,
    low-signal neutral singletons (doji, spinning_top) — useful at 5-min
    resolution where they fire on most bars. `eq_tol` controls tweezer
    high/low matching (tighten it for intraday)."""
    o = np.asarray(o, float); h = np.asarray(h, float)
    l = np.asarray(l, float); c = np.asarray(c, float)
    n = len(c)
    if n < 3:
        return []
    if trend is None:
        trend = prior_trend(c)

    rng   = h - l
    body  = np.abs(c - o)
    upper = h - np.maximum(o, c)
    lower = np.minimum(o, c) - l
    bull  = c > o
    bear  = c < o
    with np.errstate(divide="ignore", invalid="ignore"):
        br = np.where(rng > 0, body / rng, 0.0)

    out: list[Candle] = []

    def ptrend(i: int) -> int:
        # Trend established by the bar BEFORE the signal completes.
        return int(trend[i - 1]) if i - 1 >= 0 else 0

    for i in range(n):
        if rng[i] <= 0:
            continue

        # -------------------- single-bar --------------------
        if br[i] < DOJI_BODY:
            if not skip_neutral:
                out.append(Candle("doji", "neutral", i, i, c[i], l[i],
                                  {"body_pct": float(br[i])}))
        elif br[i] >= MARUBOZU_BODY:
            out.append(Candle("marubozu", "long" if bull[i] else "short", i, i,
                              c[i], l[i] if bull[i] else h[i], {"body_pct": float(br[i])}))
        elif br[i] < SMALL_BODY and upper[i] > body[i] and lower[i] > body[i]:
            if not skip_neutral:
                out.append(Candle("spinning_top", "neutral", i, i, c[i], l[i],
                                  {"body_pct": float(br[i])}))

        # hammer family: small real body + one dominant wick
        if body[i] > 0 and br[i] < SMALL_BODY:
            if lower[i] >= WICK_MULT * body[i] and upper[i] <= body[i]:
                if ptrend(i) < 0:
                    out.append(Candle("hammer", "long", i, i, c[i], l[i]))
                else:
                    out.append(Candle("hanging_man", "short", i, i, c[i], h[i]))
            elif upper[i] >= WICK_MULT * body[i] and lower[i] <= body[i]:
                if ptrend(i) < 0:
                    out.append(Candle("inverted_hammer", "long", i, i, c[i], l[i]))
                else:
                    out.append(Candle("shooting_star", "short", i, i, c[i], h[i]))

        # -------------------- two-bar --------------------
        if i >= 1:
            o1, h1, l1, c1 = o[i-1], h[i-1], l[i-1], c[i-1]
            b1 = abs(c1 - o1)
            mid1 = (o1 + c1) / 2.0

            # engulfing (current real body engulfs prior real body, opposite colour)
            if bear[i-1] and bull[i] and o[i] <= c1 and c[i] >= o1 and body[i] > b1:
                out.append(Candle("bullish_engulfing", "long", i, i-1, c[i], min(l[i], l1)))
            if bull[i-1] and bear[i] and o[i] >= c1 and c[i] <= o1 and body[i] > b1:
                out.append(Candle("bearish_engulfing", "short", i, i-1, c[i], max(h[i], h1)))

            # harami (small body contained within prior large opposite body)
            if b1 > 0 and body[i] < b1 * HARAMI_INNER:
                inside = (max(o[i], c[i]) <= max(o1, c1) and min(o[i], c[i]) >= min(o1, c1))
                if inside and bear[i-1] and ptrend(i) < 0:
                    out.append(Candle("bullish_harami", "long", i, i-1, c[i], min(l[i], l1)))
                if inside and bull[i-1] and ptrend(i) > 0:
                    out.append(Candle("bearish_harami", "short", i, i-1, c[i], max(h[i], h1)))

            # piercing / dark cloud cover
            if bear[i-1] and bull[i] and o[i] < l1 and mid1 < c[i] < o1:
                out.append(Candle("piercing", "long", i, i-1, c[i], l[i]))
            if bull[i-1] and bear[i] and o[i] > h1 and o1 < c[i] < mid1:
                out.append(Candle("dark_cloud_cover", "short", i, i-1, c[i], h[i]))

            # tweezers (matched extreme + reversal colour in the right trend)
            if l1 > 0 and abs(l[i] - l1) / l1 <= eq_tol and ptrend(i) < 0 and bull[i]:
                out.append(Candle("tweezer_bottom", "long", i, i-1, c[i], min(l[i], l1)))
            if h1 > 0 and abs(h[i] - h1) / h1 <= eq_tol and ptrend(i) > 0 and bear[i]:
                out.append(Candle("tweezer_top", "short", i, i-1, c[i], max(h[i], h1)))

        # -------------------- three-bar --------------------
        if i >= 2:
            o1, h1, l1, c1 = o[i-2], h[i-2], l[i-2], c[i-2]   # first
            o2, h2, l2, c2 = o[i-1], h[i-1], l[i-1], c[i-1]   # star / middle
            b1, b2 = abs(c1 - o1), abs(c2 - o2)
            mid1 = (o1 + c1) / 2.0

            # morning star: big bear, small star below, big bull closing past mid of bar1
            if (c1 < o1 and b1 > 0 and b2 < b1 * 0.5 and bull[i]
                    and c[i] > mid1 and max(o2, c2) < c1):
                out.append(Candle("morning_star", "long", i, i-2, c[i], min(l1, l2, l[i])))
            # evening star: big bull, small star above, big bear closing past mid of bar1
            if (c1 > o1 and b1 > 0 and b2 < b1 * 0.5 and bear[i]
                    and c[i] < mid1 and min(o2, c2) > c1):
                out.append(Candle("evening_star", "short", i, i-2, c[i], max(h1, h2, h[i])))

            # three white soldiers: 3 rising bulls, each opens within prior body
            if (bull[i-2] and bull[i-1] and bull[i] and c1 < c2 < c[i]
                    and o1 < o2 < c1 and o2 < o[i] < c2
                    and br[i-2] > STRONG_BODY and br[i-1] > STRONG_BODY and br[i] > STRONG_BODY):
                out.append(Candle("three_white_soldiers", "long", i, i-2, c[i], l1))
            # three black crows: 3 falling bears, each opens within prior body
            if (bear[i-2] and bear[i-1] and bear[i] and c1 > c2 > c[i]
                    and c1 < o2 < o1 and c2 < o[i] < o2
                    and br[i-2] > STRONG_BODY and br[i-1] > STRONG_BODY and br[i] > STRONG_BODY):
                out.append(Candle("three_black_crows", "short", i, i-2, c[i], h1))

    return sorted(out, key=lambda x: x.confirm_idx)


# Names this module can emit (for validation / reporting).
CANDLE_NAMES = [
    "doji", "spinning_top", "marubozu", "hammer", "hanging_man",
    "inverted_hammer", "shooting_star",
    "bullish_engulfing", "bearish_engulfing", "bullish_harami", "bearish_harami",
    "piercing", "dark_cloud_cover", "tweezer_top", "tweezer_bottom",
    "morning_star", "evening_star", "three_white_soldiers", "three_black_crows",
]
