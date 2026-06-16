"""
Parquet export and wide matrix tests.
All tests are pure — no database required.
"""

from __future__ import annotations

import sys
import tempfile
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "scripts"))

from atlas_research.exports.parquet_export import (
    build_feature_matrix,
    export_parquet,
    load_parquet,
)

SNAP     = date(2026, 6, 6)
FEATURES = ["return_5d", "rsi_14", "rs_spy_60", "distance_sma50", "volume_ratio_20"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _long(tickers: list[str], features: dict[str, float]) -> pd.DataFrame:
    rows = []
    for t in tickers:
        for fname, fval in features.items():
            rows.append({"ticker": t, "feature_name": fname, "feature_value": fval})
    return pd.DataFrame(rows)


def _labels(tickers: list[str], ret5: float = 0.02, ret20: float = 0.05) -> pd.DataFrame:
    return pd.DataFrame([{
        "ticker": t, "return_5d": ret5, "return_20d": ret20,
        "positive_5d": ret5 > 0, "positive_20d": ret20 > 0,
    } for t in tickers])


# ---------------------------------------------------------------------------
# build_feature_matrix — structure
# ---------------------------------------------------------------------------

class TestBuildFeatureMatrix:
    def test_basic_pivot(self):
        m = build_feature_matrix(SNAP, _long(["AAPL", "MSFT"], {"rsi_14": 55.0, "return_5d": 0.02}),
                                 feature_names=["rsi_14", "return_5d"])
        assert "ticker" in m.columns
        assert "rsi_14" in m.columns
        assert len(m) == 2

    def test_column_order_preserved(self):
        from config.settings import INFERENCE_EXTRA_COLS
        ordered = ["rsi_14", "rs_spy_60", "return_5d"]
        m = build_feature_matrix(SNAP, _long(["AAPL"], {"rsi_14": 55.0, "rs_spy_60": 0.03, "return_5d": 0.02}),
                                 feature_names=ordered)
        skip = {"ticker", "date", "data_quality_score", "data_quality_flags"} | set(INFERENCE_EXTRA_COLS)
        feat_cols = [c for c in m.columns if c not in skip]
        assert feat_cols == ordered

    def test_missing_feature_is_nan(self):
        m = build_feature_matrix(SNAP, _long(["AAPL"], {"rsi_14": 55.0}),
                                 feature_names=["rsi_14", "return_5d"])
        assert pd.isna(m.loc[m["ticker"] == "AAPL", "return_5d"].iloc[0])

    def test_date_column_added(self):
        m = build_feature_matrix(SNAP, _long(["AAPL"], {"rsi_14": 55.0}),
                                 feature_names=["rsi_14"])
        assert "date" in m.columns
        assert m["date"].iloc[0] == SNAP

    def test_empty_long_returns_empty(self):
        assert build_feature_matrix(SNAP, pd.DataFrame(), feature_names=FEATURES).empty

    def test_none_long_returns_empty(self):
        assert build_feature_matrix(SNAP, None, feature_names=FEATURES).empty


# ---------------------------------------------------------------------------
# build_feature_matrix — data_quality columns
# ---------------------------------------------------------------------------

class TestDataQualityColumns:
    def test_quality_score_column_present(self):
        m = build_feature_matrix(SNAP, _long(["AAPL"], {"rsi_14": 55.0}),
                                 feature_names=["rsi_14"])
        assert "data_quality_score" in m.columns

    def test_quality_flags_column_present(self):
        m = build_feature_matrix(SNAP, _long(["AAPL"], {"rsi_14": 55.0}),
                                 feature_names=["rsi_14"])
        assert "data_quality_flags" in m.columns

    def test_default_score_is_1_when_no_scores_provided(self):
        m = build_feature_matrix(SNAP, _long(["AAPL", "MSFT"], {"rsi_14": 55.0}),
                                 feature_names=["rsi_14"])
        assert (m["data_quality_score"] == 1.0).all()

    def test_default_flags_empty_when_no_flags_provided(self):
        m = build_feature_matrix(SNAP, _long(["AAPL"], {"rsi_14": 55.0}),
                                 feature_names=["rsi_14"])
        assert m["data_quality_flags"].iloc[0] == ""

    def test_score_written_per_ticker(self):
        scores = {"AAPL": 1.0, "MSFT": 0.85}
        m = build_feature_matrix(SNAP,
                                 _long(["AAPL", "MSFT"], {"rsi_14": 55.0}),
                                 feature_names=["rsi_14"],
                                 quality_scores=scores)
        aapl_score = m.loc[m["ticker"] == "AAPL", "data_quality_score"].iloc[0]
        msft_score = m.loc[m["ticker"] == "MSFT", "data_quality_score"].iloc[0]
        assert aapl_score == pytest.approx(1.0)
        assert msft_score == pytest.approx(0.85)

    def test_flags_written_per_ticker(self):
        flags = {"MSFT": "volume_outlier"}
        m = build_feature_matrix(SNAP,
                                 _long(["AAPL", "MSFT"], {"rsi_14": 55.0}),
                                 feature_names=["rsi_14"],
                                 quality_flags=flags)
        aapl_flag = m.loc[m["ticker"] == "AAPL", "data_quality_flags"].iloc[0]
        msft_flag = m.loc[m["ticker"] == "MSFT", "data_quality_flags"].iloc[0]
        assert aapl_flag == ""
        assert msft_flag == "volume_outlier"

    def test_ticker_not_in_scores_dict_gets_1(self):
        scores = {"AAPL": 0.80}   # MSFT not in dict
        m = build_feature_matrix(SNAP,
                                 _long(["AAPL", "MSFT"], {"rsi_14": 55.0}),
                                 feature_names=["rsi_14"],
                                 quality_scores=scores)
        msft_score = m.loc[m["ticker"] == "MSFT", "data_quality_score"].iloc[0]
        assert msft_score == pytest.approx(1.0)

    def test_multiple_flags_preserved(self):
        flags = {"AAPL": "volume_outlier|nan_prices_low"}
        m = build_feature_matrix(SNAP,
                                 _long(["AAPL"], {"rsi_14": 55.0}),
                                 feature_names=["rsi_14"],
                                 quality_flags=flags)
        assert m["data_quality_flags"].iloc[0] == "volume_outlier|nan_prices_low"


# ---------------------------------------------------------------------------
# build_feature_matrix — label join
# ---------------------------------------------------------------------------

class TestLabelJoin:
    def test_labels_joined(self):
        m = build_feature_matrix(SNAP,
                                 _long(["AAPL", "MSFT"], {"rsi_14": 55.0}),
                                 labels_df=_labels(["AAPL", "MSFT"]),
                                 feature_names=["rsi_14"])
        assert "label_return_5d" in m.columns
        assert "label_positive_5d" in m.columns

    def test_label_null_for_missing_ticker(self):
        m = build_feature_matrix(SNAP,
                                 _long(["AAPL", "MSFT"], {"rsi_14": 55.0}),
                                 labels_df=_labels(["AAPL"]),  # MSFT has no label
                                 feature_names=["rsi_14"])
        msft_label = m.loc[m["ticker"] == "MSFT", "label_return_5d"].iloc[0]
        assert pd.isna(msft_label)

    def test_no_labels_no_label_columns(self):
        m = build_feature_matrix(SNAP,
                                 _long(["AAPL"], {"rsi_14": 55.0}),
                                 labels_df=None,
                                 feature_names=["rsi_14"])
        assert "label_return_5d" not in m.columns

    def test_label_values_correct(self):
        m = build_feature_matrix(SNAP,
                                 _long(["AAPL"], {"rsi_14": 55.0}),
                                 labels_df=_labels(["AAPL"], ret5=0.031),
                                 feature_names=["rsi_14"])
        assert m.loc[m["ticker"] == "AAPL", "label_return_5d"].iloc[0] == pytest.approx(0.031)


# ---------------------------------------------------------------------------
# Parquet roundtrip
# ---------------------------------------------------------------------------

class TestParquetRoundtrip:
    def test_write_and_read(self):
        m = build_feature_matrix(SNAP, _long(["AAPL", "MSFT"], {"rsi_14": 55.0, "return_5d": 0.02}),
                                 feature_names=["rsi_14", "return_5d"])
        with tempfile.TemporaryDirectory() as d:
            path = export_parquet(SNAP, m, output_dir=Path(d))
            assert path.exists()
            assert path.name == f"feature_matrix_{SNAP.isoformat()}.parquet"
            loaded = load_parquet(SNAP, output_dir=Path(d))
            assert len(loaded) == 2
            assert "rsi_14" in loaded.columns

    def test_quality_columns_survive_roundtrip(self):
        scores = {"AAPL": 0.85, "MSFT": 1.0}
        flags  = {"AAPL": "volume_outlier"}
        m = build_feature_matrix(SNAP, _long(["AAPL", "MSFT"], {"rsi_14": 55.0}),
                                 feature_names=["rsi_14"],
                                 quality_scores=scores, quality_flags=flags)
        with tempfile.TemporaryDirectory() as d:
            export_parquet(SNAP, m, output_dir=Path(d))
            loaded = load_parquet(SNAP, output_dir=Path(d))
            aapl = loaded[loaded["ticker"] == "AAPL"]
            assert aapl["data_quality_score"].iloc[0] == pytest.approx(0.85)
            assert aapl["data_quality_flags"].iloc[0] == "volume_outlier"
            msft = loaded[loaded["ticker"] == "MSFT"]
            assert msft["data_quality_score"].iloc[0] == pytest.approx(1.0)
            assert msft["data_quality_flags"].iloc[0] == ""

    def test_values_preserved(self):
        m = build_feature_matrix(SNAP, _long(["AAPL"], {"rsi_14": 58.37, "return_5d": -0.01234}),
                                 feature_names=["rsi_14", "return_5d"])
        with tempfile.TemporaryDirectory() as d:
            export_parquet(SNAP, m, output_dir=Path(d))
            loaded = load_parquet(SNAP, output_dir=Path(d))
            row = loaded[loaded["ticker"] == "AAPL"]
            assert row["rsi_14"].iloc[0] == pytest.approx(58.37, abs=1e-6)
            assert row["return_5d"].iloc[0] == pytest.approx(-0.01234, abs=1e-6)

    def test_column_selection_on_load(self):
        m = build_feature_matrix(SNAP, _long(["AAPL"], {"rsi_14": 55.0, "return_5d": 0.02}),
                                 feature_names=["rsi_14", "return_5d"])
        with tempfile.TemporaryDirectory() as d:
            export_parquet(SNAP, m, output_dir=Path(d))
            loaded = load_parquet(SNAP, output_dir=Path(d), columns=["ticker", "rsi_14"])
            assert "return_5d" not in loaded.columns
            assert "rsi_14" in loaded.columns

    def test_empty_matrix_raises(self):
        with pytest.raises(ValueError, match="empty"):
            export_parquet(SNAP, pd.DataFrame())

    def test_missing_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as d:
            assert load_parquet(date(2000, 1, 1), output_dir=Path(d)).empty

    def test_large_universe_roundtrip(self):
        """185 tickers × 27 features — no silent data loss."""
        tickers   = [f"T{i:04d}" for i in range(185)]
        feat_dict = {f"feat_{j}": float(j) * 0.01 for j in range(27)}
        feat_names = list(feat_dict.keys())
        m = build_feature_matrix(SNAP, _long(tickers, feat_dict),
                                 feature_names=feat_names)
        with tempfile.TemporaryDirectory() as d:
            export_parquet(SNAP, m, output_dir=Path(d))
            loaded = load_parquet(SNAP, output_dir=Path(d))
        assert len(loaded) == 185
        assert set(feat_names).issubset(set(loaded.columns))
        assert "data_quality_score" in loaded.columns
        assert "data_quality_flags" in loaded.columns

    def test_snappy_compression(self):
        m = build_feature_matrix(SNAP, _long(["AAPL"], {"rsi_14": 55.0}),
                                 feature_names=["rsi_14"])
        with tempfile.TemporaryDirectory() as d:
            path = export_parquet(SNAP, m, output_dir=Path(d), compression="snappy")
            assert path.stat().st_size > 0


# ---------------------------------------------------------------------------
# Integration: validation → matrix
# ---------------------------------------------------------------------------

class TestValidationToMatrix:
    """End-to-end: validation results flow into the matrix correctly."""

    def test_warned_ticker_has_score_below_1(self):
        from atlas_research.ingest.validate import validate_bars, summary as vsum
        from datetime import timedelta

        rng = np.random.default_rng(0)
        n   = 100
        prices = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.015, n)))
        bars = pd.DataFrame({
            "date":           [date(2024,1,2)+timedelta(days=i) for i in range(n)],
            "open":           prices * 0.99,
            "high":           prices * 1.01,
            "low":            prices * 0.98,
            "close":          prices,
            "adjusted_close": prices,
            "volume":         np.full(n, 5_000_000.0),
        })
        bars.loc[bars.index[-1], "volume"] = 5_000_000 * 25  # trigger volume_outlier

        results = {
            "AAPL": validate_bars("AAPL", bars, SNAP, volume_outlier_multiple=20.0),
        }
        s = vsum(results)

        m = build_feature_matrix(
            SNAP,
            _long(["AAPL"], {"rsi_14": 55.0}),
            feature_names=["rsi_14"],
            quality_scores=s["quality_scores"],
            quality_flags=s["quality_flags"],
        )
        row = m[m["ticker"] == "AAPL"]
        assert row["data_quality_score"].iloc[0] < 1.0
        assert "volume_outlier" in row["data_quality_flags"].iloc[0]


# ---------------------------------------------------------------------------
# INFERENCE_EXTRA_COLS — jarvis / oscar / hma survive parquet roundtrip
# ---------------------------------------------------------------------------

class TestInferenceExtraCols:
    """Verify that INFERENCE_EXTRA_COLS are exported alongside ALL_FEATURES
    without affecting the ML feature order."""

    FEAT = ["rsi_14", "return_5d"]

    def _eav(self, tickers, *, oscar=1.0, jarvis=1.0, qtier=1.0, hma=1.0):
        rows = []
        for t in tickers:
            rows.append({"ticker": t, "feature_name": "rsi_14",                  "feature_value": 55.0})
            rows.append({"ticker": t, "feature_name": "return_5d",               "feature_value": 0.02})
            rows.append({"ticker": t, "feature_name": "oscar_87_above_50",       "feature_value": oscar})
            rows.append({"ticker": t, "feature_name": "jarvis_quality_adjusted", "feature_value": jarvis})
            rows.append({"ticker": t, "feature_name": "quality_tier",            "feature_value": qtier})
            rows.append({"ticker": t, "feature_name": "hma_87_above",            "feature_value": hma})
        return pd.DataFrame(rows)

    def test_inference_cols_present_in_matrix(self):
        m = build_feature_matrix(SNAP, self._eav(["AAPL"]), feature_names=self.FEAT)
        assert "oscar_87_above_50" in m.columns
        assert "jarvis_quality_adjusted" in m.columns
        assert "quality_tier" in m.columns
        assert "hma_87_above" in m.columns

    def test_ml_features_still_in_correct_order(self):
        m = build_feature_matrix(SNAP, self._eav(["AAPL"]), feature_names=self.FEAT)
        ml_cols = [c for c in m.columns if c in self.FEAT]
        assert ml_cols == self.FEAT

    def test_inference_cols_appended_after_ml_features(self):
        from config.settings import INFERENCE_EXTRA_COLS
        m = build_feature_matrix(SNAP, self._eav(["AAPL"]), feature_names=self.FEAT)
        all_cols = list(m.columns)
        rsi_idx   = all_cols.index("rsi_14")
        oscar_idx = all_cols.index("oscar_87_above_50")
        assert oscar_idx > rsi_idx

    def test_inference_col_values_correct(self):
        m = build_feature_matrix(SNAP, self._eav(["AAPL"], oscar=0.0, jarvis=-1.0, qtier=2.0),
                                 feature_names=self.FEAT)
        row = m[m["ticker"] == "AAPL"]
        assert row["oscar_87_above_50"].iloc[0] == pytest.approx(0.0)
        assert row["jarvis_quality_adjusted"].iloc[0] == pytest.approx(-1.0)
        assert row["quality_tier"].iloc[0] == pytest.approx(2.0)

    def test_inference_cols_nan_when_not_in_eav(self):
        # EAV has only ML features — inference cols should be NaN, not error
        eav = _long(["AAPL"], {"rsi_14": 55.0, "return_5d": 0.02})
        m = build_feature_matrix(SNAP, eav, feature_names=self.FEAT)
        assert pd.isna(m.loc[m["ticker"] == "AAPL", "oscar_87_above_50"].iloc[0])

    def test_inference_cols_survive_parquet_roundtrip(self):
        m = build_feature_matrix(SNAP, self._eav(["AAPL", "MSFT"], oscar=1.0),
                                 feature_names=self.FEAT)
        with tempfile.TemporaryDirectory() as d:
            export_parquet(SNAP, m, output_dir=Path(d))
            loaded = load_parquet(SNAP, output_dir=Path(d))
        assert "oscar_87_above_50" in loaded.columns
        assert "jarvis_quality_adjusted" in loaded.columns
        assert loaded.loc[loaded["ticker"] == "AAPL", "oscar_87_above_50"].iloc[0] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# NaN direction handling — missing OSCAR must not invert OMNI signal
# ---------------------------------------------------------------------------

class TestOmniOscarNaNDirection:
    """Verify the _layer_direction('omni_oscar') fix: missing oscar → neutral,
    not bearish. OMNI alone must determine direction when oscar is absent."""

    def _make_df(self, omni_val, oscar_val):
        """Single-row DataFrame with OMNI and optional OSCAR values."""
        return pd.DataFrame({
            "ticker":         ["AAPL"],
            "omni_82_above":  [omni_val],
            "oscar_87_above_50": [oscar_val],
        })

    def test_omni_bullish_oscar_missing_gives_bullish(self):
        from run_edge_hierarchy import _layer_direction  # noqa: PLC0415
        df = self._make_df(1.0, np.nan)
        d = _layer_direction(df, "omni_oscar")
        assert d.iloc[0] == 1, "OMNI bullish + missing OSCAR must produce +1, not -1"

    def test_omni_bearish_oscar_missing_gives_bearish(self):
        from run_edge_hierarchy import _layer_direction  # noqa: PLC0415
        df = self._make_df(0.0, np.nan)
        d = _layer_direction(df, "omni_oscar")
        assert d.iloc[0] == -1, "OMNI bearish + missing OSCAR must produce -1"

    def test_omni_bullish_oscar_bullish_gives_bullish(self):
        from run_edge_hierarchy import _layer_direction  # noqa: PLC0415
        df = self._make_df(1.0, 1.0)
        d = _layer_direction(df, "omni_oscar")
        assert d.iloc[0] == 1

    def test_omni_bearish_oscar_bearish_gives_bearish(self):
        from run_edge_hierarchy import _layer_direction  # noqa: PLC0415
        df = self._make_df(0.0, 0.0)
        d = _layer_direction(df, "omni_oscar")
        assert d.iloc[0] == -1

    def test_both_missing_gives_neutral(self):
        from run_edge_hierarchy import _layer_direction  # noqa: PLC0415
        df = self._make_df(np.nan, np.nan)
        d = _layer_direction(df, "omni_oscar")
        assert d.iloc[0] == 0, "Both missing → neutral (0)"

    def test_omni_missing_oscar_bullish_gives_bullish(self):
        from run_edge_hierarchy import _layer_direction  # noqa: PLC0415
        df = self._make_df(np.nan, 1.0)
        d = _layer_direction(df, "omni_oscar")
        assert d.iloc[0] == 1, "OMNI missing + OSCAR bullish must produce +1"


# ---------------------------------------------------------------------------
# OMNI-based trigger patterns
# ---------------------------------------------------------------------------

class TestOmniTriggers:
    """Verify newly implemented OMNI-based condition types fire correctly."""

    def _df(self, **kwargs):
        base = {"ticker": ["AAPL"], "date": [date(2026, 1, 2)],
                "omni_82_above": [np.nan], "oscar_87_above_50": [np.nan],
                "hma_87_above": [np.nan], "omni_82_bounce": [np.nan],
                "omni_82_slope": [np.nan], "return_1d": [np.nan],
                "volume_ratio_20": [np.nan]}
        base.update(kwargs)
        return pd.DataFrame(base)

    def _trig(self, condition_type, params, df):
        from run_edge_hierarchy import _trigger_vec_local
        false_s = pd.Series(False, index=df.index)
        return _trigger_vec_local(condition_type, params, df, false_s)

    def test_oscar_cross_up_fires_when_above(self):
        df = self._df(oscar_87_above_50=[1.0])
        assert self._trig("oscar_cross_up", {}, df).iloc[0]

    def test_oscar_cross_up_no_fire_when_below(self):
        df = self._df(oscar_87_above_50=[0.0])
        assert not self._trig("oscar_cross_up", {}, df).iloc[0]

    def test_ema_lows_cross_up_fires_when_above_omni(self):
        df = self._df(omni_82_above=[1.0])
        assert self._trig("ema_lows_cross_up", {}, df).iloc[0]

    def test_hma_cross_up_fires_when_hma_above(self):
        df = self._df(hma_87_above=[1.0])
        assert self._trig("hma_cross_up", {}, df).iloc[0]

    def test_ema_lows_support_fires_on_bounce(self):
        df = self._df(omni_82_bounce=[1.0])
        assert self._trig("ema_lows_support", {}, df).iloc[0]

    def test_ema_lows_green_slope_fires_when_above_and_positive_slope(self):
        df = self._df(omni_82_above=[1.0], omni_82_slope=[0.001])
        assert self._trig("ema_lows_green_slope", {}, df).iloc[0]

    def test_ema_lows_green_slope_no_fire_when_above_but_negative_slope(self):
        df = self._df(omni_82_above=[1.0], omni_82_slope=[-0.001])
        assert not self._trig("ema_lows_green_slope", {}, df).iloc[0]

    def test_volume_climax_down_fires_on_spike_and_drop(self):
        df = self._df(volume_ratio_20=[3.0], return_1d=[-0.03])
        assert self._trig("volume_climax_down", {}, df).iloc[0]

    def test_volume_climax_down_no_fire_without_vol_spike(self):
        df = self._df(volume_ratio_20=[1.2], return_1d=[-0.03])
        assert not self._trig("volume_climax_down", {}, df).iloc[0]

    def test_unknown_condition_returns_false(self):
        df = self._df()
        result = self._trig("sector_leading_nd", {}, df)
        assert not result.iloc[0]
