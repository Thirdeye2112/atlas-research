"""
pattern_fulfillment_candlesticks.py
======================================
Builds Candidate records for the 19 candlestick patterns, on EITHER 5m or
daily bars, by reusing atlas_research.ta.candlesticks.detect_all_candles
verbatim (no modification) and mapping each detected Candle's bar geometry
to the confirm_level / invalidate_level pair LITERALLY specified by that
pattern's pattern_reference row (see PATTERN_FULFILLMENT_REPORT.md Step 2
for the per-pattern mapping table and the handful of documented
simplifications, e.g. three_black_crows' qualitative "strong bull reversal"
invalidation is mechanized as a close above the third bar's midpoint, by
symmetry with three_white_soldiers' own midpoint-based invalidation text).

morning_star / evening_star are `confirmed_immediately=True`: per
pattern_reference, "the third bar's close above/below bar-1's midpoint IS
the confirmation (built into detection)" -- detect_all_candles already
enforces this as part of recognizing the shape at all, so for these two
T_recog == T_confirm.

doji / spinning_top are `two_sided=True`: pattern_reference's own
confirmation text doesn't commit to a direction at recognition ("next bar
closes decisively in ONE direction"), so direction is resolved by whichever
side's level breaks first during Stage A.
"""
from __future__ import annotations

import numpy as np

from atlas_research.ta.candlesticks import detect_all_candles, prior_trend
from pattern_fulfillment_common import Candidate

EQ_TOL_5M = 0.0008   # same intraday tightening v1/v2 established


def build_candlestick_candidates(o, h, l, c, ticker: str, timeframe: str) -> list[Candidate]:
    o = np.asarray(o, float); h = np.asarray(h, float)
    l = np.asarray(l, float); c = np.asarray(c, float)
    eq_tol = EQ_TOL_5M if timeframe == "5m" else 0.003
    trend = prior_trend(c)
    candles = detect_all_candles(o, h, l, c, trend=trend, eq_tol=eq_tol, skip_neutral=False)

    out = []
    for cdl in candles:
        i0 = cdl.confirm_idx
        i1 = i0 - 1
        i2 = i0 - 2
        name = cdl.name

        if name == "doji":
            out.append(Candidate(name, ticker, timeframe, i0, None,
                                  confirm_level={"long": h[i0], "short": l[i0]},
                                  invalidate_level=None, two_sided=True))
            continue
        if name == "spinning_top":
            out.append(Candidate(name, ticker, timeframe, i0, None,
                                  confirm_level={"long": h[i0], "short": l[i0]},
                                  invalidate_level=None, two_sided=True))
            continue
        if name == "marubozu":
            direction = cdl.direction
            out.append(Candidate(name, ticker, timeframe, i0, direction,
                                  confirm_level=c[i0], invalidate_level=o[i0]))
            continue
        if name == "hammer":
            out.append(Candidate(name, ticker, timeframe, i0, "long",
                                  confirm_level=h[i0], invalidate_level=l[i0]))
            continue
        if name == "hanging_man":
            out.append(Candidate(name, ticker, timeframe, i0, "short",
                                  confirm_level=c[i0], invalidate_level=h[i0]))
            continue
        if name == "inverted_hammer":
            out.append(Candidate(name, ticker, timeframe, i0, "long",
                                  confirm_level=h[i0], invalidate_level=l[i0]))
            continue
        if name == "shooting_star":
            out.append(Candidate(name, ticker, timeframe, i0, "short",
                                  confirm_level=l[i0], invalidate_level=h[i0]))
            continue
        if name == "bullish_engulfing":
            out.append(Candidate(name, ticker, timeframe, i0, "long",
                                  confirm_level=c[i0], invalidate_level=l[i0]))
            continue
        if name == "bearish_engulfing":
            out.append(Candidate(name, ticker, timeframe, i0, "short",
                                  confirm_level=c[i0], invalidate_level=h[i0]))
            continue
        if name == "bullish_harami":
            out.append(Candidate(name, ticker, timeframe, i0, "long",
                                  confirm_level=o[i1], invalidate_level=l[i0]))
            continue
        if name == "bearish_harami":
            out.append(Candidate(name, ticker, timeframe, i0, "short",
                                  confirm_level=o[i1], invalidate_level=h[i1]))
            continue
        if name == "piercing":
            out.append(Candidate(name, ticker, timeframe, i0, "long",
                                  confirm_level=c[i0], invalidate_level=l[i0]))
            continue
        if name == "dark_cloud_cover":
            out.append(Candidate(name, ticker, timeframe, i0, "short",
                                  confirm_level=c[i0], invalidate_level=h[i0]))
            continue
        if name == "tweezer_bottom":
            out.append(Candidate(name, ticker, timeframe, i0, "long",
                                  confirm_level=max(h[i0], h[i1]), invalidate_level=min(l[i0], l[i1])))
            continue
        if name == "tweezer_top":
            out.append(Candidate(name, ticker, timeframe, i0, "short",
                                  confirm_level=min(l[i0], l[i1]), invalidate_level=max(h[i0], h[i1])))
            continue
        if name == "morning_star":
            out.append(Candidate(name, ticker, timeframe, i0, "long",
                                  confirm_level=c[i0], invalidate_level=min(l[i2], l[i1], l[i0]),
                                  confirmed_immediately=True))
            continue
        if name == "evening_star":
            out.append(Candidate(name, ticker, timeframe, i0, "short",
                                  confirm_level=c[i0], invalidate_level=max(h[i2], h[i1], h[i0]),
                                  confirmed_immediately=True))
            continue
        if name == "three_white_soldiers":
            mid0 = (o[i0] + c[i0]) / 2.0
            out.append(Candidate(name, ticker, timeframe, i0, "long",
                                  confirm_level=c[i0], invalidate_level=mid0))
            continue
        if name == "three_black_crows":
            mid0 = (o[i0] + c[i0]) / 2.0
            out.append(Candidate(name, ticker, timeframe, i0, "short",
                                  confirm_level=c[i0], invalidate_level=mid0))
            continue
    return out


CANDLESTICK_NAMES_WITH_INVERSION = {
    "marubozu", "bearish_engulfing", "bullish_engulfing",
    "three_black_crows", "three_white_soldiers", "tweezer_bottom", "tweezer_top",
}
