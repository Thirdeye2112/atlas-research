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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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
        ordered = ["rsi_14", "rs_spy_60", "return_5d"]
        m = build_feature_matrix(SNAP, _long(["AAPL"], {"rsi_14": 55.0, "rs_spy_60": 0.03, "return_5d": 0.02}),
                                 feature_names=ordered)
        feat_cols = [c for c in m.columns if c not in ("ticker", "date", "data_quality_score", "data_quality_flags")]
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
