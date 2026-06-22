"""
Correctness/sanity tests for scripts/options_build_oi_structure_features.py.
Pure function tests -- no DB, no API, no file I/O. Synthetic contract data
only.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import options_build_oi_structure_features as oi_features  # noqa: E402


# ---------------------------------------------------------------------------
# Moneyness correctness
# ---------------------------------------------------------------------------

class TestMoneynessDefinitions:
    def test_moneyness_pct(self):
        assert oi_features.moneyness_pct(110, 100) == pytest.approx(0.10)
        assert oi_features.moneyness_pct(90, 100) == pytest.approx(-0.10)
        assert oi_features.moneyness_pct(100, 100) == pytest.approx(0.0)

    def test_moneyness_pct_vectorized(self):
        strikes = pd.Series([90.0, 100.0, 110.0])
        pct = oi_features.moneyness_pct(strikes, 100.0)
        assert list(pct) == pytest.approx([-0.10, 0.0, 0.10])

    @pytest.mark.parametrize("strike,spot,expected", [(110, 100, True), (90, 100, False), (100, 100, False)])
    def test_otm_call(self, strike, spot, expected):
        assert bool(oi_features.is_otm_call(strike, spot)) is expected

    @pytest.mark.parametrize("strike,spot,expected", [(90, 100, True), (110, 100, False), (100, 100, False)])
    def test_itm_call(self, strike, spot, expected):
        assert bool(oi_features.is_itm_call(strike, spot)) is expected

    @pytest.mark.parametrize("strike,spot,expected", [(90, 100, True), (110, 100, False), (100, 100, False)])
    def test_otm_put(self, strike, spot, expected):
        assert bool(oi_features.is_otm_put(strike, spot)) is expected

    @pytest.mark.parametrize("strike,spot,expected", [(110, 100, True), (90, 100, False), (100, 100, False)])
    def test_itm_put(self, strike, spot, expected):
        assert bool(oi_features.is_itm_put(strike, spot)) is expected

    def test_call_and_put_are_inverse_of_each_other(self):
        """A call and a put at the same strike/spot must have opposite
        moneyness -- a call OTM above spot is exactly the put's ITM side."""
        strikes = np.array([80.0, 95.0, 100.0, 105.0, 120.0])
        spot = 100.0
        otm_call = oi_features.is_otm_call(strikes, spot)
        otm_put = oi_features.is_otm_put(strikes, spot)
        itm_call = oi_features.is_itm_call(strikes, spot)
        itm_put = oi_features.is_itm_put(strikes, spot)
        assert list(otm_call) == list(itm_put)
        assert list(otm_put) == list(itm_call)


# ---------------------------------------------------------------------------
# Feature sanity (compute_ticker_features, synthetic snapshots)
# ---------------------------------------------------------------------------

def _make_contracts(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _random_contracts(rng: np.random.Generator, n: int, today: date) -> pd.DataFrame:
    types = rng.choice(["call", "put"], size=n)
    strikes = rng.uniform(50, 200, size=n).round(1)
    # ~30% of rows get no reported open_interest (missing, not zero) --
    # mirrors the real ~60-75% coverage seen against the live account.
    oi = rng.integers(0, 5000, size=n).astype(float)
    oi[rng.random(n) < 0.3] = np.nan
    dte = rng.integers(0, 90, size=n)
    exp = [(today + pd.Timedelta(days=int(d))).isoformat() for d in dte]
    return pd.DataFrame({"type": types, "strike_price": strikes, "open_interest": oi, "expiration_date": exp})


class TestFeatureSanity:
    TODAY = date(2026, 6, 22)

    def test_basic_known_values(self):
        rows = [
            {"type": "call", "strike_price": 100, "open_interest": 50, "expiration_date": "2026-07-01"},
            {"type": "call", "strike_price": 110, "open_interest": 30, "expiration_date": "2026-07-01"},
            {"type": "put", "strike_price": 90, "open_interest": 20, "expiration_date": "2026-07-01"},
            {"type": "put", "strike_price": 80, "open_interest": 10, "expiration_date": "2026-07-15"},
        ]
        df = _make_contracts(rows)
        feat, skipped = oi_features.compute_ticker_features("TEST", df, 100.0, "2026-06-20", self.TODAY)
        assert not skipped
        assert feat["total_call_oi"] == 80
        assert feat["total_put_oi"] == 30
        assert feat["put_call_oi_ratio"] == pytest.approx(30 / 80)

    def test_moneyness_skipped_when_underlying_close_missing(self):
        rows = [{"type": "call", "strike_price": 100, "open_interest": 50, "expiration_date": "2026-07-01"}]
        df = _make_contracts(rows)
        feat, skipped = oi_features.compute_ticker_features("TEST", df, float("nan"), None, self.TODAY)
        assert skipped
        for col in oi_features.MONEYNESS_FEATURES:
            assert pd.isna(feat[col])
        # non-moneyness features must still be computed, not skipped
        assert feat["total_call_oi"] == 50

    @pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
    def test_invariants_hold_on_random_synthetic_snapshots(self, seed):
        rng = np.random.default_rng(seed)
        spot = float(rng.uniform(20, 500))
        df = _random_contracts(rng, n=200, today=self.TODAY)
        feat, _skipped = oi_features.compute_ticker_features("RAND", df, spot, "2026-06-20", self.TODAY)

        # nonnegative totals
        assert feat["total_call_oi"] >= 0
        assert feat["total_put_oi"] >= 0

        # near-money / OTM subsets can never exceed their side's total
        assert feat["near_money_call_oi"] <= feat["total_call_oi"] + 1e-9
        assert feat["near_money_put_oi"] <= feat["total_put_oi"] + 1e-9
        assert feat["otm_call_oi"] <= feat["total_call_oi"] + 1e-9
        assert feat["otm_put_oi"] <= feat["total_put_oi"] + 1e-9
        assert feat["short_dated_call_oi"] <= feat["total_call_oi"] + 1e-9
        assert feat["short_dated_put_oi"] <= feat["total_put_oi"] + 1e-9

        # near-money and "clearly OTM" must not double-count the same OI
        assert feat["near_money_call_oi"] + feat["otm_call_oi"] <= feat["total_call_oi"] + 1e-9
        assert feat["near_money_put_oi"] + feat["otm_put_oi"] <= feat["total_put_oi"] + 1e-9

        # concentration features: in (0, 1] or null, never outside that range
        for col in ("call_oi_concentration_top_strike", "put_oi_concentration_top_strike"):
            val = feat[col]
            assert pd.isna(val) or (0 <= val <= 1), f"{col}={val} out of [0,1] and not null"

        # put_call_oi_ratio is null/NaN iff call OI is zero or missing
        ratio = feat["put_call_oi_ratio"]
        call_oi = feat["total_call_oi"]
        if call_oi is None or pd.isna(call_oi) or call_oi == 0:
            assert pd.isna(ratio)
        else:
            assert not pd.isna(ratio)

    def test_put_call_ratio_null_when_call_oi_zero(self):
        rows = [{"type": "put", "strike_price": 90, "open_interest": 20, "expiration_date": "2026-07-01"}]
        df = _make_contracts(rows)
        feat, _ = oi_features.compute_ticker_features("TEST", df, 100.0, "2026-06-20", self.TODAY)
        assert feat["total_call_oi"] == 0
        assert pd.isna(feat["put_call_oi_ratio"])

    def test_put_call_ratio_real_when_call_oi_positive(self):
        rows = [
            {"type": "call", "strike_price": 100, "open_interest": 5, "expiration_date": "2026-07-01"},
            {"type": "put", "strike_price": 90, "open_interest": 0, "expiration_date": "2026-07-01"},
        ]
        df = _make_contracts(rows)
        feat, _ = oi_features.compute_ticker_features("TEST", df, 100.0, "2026-06-20", self.TODAY)
        assert not pd.isna(feat["put_call_oi_ratio"])
        assert feat["put_call_oi_ratio"] == pytest.approx(0.0)
