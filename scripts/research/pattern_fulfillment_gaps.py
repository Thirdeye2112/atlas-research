"""
pattern_fulfillment_gaps.py
==============================
Builds Candidate records for classic_gap_up, classic_gap_down (daily) and
fvg_bullish, fvg_bearish (5m). Computed fresh, directly from bars -- NOT
from the live `gaps` table, which is not in this phase's sanctioned
read-only table list and whose builder lives on a separate, uncommitted
branch (feat/gaps). See PATTERN_FULFILLMENT_REPORT.md Step 1.

classic_gap_up/down: a daily-resolution overnight gap. Recognition and
resolution both happen on the SAME bar (the gap day itself) since "holds
at end of session" / "fills within the same session" can only be checked
against that day's own close when working from daily OHLC (no intraday
granularity for the gap day in this daily-only treatment) -- so there is
no NEITHER_A bucket for gaps by construction; every gap day's close is
either still beyond, or has reverted to, the prior close.

fvg_bullish/bearish: the standard 3-bar "fair value gap" imbalance
(bar1.high < bar3.low for bullish, bar1.low > bar3.high for bearish),
recognized when bar3 closes. Confirmation/invalidation require a 2-step
condition per pattern_reference's text ("price enters the zone AND a
[bullish/bearish] reaction") -- implemented as a bespoke forward scan
(Candidate.extra["precomputed_stage_a"]) rather than the shared engine's
generic single-level template, since "must first enter the zone" is a
prerequisite the generic close-beyond-a-level check doesn't express.
"""
from __future__ import annotations

import numpy as np

from pattern_fulfillment_common import Candidate

GAP_THRESHOLD_PCT = 0.002   # 0.2%, filters noise-level opens from real gaps


def build_classic_gap_candidates(open_, high, low, close, ticker: str) -> list[Candidate]:
    open_ = np.asarray(open_, float); close = np.asarray(close, float)
    n = len(close)
    out = []
    for t in range(1, n):
        prior_close = close[t - 1]
        if prior_close <= 0:
            continue
        gap_pct = (open_[t] - prior_close) / prior_close
        if gap_pct > GAP_THRESHOLD_PCT:
            confirmed = close[t] > prior_close
            stage_a = ("CONFIRMED" if confirmed else "INVALIDATED", t, "up")
            out.append(Candidate("classic_gap_up", ticker, "daily", t, "up",
                                  confirm_level=None, invalidate_level=None,
                                  extra={"precomputed_stage_a": stage_a}))
        elif gap_pct < -GAP_THRESHOLD_PCT:
            confirmed = close[t] < prior_close
            stage_a = ("CONFIRMED" if confirmed else "INVALIDATED", t, "down")
            out.append(Candidate("classic_gap_down", ticker, "daily", t, "down",
                                  confirm_level=None, invalidate_level=None,
                                  extra={"precomputed_stage_a": stage_a}))
    return out


def build_fvg_candidates(high, low, close, ticker: str, timeframe: str, window: int) -> list[Candidate]:
    high = np.asarray(high, float); low = np.asarray(low, float); close = np.asarray(close, float)
    n = len(close)
    out = []
    for b3 in range(2, n):
        b1 = b3 - 2
        if low[b3] > high[b1]:   # bullish FVG
            zone_bottom, zone_top = high[b1], low[b3]
            stage_a = _fvg_scan(close, low, high, b3, n, window, zone_bottom, zone_top, "bullish")
            out.append(Candidate("fvg_bullish", ticker, timeframe, b3, "up",
                                  confirm_level=None, invalidate_level=None,
                                  extra={"precomputed_stage_a": stage_a, "zone_top": float(zone_top),
                                         "zone_bottom": float(zone_bottom)}))
        if high[b3] < low[b1]:   # bearish FVG
            zone_top, zone_bottom = low[b1], high[b3]
            stage_a = _fvg_scan(close, low, high, b3, n, window, zone_bottom, zone_top, "bearish")
            out.append(Candidate("fvg_bearish", ticker, timeframe, b3, "down",
                                  confirm_level=None, invalidate_level=None,
                                  extra={"precomputed_stage_a": stage_a, "zone_top": float(zone_top),
                                         "zone_bottom": float(zone_bottom)}))
    return out


def _fvg_scan(close, low, high, b3, n, window, zone_bottom, zone_top, kind):
    lo, hi = b3 + 1, min(n - 1, b3 + window)
    for j in range(lo, hi + 1):
        if kind == "bullish":
            entered = low[j] <= zone_top
            if not entered:
                continue
            if close[j] > zone_bottom:
                return ("CONFIRMED", j, "up")
            if close[j] < zone_bottom:
                return ("INVALIDATED", j, "up")
        else:
            entered = high[j] >= zone_bottom
            if not entered:
                continue
            if close[j] < zone_top:
                return ("CONFIRMED", j, "down")
            if close[j] > zone_top:
                return ("INVALIDATED", j, "down")
    return ("NEITHER_A", None, None)
