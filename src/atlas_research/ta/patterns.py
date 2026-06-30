"""
patterns.py — classic chart-pattern recognition built on the structure layer.

Each detector reads the swing-pivot sequence (from structure.swing_pivots) plus
the price arrays and returns confirmed pattern instances. "Confirmed" means the
breakout/neckline event has happened on a CLOSE — so confirm_idx is a real,
no-lookahead entry-timing bar. Each instance carries entry / stop / target
(measured move) so it can be backtested and drawn.

Patterns implemented:
  bull_flag, bear_flag          — pole + tight consolidation + breakout
  hs_top, hs_bottom (inverse)   — head & shoulders / inverse
  double_top, double_bottom

Tolerances are parameters; defaults are sane for daily bars.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
from .structure import Pivot


@dataclass
class Pattern:
    name: str
    direction: str               # 'long' | 'short'
    confirm_idx: int             # bar where the pattern confirmed (entry timing)
    entry: float
    stop: float
    target: float
    points: list = field(default_factory=list)   # [(idx, price), ...] key points
    neckline: float | None = None

    @property
    def rr(self) -> float:
        risk = abs(self.entry - self.stop)
        return abs(self.target - self.entry) / risk if risk > 0 else float("nan")


def _first_close_below(close, start, level_fn, limit):
    for j in range(start, min(start + limit, len(close))):
        if close[j] < level_fn(j):
            return j
    return None


def _first_close_above(close, start, level_fn, limit):
    for j in range(start, min(start + limit, len(close))):
        if close[j] > level_fn(j):
            return j
    return None


# ---------------------------------------------------------------- H&S -------
def head_and_shoulders(piv: list[Pivot], high, low, close,
                       shoulder_tol=0.06, confirm_within=40) -> list[Pattern]:
    out = []
    for i in range(len(piv) - 4):
        a, b, c, d, e = piv[i:i+5]
        if min(a.price, c.price, e.price) <= 0:   # bad-data guard (zero price)
            continue
        # top: H L H L H, head highest, shoulders ~equal
        if [a.kind,b.kind,c.kind,d.kind,e.kind] == ['H','L','H','L','H']:
            if c.price > a.price and c.price > e.price and \
               abs(a.price - e.price)/c.price < shoulder_tol and \
               c.price > max(a.price, e.price) * 1.01:
                neck_sl, neck_ic = np.polyfit([b.idx, d.idx], [b.price, d.price], 1)
                lvl = lambda j: neck_sl*j + neck_ic
                cj = _first_close_below(close, e.idx+1, lvl, confirm_within)
                if cj is not None:
                    entry = float(close[cj]); neck = float(lvl(cj))
                    target = neck - (c.price - neck)
                    out.append(Pattern("hs_top","short",cj,entry,float(e.price*1.005),
                                       float(target),[(a.idx,a.price),(b.idx,b.price),
                                       (c.idx,c.price),(d.idx,d.price),(e.idx,e.price)],neck))
        # bottom (inverse): L H L H L, head lowest
        if [a.kind,b.kind,c.kind,d.kind,e.kind] == ['L','H','L','H','L']:
            if c.price < a.price and c.price < e.price and \
               abs(a.price - e.price)/c.price < shoulder_tol and \
               c.price < min(a.price, e.price) * 0.99:
                neck_sl, neck_ic = np.polyfit([b.idx, d.idx], [b.price, d.price], 1)
                lvl = lambda j: neck_sl*j + neck_ic
                cj = _first_close_above(close, e.idx+1, lvl, confirm_within)
                if cj is not None:
                    entry = float(close[cj]); neck = float(lvl(cj))
                    target = neck + (neck - c.price)
                    out.append(Pattern("hs_bottom","long",cj,entry,float(e.price*0.995),
                                       float(target),[(a.idx,a.price),(b.idx,b.price),
                                       (c.idx,c.price),(d.idx,d.price),(e.idx,e.price)],neck))
    return out


# ------------------------------------------------------- double top/bottom --
def double_top_bottom(piv: list[Pivot], high, low, close,
                      eq_tol=0.03, confirm_within=40) -> list[Pattern]:
    out = []
    for i in range(len(piv) - 2):
        a, b, c = piv[i:i+3]
        if min(a.price, b.price, c.price) <= 0:    # bad-data guard
            continue
        if [a.kind,b.kind,c.kind] == ['H','L','H'] and abs(a.price-c.price)/a.price < eq_tol:
            lvl = lambda j: b.price
            cj = _first_close_below(close, c.idx+1, lvl, confirm_within)
            if cj is not None:
                entry = float(close[cj]); top = (a.price+c.price)/2
                target = b.price - (top - b.price)
                out.append(Pattern("double_top","short",cj,entry,float(top*1.005),
                                   float(target),[(a.idx,a.price),(b.idx,b.price),(c.idx,c.price)],float(b.price)))
        if [a.kind,b.kind,c.kind] == ['L','H','L'] and abs(a.price-c.price)/a.price < eq_tol:
            lvl = lambda j: b.price
            cj = _first_close_above(close, c.idx+1, lvl, confirm_within)
            if cj is not None:
                entry = float(close[cj]); bot = (a.price+c.price)/2
                target = b.price + (b.price - bot)
                out.append(Pattern("double_bottom","long",cj,entry,float(bot*0.995),
                                   float(target),[(a.idx,a.price),(b.idx,b.price),(c.idx,c.price)],float(b.price)))
    return out


# -------------------------------------------------------------- flags -------
def flags(piv: list[Pivot], high, low, close,
          pole_min=0.08, pole_max_bars=25, max_retrace=0.55, confirm_within=20) -> list[Pattern]:
    out = []
    for i in range(len(piv) - 2):
        a, b, c = piv[i:i+3]
        if min(a.price, b.price, c.price) <= 0:    # bad-data guard
            continue
        # bull flag: low(a) -> high(b) pole, pullback to low(c), breakout above b
        if [a.kind,b.kind,c.kind] == ['L','H','L']:
            pole = (b.price - a.price)/a.price
            dur = b.idx - a.idx
            if pole >= pole_min and 0 < dur <= pole_max_bars:
                retr = (b.price - c.price)/(b.price - a.price) if b.price>a.price else 1
                if 0 < retr <= max_retrace:
                    lvl = lambda j: b.price
                    cj = _first_close_above(close, c.idx+1, lvl, confirm_within)
                    if cj is not None:
                        entry=float(close[cj]); target=entry + (b.price - a.price)
                        out.append(Pattern("bull_flag","long",cj,entry,float(c.price),
                                           float(target),[(a.idx,a.price),(b.idx,b.price),(c.idx,c.price)]))
        # bear flag: high(a) -> low(b) pole, bounce to high(c), breakdown below b
        if [a.kind,b.kind,c.kind] == ['H','L','H']:
            pole = (a.price - b.price)/a.price
            dur = b.idx - a.idx
            if pole >= pole_min and 0 < dur <= pole_max_bars:
                retr = (c.price - b.price)/(a.price - b.price) if a.price>b.price else 1
                if 0 < retr <= max_retrace:
                    lvl = lambda j: b.price
                    cj = _first_close_below(close, c.idx+1, lvl, confirm_within)
                    if cj is not None:
                        entry=float(close[cj]); target=entry - (a.price - b.price)
                        out.append(Pattern("bear_flag","short",cj,entry,float(c.price),
                                           float(target),[(a.idx,a.price),(b.idx,b.price),(c.idx,c.price)]))
    return out


def swing_legs(piv: list[Pivot], high, low, close, min_amp=0.05, early_n=5) -> list[dict]:
    """
    The 'dome/hump' macro shape: a rise from a swing LOW to the next swing HIGH
    (the up-leg), then the correction down to the following swing LOW.
    Returns one dict per up-leg with the EARLY SIGNATURE (first `early_n` bars off
    the low) and the eventual leg amplitude/duration + correction depth/duration —
    so we can later study whether the early bars predict how high & how deep.
    """
    out = []
    for i in range(len(piv) - 1):
        a, b = piv[i], piv[i+1]
        if not (a.kind == 'L' and b.kind == 'H' and a.price > 0):
            continue
        leg_amp = (b.price - a.price) / a.price
        if leg_amp < min_amp:
            continue
        leg_bars = b.idx - a.idx
        # correction to the next swing low (if any)
        c = piv[i+2] if i+2 < len(piv) and piv[i+2].kind == 'L' else None
        corr_depth = (b.price - c.price) / b.price if c else None
        corr_bars = (c.idx - b.idx) if c else None
        # early signature: first early_n bars off the low (capped at the peak)
        e_end = min(a.idx + early_n, b.idx, len(close) - 1)
        early_gain = (close[e_end] - a.price) / a.price if a.price > 0 else None
        early_bars = e_end - a.idx
        early_slope = (early_gain / early_bars) if early_bars else None
        out.append(dict(
            start_idx=a.idx, peak_idx=b.idx, corr_idx=(c.idx if c else None),
            leg_amp=float(leg_amp), leg_bars=int(leg_bars),
            corr_depth=(float(corr_depth) if corr_depth is not None else None),
            corr_bars=(int(corr_bars) if corr_bars is not None else None),
            early_n=int(early_bars), early_gain=(float(early_gain) if early_gain is not None else None),
            early_slope=(float(early_slope) if early_slope is not None else None),
        ))
    return out


# -------------------------------------------------------------- wedges ------
def wedges(piv: list[Pivot], high, low, close,
           converge=0.7, confirm_within=30) -> list[Pattern]:
    """Rising wedge (bearish) / falling wedge (bullish): two CONVERGING trendlines.
    Rising wedge = highs & lows both slope UP but the lows rise faster, so the lines
    pinch upward and price tends to break DOWN. Falling wedge is the mirror (breaks UP).
    Target = measured move = the wedge's widest height projected from the breakout."""
    out = []
    for i in range(len(piv) - 4):
        w = piv[i:i+5]
        if min(p.price for p in w) <= 0:
            continue
        highs = [(p.idx, p.price) for p in w if p.kind == 'H']
        lows  = [(p.idx, p.price) for p in w if p.kind == 'L']
        if len(highs) < 2 or len(lows) < 2:
            continue
        hi_sl, hi_ic = np.polyfit([x for x, _ in highs], [y for _, y in highs], 1)
        lo_sl, lo_ic = np.polyfit([x for x, _ in lows],  [y for _, y in lows],  1)
        hline = lambda j: hi_sl*j + hi_ic
        lline = lambda j: lo_sl*j + lo_ic
        i0, i1 = w[0].idx, w[-1].idx
        w0, w1 = hline(i0) - lline(i0), hline(i1) - lline(i1)
        if w0 <= 0 or w1 <= 0 or w1 >= w0 * converge:    # must converge to <converge of start
            continue
        height = float(w0); last = w[-1].idx
        pts = [(p.idx, p.price) for p in w]
        # rising wedge (bearish): both lines up, lows steeper -> break DOWN
        if hi_sl > 0 and lo_sl > 0 and lo_sl > hi_sl:
            cj = _first_close_below(close, last+1, lline, confirm_within)
            if cj is not None:
                entry = float(close[cj])
                out.append(Pattern("rising_wedge", "short", cj, entry,
                                   float(hline(cj)), entry - height, pts, float(lline(cj))))
        # falling wedge (bullish): both lines down, highs steeper -> break UP
        if hi_sl < 0 and lo_sl < 0 and hi_sl < lo_sl:
            cj = _first_close_above(close, last+1, hline, confirm_within)
            if cj is not None:
                entry = float(close[cj])
                out.append(Pattern("falling_wedge", "long", cj, entry,
                                   float(lline(cj)), entry + height, pts, float(hline(cj))))
    return out


def _two_lines(w: list[Pivot]):
    """Fit the upper (highs) and lower (lows) trendlines through a pivot window.
    Returns (hi_slope, hi_intercept, lo_slope, lo_intercept) or None."""
    highs = [(p.idx, p.price) for p in w if p.kind == 'H']
    lows  = [(p.idx, p.price) for p in w if p.kind == 'L']
    if len(highs) < 2 or len(lows) < 2:
        return None
    hi = np.polyfit([x for x, _ in highs], [y for _, y in highs], 1)
    lo = np.polyfit([x for x, _ in lows],  [y for _, y in lows],  1)
    return float(hi[0]), float(hi[1]), float(lo[0]), float(lo[1])


# ----------------------------------------------- triangles / range / megaphone
def triangles_ranges(piv: list[Pivot], high, low, close,
                     converge=0.7, confirm_within=30) -> list[Pattern]:
    """Two-line geometry on a 5-pivot window: ascending / descending / symmetric
    triangle, rectangle (range), and broadening (megaphone). Wedges are handled
    separately (both lines same-sign). Target = measured move (widest height)."""
    out = []
    for i in range(len(piv) - 4):
        w = piv[i:i+5]
        if min(p.price for p in w) <= 0:
            continue
        ln = _two_lines(w)
        if ln is None:
            continue
        hi_sl, hi_ic, lo_sl, lo_ic = ln
        hline = lambda j: hi_sl*j + hi_ic
        lline = lambda j: lo_sl*j + lo_ic
        i0, i1 = w[0].idx, w[-1].idx
        w0, w1 = hline(i0) - lline(i0), hline(i1) - lline(i1)
        if w0 <= 0:
            continue
        FLAT = 0.20 * w0
        hi_chg, lo_chg = hline(i1) - hline(i0), lline(i1) - lline(i0)
        hi_flat, lo_flat = abs(hi_chg) < FLAT, abs(lo_chg) < FLAT
        conv = w1 < w0 * converge
        parallel = w0 * converge <= w1 <= w0 * 1.3
        div = w1 > w0 * 1.3
        height = float(max(w0, w1)); last = w[-1].idx
        pts = [(p.idx, p.price) for p in w]

        def emit_up(name, dir_, line_lvl, stop_lvl, sign):
            cj = (_first_close_above if sign > 0 else _first_close_below)(close, last+1, line_lvl, confirm_within)
            if cj is not None:
                e = float(close[cj])
                out.append(Pattern(name, dir_, cj, e, float(stop_lvl(cj)), e + sign*height, pts, float(line_lvl(cj))))
                return cj
            return None

        if hi_flat and lo_chg >= FLAT and conv:            # ascending triangle -> up
            emit_up("ascending_triangle", "long", hline, lline, +1)
        if lo_flat and hi_chg <= -FLAT and conv:           # descending triangle -> down
            emit_up("descending_triangle", "short", lline, hline, -1)
        if hi_chg <= -FLAT and lo_chg >= FLAT and conv:    # symmetric -> first break wins
            up = _first_close_above(close, last+1, hline, confirm_within)
            dn = _first_close_below(close, last+1, lline, confirm_within)
            if up is not None and (dn is None or up <= dn):
                e = float(close[up]); out.append(Pattern("symmetric_triangle","long",up,e,float(lline(up)),e+height,pts))
            elif dn is not None:
                e = float(close[dn]); out.append(Pattern("symmetric_triangle","short",dn,e,float(hline(dn)),e-height,pts))
        if hi_flat and lo_flat and parallel:               # rectangle / range
            up = _first_close_above(close, last+1, hline, confirm_within)
            dn = _first_close_below(close, last+1, lline, confirm_within)
            if up is not None and (dn is None or up <= dn):
                e = float(close[up]); out.append(Pattern("rectangle","long",up,e,float(lline(up)),e+height,pts))
            elif dn is not None:
                e = float(close[dn]); out.append(Pattern("rectangle","short",dn,e,float(hline(dn)),e-height,pts))
        if div and hi_chg >= FLAT and lo_chg <= -FLAT:     # broadening / megaphone
            dn = _first_close_below(close, last+1, lline, confirm_within)
            up = _first_close_above(close, last+1, hline, confirm_within)
            if dn is not None and (up is None or dn <= up):
                e = float(close[dn]); out.append(Pattern("broadening","short",dn,e,float(hline(dn)),e-height,pts))
            elif up is not None:
                e = float(close[up]); out.append(Pattern("broadening","long",up,e,float(lline(up)),e+height,pts))
    return out


# ----------------------------------------------------------- parallel channels
def channels(piv: list[Pivot], high, low, close, confirm_within=20) -> list[Pattern]:
    """Ascending/descending parallel channel; the tradeable signal is the BREAK of
    the channel (ascending channel breakdown = short, descending breakout = long)."""
    out = []
    for i in range(len(piv) - 4):
        w = piv[i:i+5]
        if min(p.price for p in w) <= 0:
            continue
        ln = _two_lines(w)
        if ln is None:
            continue
        hi_sl, hi_ic, lo_sl, lo_ic = ln
        hline = lambda j: hi_sl*j + hi_ic
        lline = lambda j: lo_sl*j + lo_ic
        i0, i1 = w[0].idx, w[-1].idx
        w0, w1 = hline(i0) - lline(i0), hline(i1) - lline(i1)
        if w0 <= 0 or not (0.7*w0 < w1 < 1.3*w0):       # must stay ~parallel
            continue
        avg = (hline(i0) + lline(i0)) / 2
        if abs(hi_sl * (i1-i0) / avg) < 0.02:           # too flat -> that's a rectangle
            continue
        height = float((w0 + w1) / 2); last = w[-1].idx
        pts = [(p.idx, p.price) for p in w]
        if hi_sl > 0 and lo_sl > 0:                     # ascending channel -> breakdown short
            cj = _first_close_below(close, last+1, lline, confirm_within)
            if cj is not None:
                e = float(close[cj]); out.append(Pattern("ascending_channel_break","short",cj,e,float(hline(cj)),e-height,pts,float(lline(cj))))
        if hi_sl < 0 and lo_sl < 0:                     # descending channel -> breakout long
            cj = _first_close_above(close, last+1, hline, confirm_within)
            if cj is not None:
                e = float(close[cj]); out.append(Pattern("descending_channel_break","long",cj,e,float(lline(cj)),e+height,pts,float(hline(cj))))
    return out


# ------------------------------------------------------------ triple top/bottom
def triple_top_bottom(piv: list[Pivot], high, low, close,
                      tol=0.03, confirm_within=30) -> list[Pattern]:
    """Three ~equal highs (top, bearish) / lows (bottom, bullish). Distinct from H&S
    (no higher head) and double (three touches). Target = neckline -/+ height."""
    out = []
    for i in range(len(piv) - 4):
        a, b, c, d, e = piv[i:i+5]
        if min(a.price, b.price, c.price, d.price, e.price) <= 0:
            continue
        ks = [a.kind, b.kind, c.kind, d.kind, e.kind]
        if ks == ['H', 'L', 'H', 'L', 'H']:
            hs = [a.price, c.price, e.price]
            if (max(hs) - min(hs)) / np.mean(hs) < tol:
                neck = min(b.price, d.price); height = float(np.mean(hs) - neck)
                cj = _first_close_below(close, e.idx+1, lambda j: neck, confirm_within)
                if cj is not None:
                    en = float(close[cj])
                    out.append(Pattern("triple_top","short",cj,en,float(max(hs)*1.005),en-height,
                                       [(p.idx,p.price) for p in (a,b,c,d,e)], float(neck)))
        if ks == ['L', 'H', 'L', 'H', 'L']:
            ls = [a.price, c.price, e.price]
            if (max(ls) - min(ls)) / np.mean(ls) < tol:
                neck = max(b.price, d.price); height = float(neck - np.mean(ls))
                cj = _first_close_above(close, e.idx+1, lambda j: neck, confirm_within)
                if cj is not None:
                    en = float(close[cj])
                    out.append(Pattern("triple_bottom","long",cj,en,float(min(ls)*0.995),en+height,
                                       [(p.idx,p.price) for p in (a,b,c,d,e)], float(neck)))
    return out


# -------------------------------------------------------------------- pennants
def pennants(piv: list[Pivot], high, low, close,
             pole_min=0.04, confirm_within=20) -> list[Pattern]:
    """Pole (sharp move) + small CONVERGING consolidation + breakout in the pole's
    direction (the converging cousin of the flag). Target = the pole height."""
    out = []
    for i in range(1, len(piv) - 3):
        pa, pb = piv[i-1], piv[i]
        w = piv[i:i+4]
        if min(p.price for p in [pa, pb] + list(w)) <= 0:
            continue
        pole = (pb.price - pa.price) / pa.price
        ln = _two_lines(w)
        if ln is None:
            continue
        hi_sl, hi_ic, lo_sl, lo_ic = ln
        hline = lambda j: hi_sl*j + hi_ic
        lline = lambda j: lo_sl*j + lo_ic
        i0, i1 = w[0].idx, w[-1].idx
        w0, w1 = hline(i0) - lline(i0), hline(i1) - lline(i1)
        if w0 <= 0 or w1 >= w0 * 0.8 or not (hi_sl < 0 and lo_sl > 0):   # converging
            continue
        last = w[-1].idx; height = abs(pb.price - pa.price)
        pts = [(pa.idx, pa.price)] + [(p.idx, p.price) for p in w]
        if pole >= pole_min:
            cj = _first_close_above(close, last+1, hline, confirm_within)
            if cj is not None:
                e = float(close[cj]); out.append(Pattern("bull_pennant","long",cj,e,float(lline(cj)),e+height,pts))
        elif pole <= -pole_min:
            cj = _first_close_below(close, last+1, lline, confirm_within)
            if cj is not None:
                e = float(close[cj]); out.append(Pattern("bear_pennant","short",cj,e,float(hline(cj)),e-height,pts))
    return out


def detect_all(piv: list[Pivot], high, low, close) -> list[Pattern]:
    pats = []
    pats += head_and_shoulders(piv, high, low, close)
    pats += double_top_bottom(piv, high, low, close)
    pats += flags(piv, high, low, close)
    pats += wedges(piv, high, low, close)
    pats += triangles_ranges(piv, high, low, close)
    pats += channels(piv, high, low, close)
    pats += triple_top_bottom(piv, high, low, close)
    pats += pennants(piv, high, low, close)
    return sorted(pats, key=lambda p: p.confirm_idx)
