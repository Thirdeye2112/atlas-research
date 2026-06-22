"""
foundation_retest_triggers.py
================================
Builds the 8 tool families (16 directional trigger_types) as a uniform list
of Trigger records. Every trigger's docstring states the EXACT bar at which
it becomes causally knowable, per the gaps.py-derived checklist (see
foundation_retest_common.py's module docstring).

Reuses, without modification, compute_features()'s already PIT-verified
columns (RSI/MACD/EMA/VWAP/volume) for 4 of the 8 families. The other 4
(channel break, swing pivot, FVG fill, volume-spike+direction) are built
fresh here, each with an explicit causal-timing note.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from atlas_research.ta.structure import swing_pivots, Pivot

PIVOT_WIDTH = 3
AMP_MULT = 2.5
VOL_SPIKE_RATIO = 1.5


@dataclass
class Trigger:
    trigger_type: str
    decision_idx: int     # the bar at which the trigger fires AND is causally knowable
    direction: str         # 'long' | 'short'


# ---------------------------------------------------------------------------
# 1. RSI reclaim -- already an instantaneous PIT event in compute_features
#    (rsi14>=40 & rsi_prev<35 for bull, rsi14<=60 & rsi_prev>65 for bear).
#    Knowable: at the bar's own close (decision_idx = that bar).
# ---------------------------------------------------------------------------

def build_rsi_triggers(feat_df: pd.DataFrame) -> list[Trigger]:
    bull = feat_df["rsi_reclaim_bull"].fillna(False).to_numpy()
    bear = feat_df["rsi_reclaim_bear"].fillna(False).to_numpy()
    out = [Trigger("rsi_reclaim_bull", int(i), "long") for i in np.where(bull)[0]]
    out += [Trigger("rsi_reclaim_bear", int(i), "short") for i in np.where(bear)[0]]
    return out


# ---------------------------------------------------------------------------
# 2. MACD cross -- instantaneous PIT event (macd_bull_cross/macd_bear_cross).
#    Knowable: at the bar's own close.
# ---------------------------------------------------------------------------

def build_macd_triggers(feat_df: pd.DataFrame) -> list[Trigger]:
    bull = feat_df["macd_bull_cross"].fillna(False).to_numpy()
    bear = feat_df["macd_bear_cross"].fillna(False).to_numpy()
    out = [Trigger("macd_bull_cross", int(i), "long") for i in np.where(bull)[0]]
    out += [Trigger("macd_bear_cross", int(i), "short") for i in np.where(bear)[0]]
    return out


# ---------------------------------------------------------------------------
# 3. Price crossing EMA9 -- derived from compute_features' price_above_ema9
#    (already PIT) via a same-bar diff against the prior bar's value. The
#    diff itself introduces no look-ahead: comparing state[T] to state[T-1]
#    only uses information already known at T.
#    Knowable: at the bar's own close.
# ---------------------------------------------------------------------------

def build_ema_cross_triggers(feat_df: pd.DataFrame) -> list[Trigger]:
    above = feat_df["price_above_ema9"].fillna(False).to_numpy()
    prev = np.concatenate([[False], above[:-1]])
    cross_up = above & ~prev
    cross_down = ~above & prev
    out = [Trigger("ema9_cross_up", int(i), "long") for i in np.where(cross_up)[0]]
    out += [Trigger("ema9_cross_down", int(i), "short") for i in np.where(cross_down)[0]]
    return out


# ---------------------------------------------------------------------------
# 4. VWAP reclaim/loss.
#    DATA-INTEGRITY FINDING (Step 0): compute_features()'s own `vwap_cross_up`
#    column is BUGGED -- `above_vwap.shift(1)` upcasts a bool Series to
#    `object` dtype to hold the leading NaN; `~` applied to that object-dtype
#    series triggers Python's bitwise-int semantics (~True=-2, ~False=-1,
#    BOTH truthy), so `above_vwap & ~above_vwap_prev` collapses to just
#    `above_vwap` -- i.e. `vwap_cross_up` silently equals `above_vwap` itself
#    (34,954 of 67,241 AAPL bars), not a real crossing event. Verified by an
#    independent manual transition count (True->False vs False->True must be
#    equal +-1 for any binary sequence; the stored column violates this
#    10-to-1). `vwap_cross_down` is NOT affected -- it negates the proper
#    bool-dtype `above_vwap` column directly, not the shifted/upcast one.
#    This bug is upstream, shared production code (affects every phase of
#    this research arc that used `vwap_cross_up`, including setup-formation
#    v2 and pattern-fulfillment's "vwap" trigger) -- not modified here (this
#    branch is read-only on existing code); instead, recomputed safely below
#    using the same numpy-array shift pattern already used for the EMA cross
#    above, which never goes through pandas' object-dtype shift path.
#    Knowable: at the bar's own close.
# ---------------------------------------------------------------------------

def build_vwap_triggers(feat_df: pd.DataFrame) -> list[Trigger]:
    above = feat_df["above_vwap"].fillna(False).to_numpy()
    prev = np.concatenate([[False], above[:-1]])
    cross_up = above & ~prev
    cross_down = ~above & prev
    out = [Trigger("vwap_reclaim", int(i), "long") for i in np.where(cross_up)[0]]
    out += [Trigger("vwap_loss", int(i), "short") for i in np.where(cross_down)[0]]
    return out


# ---------------------------------------------------------------------------
# 5. Channel boundary break -- detect_channels() (reproduced verbatim from
#    feat/channels-and-5m commit 65c3fbe, already PIT-audited in the
#    pattern-fulfillment phase): the channel is fit from PAST pivots only;
#    the break is the first close beyond a boundary in a forward scan from
#    the fit bar. Knowable: at break_idx itself (the bar whose CLOSE first
#    breaches the boundary) -- no separate "early window" is measured here,
#    so this trigger does NOT have the dome-leg-style accounting-overlap
#    risk (it is a single instantaneous event, not a sub-segment of a
#    longer measured path).
# ---------------------------------------------------------------------------

def build_channel_break_triggers(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> list[Trigger]:
    from foundation_retest_channels import detect_channels
    channels = detect_channels(high, low, close, break_window=120)
    out = []
    for ch in channels:
        if ch.break_idx is None:
            continue
        direction = "long" if ch.break_dir == "up" else "short"
        out.append(Trigger(f"channel_break_{ch.break_dir}", int(ch.break_idx), direction))
    return out


# ---------------------------------------------------------------------------
# 6. Swing pivot confirmed -- THE dome-leg-verify FIX, applied here from the
#    start. swing_pivots(width=3): a bar P is a swing low/high only if it is
#    the strict extreme over [P-3, P+3] -- this REQUIRES 3 bars after P, so
#    P itself is NOT knowable until bar P+3. decision_idx = P + PIVOT_WIDTH
#    (the confirmation bar), NEVER P. Entry price is close[P+width] (what
#    you could actually transact at), not the pivot's own extreme price
#    (which has already passed by the time you know about it).
#    Only "significant" pivots (move from the prior opposite pivot >=
#    AMP_MULT x ATR14) are used, to exclude noise-level zigzags -- same
#    convention as research/dome-leg-signature.
# ---------------------------------------------------------------------------

def build_swing_pivot_triggers(high: np.ndarray, low: np.ndarray, atr: np.ndarray, n: int) -> list[Trigger]:
    piv = swing_pivots(high, low, width=PIVOT_WIDTH)
    out = []
    last_opp_price = None
    for p in piv:
        is_significant = False
        if last_opp_price is not None and not np.isnan(atr[p.idx]) and atr[p.idx] > 0:
            if abs(p.price - last_opp_price) >= AMP_MULT * atr[p.idx]:
                is_significant = True
        last_opp_price = p.price
        if not is_significant:
            continue
        conf_idx = p.idx + PIVOT_WIDTH
        if conf_idx >= n:
            continue
        direction = "long" if p.kind == "L" else "short"
        trigger_type = "swing_pivot_low_confirmed" if p.kind == "L" else "swing_pivot_high_confirmed"
        out.append(Trigger(trigger_type, int(conf_idx), direction))
    return out


# ---------------------------------------------------------------------------
# 7. FVG fill -- 3-bar imbalance (compute_fvgs's exact definition, reproduced
#    from ta/gaps.py on branch feat/gaps -- NOT the live `gaps` table, to
#    avoid depending on a table whose backfill state for this exact date
#    range wasn't independently confirmed here). Bullish FVG: C1.high <
#    C3.low, zone=[C1.high, C3.low], known at C3's CLOSE (per gaps.py's own
#    explicit "Look-ahead: CRITICAL... confirmed at C3's CLOSE" note).
#    "Fill" = the first bar AFTER the zone is known where price re-enters it
#    (low[T] <= zone_top for a bullish zone). decision_idx = that fill bar,
#    necessarily >= C3's index, so never before the zone exists.
# ---------------------------------------------------------------------------

def build_fvg_fill_triggers(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int = 96) -> list[Trigger]:
    n = len(close)
    out = []
    for c3 in range(2, n):
        c1 = c3 - 2
        if low[c3] > high[c1]:   # bullish FVG, known at c3's close
            zone_bottom, zone_top = high[c1], low[c3]
            for j in range(c3 + 1, min(n, c3 + 1 + window)):
                if low[j] <= zone_top:
                    out.append(Trigger("fvg_fill_bullish", int(j), "long"))
                    break
        if high[c3] < low[c1]:   # bearish FVG, known at c3's close
            zone_top, zone_bottom = low[c1], high[c3]
            for j in range(c3 + 1, min(n, c3 + 1 + window)):
                if high[j] >= zone_bottom:
                    out.append(Trigger("fvg_fill_bearish", int(j), "short"))
                    break
    return out


# ---------------------------------------------------------------------------
# 8. Volume spike + concurrent candle direction -- vol_ratio (PIT, already
#    in compute_features) newly crossing above VOL_SPIKE_RATIO, paired with
#    that SAME bar's own color (also already known at its close).
#    Knowable: at the bar's own close.
# ---------------------------------------------------------------------------

def build_volume_spike_triggers(feat_df: pd.DataFrame) -> list[Trigger]:
    vol_ratio = feat_df["vol_ratio"].to_numpy()
    is_high_vol = vol_ratio > VOL_SPIKE_RATIO
    prev = np.concatenate([[False], is_high_vol[:-1]])
    newly_spiked = is_high_vol & ~prev
    is_green = feat_df["is_green"].to_numpy()
    is_red = feat_df["is_red"].to_numpy()
    out = [Trigger("volume_spike_green", int(i), "long") for i in np.where(newly_spiked & is_green)[0]]
    out += [Trigger("volume_spike_red", int(i), "short") for i in np.where(newly_spiked & is_red)[0]]
    return out


def build_all_triggers(feat_df: pd.DataFrame, atr: np.ndarray) -> list[Trigger]:
    h = feat_df["high"].to_numpy(float); l = feat_df["low"].to_numpy(float); c = feat_df["close"].to_numpy(float)
    n = len(c)
    out = []
    out += build_rsi_triggers(feat_df)
    out += build_macd_triggers(feat_df)
    out += build_ema_cross_triggers(feat_df)
    out += build_vwap_triggers(feat_df)
    out += build_channel_break_triggers(h, l, c)
    out += build_swing_pivot_triggers(h, l, atr, n)
    out += build_fvg_fill_triggers(h, l, c)
    out += build_volume_spike_triggers(feat_df)
    return sorted(out, key=lambda t: t.decision_idx)
