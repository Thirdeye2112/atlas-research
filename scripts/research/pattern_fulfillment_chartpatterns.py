"""
pattern_fulfillment_chartpatterns.py
=======================================
Builds Candidate records for double_top, double_bottom, hs_top, hs_bottom,
bull_flag, bear_flag -- DAILY ONLY (see PATTERN_FULFILLMENT_REPORT.md
scoping notes: these are inherently multi-week structures; pattern_memory
already has clean confirm_date-level daily granularity, and 5m would
require re-deriving swing-pivot detection at a resolution where these
shapes are structurally less meaningful).

IMPORTANT: this is NOT a call into atlas_research.ta.patterns's own
double_top_bottom / head_and_shoulders / flags functions. Those functions
search forward from the shape's last pivot for the first qualifying close
and SILENTLY DROP any shape that never finds one within their
`confirm_within` window -- i.e. they only ever return already-confirmed
instances, which would make it structurally impossible to count failed/
invalidated/no-follow-through patterns (exactly what this backtest is
required to do honestly). So this module REPLICATES the exact same
shape-recognition conditions (same pivot patterns, same tolerances) from
ta/patterns.py, but emits a Candidate at the RECOGNITION bar (the last
defining pivot) regardless of whether anything happens afterward, and lets
the shared engine's Stage A do the confirm/invalidate/neither accounting.
"""
from __future__ import annotations

import numpy as np

from atlas_research.ta.structure import swing_pivots
from pattern_fulfillment_common import Candidate

EQ_TOL = 0.03
SHOULDER_TOL = 0.06
POLE_MIN = 0.08
POLE_MAX_BARS = 25
MAX_RETRACE = 0.55
PIVOT_WIDTH = 3


def build_chartpattern_candidates(high, low, close, ticker: str, timeframe: str) -> list[Candidate]:
    high = np.asarray(high, float); low = np.asarray(low, float); close = np.asarray(close, float)
    piv = swing_pivots(high, low, width=PIVOT_WIDTH)
    out: list[Candidate] = []

    # ---- double top / bottom (3-pivot: H-L-H or L-H-L) --------------------
    for i in range(len(piv) - 2):
        a, b, c = piv[i:i + 3]
        if min(a.price, b.price, c.price) <= 0:
            continue
        if [a.kind, b.kind, c.kind] == ["H", "L", "H"] and abs(a.price - c.price) / a.price < EQ_TOL:
            neckline = b.price
            top = (a.price + c.price) / 2.0
            out.append(Candidate("double_top", ticker, timeframe, c.idx, "short",
                                  confirm_level=neckline, invalidate_level=top * 1.005,
                                  extra={"points": [(a.idx, a.price), (b.idx, b.price), (c.idx, c.price)]}))
        if [a.kind, b.kind, c.kind] == ["L", "H", "L"] and abs(a.price - c.price) / a.price < EQ_TOL:
            neckline = b.price
            bot = (a.price + c.price) / 2.0
            out.append(Candidate("double_bottom", ticker, timeframe, c.idx, "long",
                                  confirm_level=neckline, invalidate_level=bot * 0.995,
                                  extra={"points": [(a.idx, a.price), (b.idx, b.price), (c.idx, c.price)]}))

    # ---- head & shoulders (5-pivot) ----------------------------------------
    for i in range(len(piv) - 4):
        a, b, c, d, e = piv[i:i + 5]
        if min(a.price, c.price, e.price) <= 0:
            continue
        if [a.kind, b.kind, c.kind, d.kind, e.kind] == ["H", "L", "H", "L", "H"]:
            if (c.price > a.price and c.price > e.price
                    and abs(a.price - e.price) / c.price < SHOULDER_TOL
                    and c.price > max(a.price, e.price) * 1.01):
                neck_sl, neck_ic = np.polyfit([b.idx, d.idx], [b.price, d.price], 1)
                neckline_at_e = neck_sl * e.idx + neck_ic
                out.append(Candidate("hs_top", ticker, timeframe, e.idx, "short",
                                      confirm_level=(lambda j, m=neck_sl, ic=neck_ic: m * j + ic),
                                      invalidate_level=e.price * 1.005,
                                      extra={"points": [(p.idx, p.price) for p in (a, b, c, d, e)],
                                             "neckline_at_recog": float(neckline_at_e)}))
        if [a.kind, b.kind, c.kind, d.kind, e.kind] == ["L", "H", "L", "H", "L"]:
            if (c.price < a.price and c.price < e.price
                    and abs(a.price - e.price) / c.price < SHOULDER_TOL
                    and c.price < min(a.price, e.price) * 0.99):
                neck_sl, neck_ic = np.polyfit([b.idx, d.idx], [b.price, d.price], 1)
                out.append(Candidate("hs_bottom", ticker, timeframe, e.idx, "long",
                                      confirm_level=(lambda j, m=neck_sl, ic=neck_ic: m * j + ic),
                                      invalidate_level=e.price * 0.995,
                                      extra={"points": [(p.idx, p.price) for p in (a, b, c, d, e)]}))

    # ---- flags (3-pivot: L-H-L bull, H-L-H bear) ---------------------------
    for i in range(len(piv) - 2):
        a, b, c = piv[i:i + 3]
        if min(a.price, b.price, c.price) <= 0:
            continue
        if [a.kind, b.kind, c.kind] == ["L", "H", "L"]:
            pole = (b.price - a.price) / a.price
            dur = b.idx - a.idx
            if pole >= POLE_MIN and 0 < dur <= POLE_MAX_BARS:
                retr = (b.price - c.price) / (b.price - a.price) if b.price > a.price else 1
                if 0 < retr <= MAX_RETRACE:
                    out.append(Candidate("bull_flag", ticker, timeframe, c.idx, "long",
                                          confirm_level=b.price, invalidate_level=c.price,
                                          extra={"points": [(a.idx, a.price), (b.idx, b.price), (c.idx, c.price)]}))
        if [a.kind, b.kind, c.kind] == ["H", "L", "H"]:
            pole = (a.price - b.price) / a.price
            dur = b.idx - a.idx
            if pole >= POLE_MIN and 0 < dur <= POLE_MAX_BARS:
                retr = (c.price - b.price) / (a.price - b.price) if a.price > b.price else 1
                if 0 < retr <= MAX_RETRACE:
                    out.append(Candidate("bear_flag", ticker, timeframe, c.idx, "short",
                                          confirm_level=b.price, invalidate_level=c.price,
                                          extra={"points": [(a.idx, a.price), (b.idx, b.price), (c.idx, c.price)]}))

    return sorted(out, key=lambda cd: cd.idx)
