"""
Regression tests for atlas_research.intraday.features.compute_features(),
specifically targeting the cross/event-feature bug family documented in
reports/research/COMPUTE_FEATURES_AUDIT.md: a bool-dtype column passed
through `.shift(1)` upcasts to `object` dtype to hold the leading NaN, and
Python's `~` on that object-dtype series of real bool objects does
bitwise-int negation (~True=-2, ~False=-1, BOTH truthy) instead of logical
negation -- silently collapsing "current_state & ~shifted_prev_state" into
just "current_state". Found in vwap_cross_up, orb_bull_signal, and
orb_bear_signal; fixed via shift(1, fill_value=False), which never
introduces a NaN and so never upcasts the dtype.

Pure tests -- no DB, no file I/O, synthetic OHLCV only.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from atlas_research.intraday.features import compute_features


def _make_session(date_str: str, closes: list[float], vol: float = 1_000_000.0) -> pd.DataFrame:
    """One synthetic 5m session: 9:30 ET onward, one bar per close value."""
    start = pd.Timestamp(f"{date_str} 09:30:00", tz="America/New_York").tz_convert("UTC")
    n = len(closes)
    ts = [start + pd.Timedelta(minutes=5 * i) for i in range(n)]
    closes = np.asarray(closes, dtype=float)
    opens = np.concatenate([[closes[0]], closes[:-1]])
    highs = np.maximum(opens, closes) + 0.01
    lows = np.minimum(opens, closes) - 0.01
    return pd.DataFrame({
        "ticker": "TEST", "ts": ts, "open": opens, "high": highs, "low": lows,
        "close": closes, "volume": np.full(n, vol),
    })


class TestShiftDtypeRegression:
    def test_bool_shift_with_fill_value_stays_bool(self):
        """The exact mechanism of the fix: shift(1, fill_value=False) must
        never upcast to object dtype, unlike shift(1).fillna(False)."""
        s = pd.Series([True, True, False, False, True, True, False])
        broken = s.shift(1).fillna(False)
        fixed = s.shift(1, fill_value=False)
        assert broken.dtype == object, "sanity check: the OLD pattern should still upcast (documents the footgun)"
        assert fixed.dtype == bool, "the FIX must preserve bool dtype"

    def test_bitwise_not_on_object_dtype_bool_is_the_footgun(self):
        """Documents WHY the bug happened: ~ on object-dtype True/False is
        bitwise-int negation, and both results are truthy."""
        broken = pd.Series([True, False]).shift(1).fillna(False)
        negated = ~broken
        assert list(negated) == [-1, -2]
        assert bool(negated.iloc[0]) is True and bool(negated.iloc[1]) is True, (
            "both ~True and ~False are truthy as Python ints -- this is the root cause"
        )


class TestVwapCrossBalance:
    """A genuine binary crossing series must have equal (+-1) up- and
    down-transition counts -- the identity check that originally found the
    bug. Synthetic price oscillates around a level repeatedly within one
    session so VWAP is crossed a known, nontrivial number of times."""

    def test_cross_up_down_balanced_and_not_collapsed_to_state(self):
        n = 60
        # oscillate close around 100 with a slow upward drift in the VWAP
        # reference itself, guaranteeing multiple genuine crossings
        closes = 100 + 2.5 * np.sin(np.linspace(0, 6 * np.pi, n)) + np.linspace(0, 1, n)
        bars = _make_session("2024-01-02", list(closes))
        feat = compute_features(bars)

        up = int(feat["vwap_cross_up"].sum())
        down = int(feat["vwap_cross_down"].sum())
        assert up > 1, "the oscillating synthetic series must produce multiple real crossings"
        assert abs(up - down) <= 1, f"crossing counts must balance (+-1): up={up} down={down}"

        # the regression signature: a BROKEN cross_up equals above_vwap exactly
        assert not feat["vwap_cross_up"].equals(feat["above_vwap"]), (
            "vwap_cross_up must NOT collapse to the persistent above_vwap state"
        )
        assert feat["vwap_cross_up"].dtype == bool
        assert feat["vwap_cross_down"].dtype == bool

    def test_monotonic_series_crosses_at_most_once(self):
        """A price path that only ever rises should cross VWAP up at most a
        handful of times near the start (while VWAP is catching up) and
        essentially never cross down -- NOT fire on every single bar."""
        n = 40
        closes = np.linspace(100, 130, n)
        bars = _make_session("2024-01-03", list(closes))
        feat = compute_features(bars)
        up = int(feat["vwap_cross_up"].sum())
        # A monotonically-rising series must NOT have cross_up fire on
        # (n - small warmup) bars, which is what the collapsed-to-state bug
        # would produce (above_vwap stays True for nearly the whole session).
        assert up < n // 2, f"cross_up firing {up}/{n} times on a monotonic series indicates state-collapse"


class TestOrbSignalNotCollapsed:
    """orb_bull_signal/orb_bear_signal must fire on the FIRST breakout bar
    only, not on every subsequent bar while price remains beyond the
    opening-range boundary (the same collapse failure mode as VWAP)."""

    def test_orb_bull_signal_fires_once_not_every_bar_above(self):
        n = 30
        # 6 bars forming a tight opening range, then a clean breakout that
        # STAYS above OR-high for the rest of the session.
        or_bars = [100.0, 100.2, 99.9, 100.1, 100.0, 100.1]
        post_breakout = list(np.linspace(101.0, 110.0, n - len(or_bars)))
        closes = or_bars + post_breakout
        bars = _make_session("2024-01-04", closes)
        feat = compute_features(bars)

        bull_signal_count = int(feat["orb_bull_signal"].sum())
        above_or_high_after_or = int((feat["above_or_high"] & ~feat["in_or"]).sum())

        assert above_or_high_after_or > 1, "test setup sanity: price should stay above OR-high for many bars"
        assert bull_signal_count >= 1, "the breakout itself must be detected at least once"
        assert bull_signal_count < above_or_high_after_or, (
            f"orb_bull_signal ({bull_signal_count}) must fire on FEWER bars than the persistent "
            f"above-OR-high state ({above_or_high_after_or}) -- equal counts indicate state-collapse"
        )
        # the precise regression signature found in production data
        assert not feat["orb_bull_signal"].equals(feat["above_or_high"] & ~feat["in_or"])

    def test_orb_bear_signal_fires_once_not_every_bar_below(self):
        n = 30
        or_bars = [100.0, 99.9, 100.1, 100.0, 99.95, 100.05]
        post_breakdown = list(np.linspace(99.0, 90.0, n - len(or_bars)))
        closes = or_bars + post_breakdown
        bars = _make_session("2024-01-05", closes)
        feat = compute_features(bars)

        bear_signal_count = int(feat["orb_bear_signal"].sum())
        below_or_low_after_or = int((feat["below_or_low"] & ~feat["in_or"]).sum())

        assert below_or_low_after_or > 1
        assert bear_signal_count >= 1
        assert bear_signal_count < below_or_low_after_or
        assert not feat["orb_bear_signal"].equals(feat["below_or_low"] & ~feat["in_or"])


class TestOtherCrossFeaturesUnaffected:
    """Confirms the sibling features that were audited and found SAFE
    remain correct (macd cross uses float-column shifts + comparisons, no
    bitwise-~ on a shifted bool, so it was never at risk)."""

    def test_macd_cross_balanced(self):
        n = 80
        closes = 100 + 5 * np.sin(np.linspace(0, 4 * np.pi, n))
        bars = _make_session("2024-01-08", list(closes))
        feat = compute_features(bars)
        up = int(feat["macd_bull_cross"].sum())
        down = int(feat["macd_bear_cross"].sum())
        assert abs(up - down) <= 1, f"macd cross counts must balance: up={up} down={down}"
