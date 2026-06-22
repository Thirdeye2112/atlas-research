"""
foundation_retest_channels.py
================================
detect_channels() reproduced verbatim from commit 65c3fbe on branch
feat/channels-and-5m (pushed to origin, same merge-base as this branch),
already reused and PIT-audited in research/pattern-fulfillment. See that
phase's report for the original provenance note; reproduced again here
rather than imported across worktrees, per this phase's own
new-files-only-under-scripts/research rule.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from atlas_research.ta.structure import swing_pivots


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
