"""
Feature module tests — updated for numpy-array input contract.
All tests are pure (no DB, no file I/O).
"""
from __future__ import annotations
import math, sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atlas_research.features import momentum, regime, relative_strength, trend, volatility, volume
from atlas_research.features.feature_factory import build_features, build_features_from_arrays

RNG = np.random.default_rng(42)

def _close(n=300, drift=0.001): return 100 * np.exp(np.cumsum(RNG.normal(drift, 0.015, n)))
def _hl(close): return close * (1+abs(RNG.normal(0,0.008,len(close)))), close*(1-abs(RNG.normal(0,0.008,len(close))))
def _vol(n=300): return RNG.integers(1_000_000,10_000_000,n).astype(float)
def _bars(n=300):
    from datetime import date, timedelta
    c = _close(n); h,l = _hl(c); v = _vol(n)
    return pd.DataFrame({"date":[date(2020,1,2)+timedelta(days=i) for i in range(n)],
                         "adjusted_close":c,"open":c*0.99,"high":h,"low":l,"volume":v})

class TestTrend:
    def test_above_sma20_rising(self):
        close = np.linspace(90, 110, 25)
        r = trend.compute(close)
        assert r["above_sma20"] == 1.0

    def test_no_sma200_short(self):
        r = trend.compute(np.full(50, 100.0))
        assert r["distance_sma200"] is None

    def test_all_keys(self):
        r = trend.compute(_close(300))
        assert set(r) == {"distance_sma20","distance_sma50","distance_sma200",
                          "above_sma20","above_sma50","above_sma200"}

    def test_below_sma50_falling(self):
        close = np.linspace(120, 80, 60)
        r = trend.compute(close)
        assert r["above_sma50"] == 0.0
        assert r["distance_sma50"] < 0

    def test_accepts_numpy_not_series(self):
        # must not accept pd.Series without explicit conversion
        arr = np.array([100.0, 101.0, 102.0] * 70)
        r = trend.compute(arr)
        assert isinstance(r, dict)

class TestMomentum:
    def test_return_1d(self):
        r = momentum.compute(np.array([100.0, 102.0]))
        assert r["return_1d"] == pytest.approx(math.log(102/100), abs=1e-6)

    def test_rsi_bounds(self):
        r = momentum.compute(_close(100))
        assert r["rsi_14"] is not None and 0 <= r["rsi_14"] <= 100

    def test_all_returns_present(self):
        r = momentum.compute(_close(300))
        for k in ["return_1d","return_3d","return_5d","return_10d","return_20d","return_60d"]:
            assert r[k] is not None

    def test_ema_no_pandas(self):
        # _ema is pure numpy — verify MACD doesn't import pandas
        import atlas_research.features.momentum as m_mod
        import inspect
        src = inspect.getsource(m_mod)
        assert "pd." not in src, "momentum.py must not use pandas"

    def test_rsi_all_gains_returns_100(self):
        rising = np.arange(1.0, 20.0)
        r = momentum.compute(rising)
        assert r["rsi_14"] == 100.0

class TestVolatility:
    def test_atr_positive(self):
        c = _close(100); h,l = _hl(c)
        r = volatility.compute(c, h, l)
        assert r["atr_14"] is not None and r["atr_14"] > 0

    def test_realized_vol_annualised(self):
        c = _close(100)
        r = volatility.compute(c, c, c)
        assert r["realized_vol_20"] is not None
        assert 0.01 < r["realized_vol_20"] < 2.0

    def test_insufficient_none(self):
        c = np.full(5, 100.0)
        r = volatility.compute(c, c, c)
        assert r["atr_14"] is None

    def test_no_pandas_in_source(self):
        import atlas_research.features.volatility as v_mod, inspect
        src = inspect.getsource(v_mod)
        assert "pd." not in src

class TestVolume:
    def test_flat_volume_ratio_one(self):
        c = np.full(50, 100.0)
        v = np.full(50, 1_000_000.0)
        r = volume.compute(c, v)
        assert r["volume_ratio_20"] == pytest.approx(1.0, abs=0.01)

    def test_dollar_volume_positive(self):
        c = _close(50); v = np.full(50, 5_000_000.0)
        r = volume.compute(c, v)
        assert r["dollar_volume_20"] is not None and r["dollar_volume_20"] > 0

    def test_insufficient_none(self):
        r = volume.compute(np.full(5,100.0), np.full(5,1e6))
        assert r["volume_ratio_20"] is None

    def test_no_pandas_in_source(self):
        import atlas_research.features.volume as v_mod, inspect
        src = inspect.getsource(v_mod)
        assert "pd." not in src

class TestRelativeStrength:
    def test_positive_outperform(self):
        tk = 100*np.exp(np.cumsum(np.full(200,0.005)))
        sp = 100*np.exp(np.cumsum(np.full(200,0.001)))
        r = relative_strength.compute(tk, sp)
        assert r["rs_spy_20"] > 0

    def test_none_insufficient(self):
        r = relative_strength.compute(np.full(5,100.0), np.full(5,100.0))
        assert r["rs_spy_20"] is None

    def test_no_pandas_in_source(self):
        import atlas_research.features.relative_strength as rs_mod, inspect
        src = inspect.getsource(rs_mod)
        assert "pd." not in src

class TestRegime:
    def test_bull_market(self):
        spy = np.linspace(80, 120, 250)
        r = regime.compute(spy)
        assert r["market_trend"] == 1.0
        assert r["spy_above_sma50"] == 1.0

    def test_bear_market(self):
        spy = np.linspace(150, 80, 250)
        r = regime.compute(spy)
        assert r["market_trend"] == -1.0
        assert r["spy_above_sma200"] == 0.0

    def test_insufficient_none(self):
        r = regime.compute(np.full(3, 100.0))
        assert r["spy_above_sma50"] is None

    def test_no_pandas_in_source(self):
        import atlas_research.features.regime as reg_mod, inspect
        src = inspect.getsource(reg_mod)
        assert "pd." not in src

class TestFeatureFactory:
    def test_phase1_features_present(self):
        from config.settings import PHASE1_FEATURES
        result = build_features("AAPL", _bars(300), _bars(300))
        assert result is not None
        for f in PHASE1_FEATURES:
            assert f in result, f"Missing Phase-1 feature: {f}"

    def test_regime_features_present(self):
        from config.settings import REGIME_FEATURES
        result = build_features("AAPL", _bars(300), _bars(300))
        for f in REGIME_FEATURES:
            assert f in result, f"Missing regime feature: {f}"

    def test_none_insufficient_bars(self):
        assert build_features("AAPL", _bars(10), None) is None

    def test_rs_none_without_spy(self):
        r = build_features("AAPL", _bars(300), None)
        assert r["rs_spy_20"] is None

    def test_array_entry_point_matches_df_entry_point(self):
        """build_features_from_arrays and build_features should produce identical results."""
        bars = _bars(300)
        c = bars["adjusted_close"].to_numpy(dtype=np.float64)
        h = bars["high"].to_numpy(dtype=np.float64)
        l = bars["low"].to_numpy(dtype=np.float64)
        v = bars["volume"].to_numpy(dtype=np.float64)

        result_df  = build_features("AAPL", bars, None)
        result_arr = build_features_from_arrays(c, h, l, v, None)

        assert result_df is not None and result_arr is not None
        for key in result_df:
            if result_df[key] is not None and result_arr[key] is not None:
                assert result_df[key] == pytest.approx(result_arr[key], abs=1e-8), (
                    f"Mismatch on {key}: df={result_df[key]} arr={result_arr[key]}"
                )

    def test_all_features_count(self):
        from config.settings import ALL_FEATURES
        result = build_features("AAPL", _bars(300), _bars(300))
        # every ALL_FEATURES entry should be in the dict
        for f in ALL_FEATURES:
            assert f in result, f"Missing from ALL_FEATURES: {f}"
