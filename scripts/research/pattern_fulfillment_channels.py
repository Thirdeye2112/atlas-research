"""
pattern_fulfillment_channels.py
==================================
Builds Candidate records for channel_ascending, channel_descending,
channel_horizontal, channel_break.

`detect_channels()` below is copied VERBATIM (not modified) from commit
65c3fbe on branch `feat/channels-and-5m` (pushed to origin, same merge-base
as this branch -- 25accac on fix/model-validity). That branch is not yet
merged into fix/model-validity, and "new files only under scripts/research/
and reports/research/" rules out adding src/atlas_research/ta/channels.py
here -- so the function is reproduced in this permitted location instead of
merging branches. Its own docstring's PIT guard is preserved verbatim:
channel boundary lines are fit using only swing pivots at or before the
detection bar; the break is found by a separate forward scan that never
looks back. See PATTERN_FULFILLMENT_REPORT.md Step 1 for the source-commit
note.

Mechanics, simplified from pattern_reference's text (documented choice):
channel_ascending/descending/horizontal's confirmation_condition describes
THREE possible "confirming" behaviors (bounce-continuation, breakout,
breakdown) -- there is no single mechanical trigger common to all three, so
this measurement uses only the breakout/breakdown case (a clean close
beyond either boundary) as confirmation, and direction is resolved AT that
break (whichever boundary gives first). channel_break is the same
underlying event, pattern_reference's own wording for "the close outside
the channel IS the primary signal" -- so for ALL FOUR types here,
T_recog = the channel's detect_idx, and the eventual break (if any, within
the same forward window) is found directly by detect_channels()'s own
scan. Invalidation per pattern_reference ("price immediately re-enters the
channel within 1-2 bars" / "false break") is checked explicitly as a
post-break override, not via the shared engine's generic Stage A scan --
precomputed here and passed through Candidate.extra["precomputed_stage_a"].
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from atlas_research.ta.structure import swing_pivots
from pattern_fulfillment_common import Candidate


@dataclass
class Channel:
    ctype: str
    start_idx: int
    detect_idx: int
    sup_slope: float
    sup_ic: float
    res_slope: float
    res_ic: float
    touches_sup: int
    touches_res: int
    width_pct: float
    break_idx: int | None = None
    break_dir: str | None = None

    def sup_at(self, x): return self.sup_slope * x + self.sup_ic
    def res_at(self, x): return self.res_slope * x + self.res_ic


def detect_channels(high, low, close, *, width: int = 5, nfit: int = 3,
                    min_bars: int = 10, min_touches: int = 2,
                    parallel_ratio: float = 2.0, slope_thr: float = 0.0008,
                    break_buf: float = 0.0, break_window: int = 120) -> list[Channel]:
    """Verbatim copy of detect_channels from feat/channels-and-5m@65c3fbe."""
    high = np.asarray(high, float); low = np.asarray(low, float); close = np.asarray(close, float)
    n = len(close)
    if n < min_bars + width * 2:
        return []
    piv = swing_pivots(high, low, width)
    highs = [p for p in piv if p.kind == "H"]
    lows = [p for p in piv if p.kind == "L"]
    if len(highs) < min_touches or len(lows) < min_touches:
        return []

    out: list[Channel] = []
    last_key = None

    for p in piv:
        di = p.idx
        rh = [q for q in highs if q.idx <= di][-nfit:]
        rl = [q for q in lows if q.idx <= di][-nfit:]
        if len(rh) < min_touches or len(rl) < min_touches:
            continue
        key = (rh[-1].idx, rl[-1].idx)
        if key == last_key:
            continue
        start_idx = min(rh[0].idx, rl[0].idx)
        if di - start_idx < min_bars:
            continue
        price = close[di]
        if price <= 0:
            continue

        res_slope, res_ic = np.polyfit([q.idx for q in rh], [q.price for q in rh], 1)
        sup_slope, sup_ic = np.polyfit([q.idx for q in rl], [q.price for q in rl], 1)

        w_start = (res_slope * start_idx + res_ic) - (sup_slope * start_idx + sup_ic)
        w_end = (res_slope * di + res_ic) - (sup_slope * di + sup_ic)
        if w_start <= 0 or w_end <= 0:
            continue
        ratio = w_end / w_start
        if ratio > parallel_ratio or ratio < 1.0 / parallel_ratio:
            continue

        avg_slope = (res_slope + sup_slope) / 2.0
        norm = avg_slope / price
        if norm > slope_thr:
            ctype = "ascending"
        elif norm < -slope_thr:
            ctype = "descending"
        else:
            ctype = "horizontal"

        ch = Channel(ctype, start_idx, di, sup_slope, sup_ic, res_slope, res_ic,
                     len(rl), len(rh), float(w_end / price))

        for j in range(di + 1, min(di + 1 + break_window, n)):
            r = res_slope * j + res_ic
            s = sup_slope * j + sup_ic
            if close[j] > r * (1.0 + break_buf):
                ch.break_idx, ch.break_dir = j, "up"; break
            if close[j] < s * (1.0 - break_buf):
                ch.break_idx, ch.break_dir = j, "down"; break

        out.append(ch)
        last_key = key

    return out


def build_channel_candidates(high, low, close, ticker: str, timeframe: str, window: int) -> list[Candidate]:
    close = np.asarray(close, float)
    n = len(close)
    channels = detect_channels(high, low, close, break_window=window)
    out: list[Candidate] = []

    for ch in channels:
        if ch.break_idx is None:
            stage_a = ("NEITHER_A", None, None)
        else:
            # false-break check: does price re-enter the channel within 1-2 bars?
            reentered = False
            t_inval = None
            for k in (1, 2):
                j = ch.break_idx + k
                if j >= n:
                    break
                s_j, r_j = ch.sup_at(j), ch.res_at(j)
                if s_j <= close[j] <= r_j:
                    reentered = True
                    t_inval = j
                    break
            if reentered:
                stage_a = ("INVALIDATED", t_inval, ch.break_dir)
            else:
                stage_a = ("CONFIRMED", ch.break_idx, ch.break_dir)

        for ptype in (f"channel_{ch.ctype}", "channel_break"):
            out.append(Candidate(ptype, ticker, timeframe, ch.detect_idx, None,
                                  confirm_level=None, invalidate_level=None,
                                  extra={"precomputed_stage_a": stage_a,
                                         "channel_type": ch.ctype,
                                         "width_pct": ch.width_pct}))
    return out
