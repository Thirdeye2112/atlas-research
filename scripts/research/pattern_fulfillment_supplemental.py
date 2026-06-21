"""
pattern_fulfillment_supplemental.py
======================================
Builds Candidate records for 4 shapes NOT in pattern_reference's 43 rows
(per the brief's explicit ask to also detect candle/structure shapes the
user's eye flagged): flat_top, long_upper_wick, long_lower_wick,
continuation_candle. Defined here, mechanically, by analogy to the nearest
official patterns -- documented per-shape below. Reported separately from
the official 43 throughout (no pattern_reference row => no taught
expected_direction/confirmation/invalidation to validate against, and no
invalidation_becomes => excluded from the Step 4 inversion test).

double_top and double_bottom (also user-flagged) are NOT redefined here --
they are already pattern_reference rows, handled in
pattern_fulfillment_chartpatterns.py.

Runs on both 5m and daily (cheap, same geometry as the candlestick family).
"""
from __future__ import annotations

import numpy as np

from pattern_fulfillment_common import Candidate

WICK_MULT = 2.0
SMALL_BODY = 0.40
STRONG_BODY_PCT = 60.0       # consistent with v1/v2's GEOM_BODY_PCT_MIN
FLAT_TOP_LOOKBACK = 10
FLAT_TOP_EQ_TOL = 0.0015


def build_supplemental_candidates(o, h, l, c, ticker: str, timeframe: str) -> list[Candidate]:
    o = np.asarray(o, float); h = np.asarray(h, float)
    l = np.asarray(l, float); c = np.asarray(c, float)
    n = len(c)
    out = []

    rng = (h - l)
    body = np.abs(c - o)
    upper = h - np.maximum(o, c)
    lower = np.minimum(o, c) - l
    with np.errstate(divide="ignore", invalid="ignore"):
        body_pct = np.where(rng > 0, body / rng * 100.0, 0.0)

    # ---- long_upper_wick / long_lower_wick (no trend-context split, unlike
    # candlesticks.py's shooting_star/hammer -- this is the simpler "any bar
    # with a dominant wick" shape the user's eye flagged) -------------------
    for i in range(n):
        if rng[i] <= 0 or body[i] <= 0:
            continue
        if body[i] / rng[i] < SMALL_BODY:
            if upper[i] >= WICK_MULT * body[i] and lower[i] <= body[i]:
                out.append(Candidate("long_upper_wick", ticker, timeframe, i, "short",
                                      confirm_level=l[i], invalidate_level=h[i]))
            if lower[i] >= WICK_MULT * body[i] and upper[i] <= body[i]:
                out.append(Candidate("long_lower_wick", ticker, timeframe, i, "long",
                                      confirm_level=h[i], invalidate_level=l[i]))

    # ---- continuation_candle: bar i-1 is a strong directional bar, bar i is
    # the same color AND closes beyond bar i-1's extreme (the "2nd candle
    # confirming the prior move" the user flagged) -- recognition already
    # requires confirmation, so confirmed_immediately=True (same treatment
    # as morning_star/macd: the real test is Stage B's R-bracket). ----------
    is_green = c > o
    is_red = c < o
    for i in range(1, n):
        if body_pct[i - 1] < STRONG_BODY_PCT:
            continue
        if is_green[i - 1] and is_green[i] and c[i] > h[i - 1]:
            out.append(Candidate("continuation_candle", ticker, timeframe, i, "long",
                                  confirm_level=None, invalidate_level=None, confirmed_immediately=True))
        if is_red[i - 1] and is_red[i] and c[i] < l[i - 1]:
            out.append(Candidate("continuation_candle", ticker, timeframe, i, "short",
                                  confirm_level=None, invalidate_level=None, confirmed_immediately=True))

    # ---- flat_top: high[i] tests the same ceiling as the max high over the
    # preceding lookback window (a looser, non-pivot-based "capped" shape,
    # distinct from double_top's strict 3-pivot H-L-H structure), bar i
    # itself rejects (closes red). direction=short. -------------------------
    for i in range(FLAT_TOP_LOOKBACK, n):
        window_highs = h[i - FLAT_TOP_LOOKBACK:i]
        prior_max = window_highs.max()
        if prior_max <= 0:
            continue
        if abs(h[i] - prior_max) / prior_max <= FLAT_TOP_EQ_TOL and is_red[i]:
            recent_low = l[i - FLAT_TOP_LOOKBACK:i + 1].min()
            out.append(Candidate("flat_top", ticker, timeframe, i, "short",
                                  confirm_level=recent_low, invalidate_level=h[i]))

    return sorted(out, key=lambda cd: cd.idx)
