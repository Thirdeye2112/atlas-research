"""
Validation layer tests — severity-based model.
All tests are pure: no database, no file I/O.
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atlas_research.ingest.validate import (
    ValidationResult,
    Severity,
    validate_bars,
    validate_universe_bars,
    summary,
)

# Snap date used across all tests
SNAP = date(2024, 5, 10)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _make_bars(
    n: int = 100,
    price: float = 100.0,
    volume: float = 5_000_000.0,
    drift: float = 0.001,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate a clean bar DataFrame whose LAST row date == SNAP.
    This prevents accidental future_date warnings from contaminating
    tests that are focused on other checks.
    """
    rng    = np.random.default_rng(seed)
    prices = price * np.exp(np.cumsum(rng.normal(drift, 0.015, n)))
    # Build dates backwards from SNAP so the final bar lands on SNAP
    dates  = [SNAP - timedelta(days=(n - 1 - i)) for i in range(n)]
    return pd.DataFrame({
        "date":           dates,
        "open":           prices * 0.99,
        "high":           prices * 1.01,
        "low":            prices * 0.98,
        "close":          prices,
        "adjusted_close": prices,
        "volume":         np.full(n, volume),
    })


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestCleanData:
    def test_clean_bars_ok(self):
        r = validate_bars("AAPL", _make_bars(200), SNAP)
        assert r.ok
        assert not r.fatal_issues
        assert not r.warning_issues

    def test_quality_score_is_1_when_clean(self):
        r = validate_bars("AAPL", _make_bars(200), SNAP)
        assert r.data_quality_score == pytest.approx(1.0)

    def test_quality_flags_empty_when_clean(self):
        r = validate_bars("AAPL", _make_bars(200), SNAP)
        assert r.data_quality_flags == ""

    def test_severity_warning_when_ok(self):
        r = validate_bars("AAPL", _make_bars(200), SNAP)
        assert r.severity() == Severity.WARNING  # ok=True → not FATAL

    def test_bars_checked_field(self):
        r = validate_bars("AAPL", _make_bars(150), SNAP)
        assert r.bars_checked == 150

    def test_legacy_issues_property(self):
        r = validate_bars("AAPL", _make_bars(200), SNAP)
        assert isinstance(r.issues, list)


# ---------------------------------------------------------------------------
# FATAL checks — ok=False, ticker must be skipped
# ---------------------------------------------------------------------------

class TestFatalChecks:
    def test_empty_df_fatal(self):
        r = validate_bars("X", pd.DataFrame(), SNAP)
        assert not r.ok and r.severity() == Severity.FATAL
        assert any("no_bars" in i for i in r.fatal_issues)

    def test_none_fatal(self):
        r = validate_bars("X", None, SNAP)
        assert not r.ok

    def test_too_few_bars_fatal(self):
        r = validate_bars("X", _make_bars(5), SNAP, min_bars=15)
        assert not r.ok
        assert any("insufficient_bars" in i for i in r.fatal_issues)

    def test_missing_column_fatal(self):
        bars = _make_bars(100).drop(columns=["volume"])
        r = validate_bars("X", bars, SNAP)
        assert not r.ok
        assert any("missing_columns" in i for i in r.fatal_issues)

    def test_nan_above_threshold_fatal(self):
        bars = _make_bars(200)
        n_nan = int(0.05 * len(bars)) + 1      # > 2% threshold
        bars.loc[list(range(n_nan)), "adjusted_close"] = float("nan")
        r = validate_bars("X", bars, SNAP, nan_fatal_threshold_pct=2.0)
        assert not r.ok
        assert any("nan_prices_high" in i for i in r.fatal_issues)

    def test_zero_price_fatal(self):
        bars = _make_bars(100)
        bars.loc[50, "adjusted_close"] = 0.0
        r = validate_bars("X", bars, SNAP)
        assert not r.ok
        assert any("nonpositive_price" in i for i in r.fatal_issues)

    def test_negative_price_fatal(self):
        bars = _make_bars(100)
        bars.loc[50, "adjusted_close"] = -5.0
        r = validate_bars("X", bars, SNAP)
        assert not r.ok

    def test_duplicate_dates_fatal(self):
        bars = pd.concat([_make_bars(100), _make_bars(100).iloc[[50]]], ignore_index=True)
        r = validate_bars("X", bars, SNAP)
        assert not r.ok
        assert any("duplicate_dates" in i for i in r.fatal_issues)

    def test_flat_prices_fatal(self):
        bars = _make_bars(100)
        bars.loc[bars.index[-10:], "adjusted_close"] = 100.0
        r = validate_bars("X", bars, SNAP, price_flatness_window=10)
        assert not r.ok
        assert any("flat_prices" in i for i in r.fatal_issues)

    def test_fatal_has_no_warnings(self):
        r = validate_bars("X", pd.DataFrame(), SNAP)
        assert r.warning_issues == []

    def test_fatal_score_not_negative(self):
        r = validate_bars("X", pd.DataFrame(), SNAP)
        assert r.data_quality_score >= 0.0


# ---------------------------------------------------------------------------
# WARNING checks — ok=True, score < 1.0, flags populated
# ---------------------------------------------------------------------------

class TestWarningChecks:
    def test_low_nan_is_warning_not_fatal(self):
        bars = _make_bars(200)
        bars.loc[50, "adjusted_close"] = float("nan")   # 0.5% < 2% threshold
        r = validate_bars("AAPL", bars, SNAP, nan_fatal_threshold_pct=2.0)
        assert r.ok, f"Expected WARNING (ok=True), got: {r.fatal_issues}"
        assert any("nan_prices_low" in i for i in r.warning_issues)

    def test_warning_reduces_score(self):
        bars = _make_bars(200)
        bars.loc[50, "adjusted_close"] = float("nan")
        r = validate_bars("AAPL", bars, SNAP)
        assert r.ok and r.data_quality_score < 1.0

    def test_warning_sets_flag(self):
        bars = _make_bars(200)
        bars.loc[50, "adjusted_close"] = float("nan")
        r = validate_bars("AAPL", bars, SNAP)
        assert "nan_prices_low" in r.data_quality_flags

    def test_volume_outlier_warning(self):
        bars = _make_bars(100, volume=5_000_000)
        bars.loc[bars.index[-1], "volume"] = 5_000_000 * 25
        r = validate_bars("AAPL", bars, SNAP, volume_outlier_multiple=20.0)
        assert r.ok
        assert any("volume_outlier" in i for i in r.warning_issues)
        assert "volume_outlier" in r.data_quality_flags

    def test_multiple_warnings_accumulate(self):
        bars = _make_bars(100, volume=5_000_000)
        bars.loc[50, "adjusted_close"] = float("nan")
        bars.loc[bars.index[-1], "volume"] = 5_000_000 * 25
        r = validate_bars("AAPL", bars, SNAP, volume_outlier_multiple=20.0)
        assert r.ok and r.data_quality_score < 0.90

    def test_multiple_flags_pipe_separated(self):
        bars = _make_bars(100, volume=5_000_000)
        bars.loc[50, "adjusted_close"] = float("nan")
        bars.loc[bars.index[-1], "volume"] = 5_000_000 * 25
        r = validate_bars("AAPL", bars, SNAP, volume_outlier_multiple=20.0)
        flags = r.data_quality_flags.split("|")
        assert len(flags) == 2

    def test_score_clamped_to_zero(self):
        bars = _make_bars(100, volume=5_000_000)
        bars.loc[bars.index[-1], "adjusted_close"] = \
            bars.loc[bars.index[-1], "close"] * 4.0    # adjustment_anomaly
        bars.loc[bars.index[-1], "volume"] = 5_000_000 * 25
        bars.loc[50, "adjusted_close"] = float("nan")
        r = validate_bars("AAPL", bars, SNAP, volume_outlier_multiple=20.0)
        assert r.data_quality_score >= 0.0

    def test_adjustment_anomaly_warning(self):
        bars = _make_bars(100)
        bars.loc[bars.index[-1], "adjusted_close"] = \
            bars.loc[bars.index[-1], "close"] * 4.0
        r = validate_bars("AAPL", bars, SNAP)
        assert r.ok
        assert any("adjustment_anomaly" in i for i in r.warning_issues)


# ---------------------------------------------------------------------------
# summary() with severity awareness
# ---------------------------------------------------------------------------

class TestSummary:
    def _warned_bars(self):
        bars = _make_bars(100, volume=5_000_000)
        bars.loc[bars.index[-1], "volume"] = 5_000_000 * 25
        return bars

    def test_all_clean(self):
        s = summary({
            "AAPL": validate_bars("AAPL", _make_bars(200), SNAP),
            "MSFT": validate_bars("MSFT", _make_bars(200), SNAP),
        })
        assert s["total_tickers"] == 2
        assert s["clean"] == 2 and s["fatal"] == 0 and s["warnings"] == 0
        assert s["passed"] == 2 and s["failed"] == 0

    def test_fatal_counted(self):
        s = summary({
            "AAPL": validate_bars("AAPL", _make_bars(200), SNAP),
            "BAD":  validate_bars("BAD",  pd.DataFrame(), SNAP),
        })
        assert s["fatal"] == 1 and s["passed"] == 1
        assert "BAD" in s["fatal_issues"]

    def test_warned_counted(self):
        s = summary({
            "AAPL": validate_bars("AAPL", _make_bars(200), SNAP),
            "WARN": validate_bars("WARN", self._warned_bars(), SNAP,
                                  volume_outlier_multiple=20.0),
        })
        assert s["warnings"] == 1 and s["clean"] == 1
        assert s["passed"] == 2   # warned ticker still passes

    def test_quality_scores_in_summary(self):
        s = summary({
            "AAPL": validate_bars("AAPL", _make_bars(200), SNAP),
            "WARN": validate_bars("WARN", self._warned_bars(), SNAP,
                                  volume_outlier_multiple=20.0),
        })
        assert s["quality_scores"]["AAPL"] == pytest.approx(1.0)
        assert s["quality_scores"]["WARN"] < 1.0

    def test_quality_flags_in_summary(self):
        s = summary({
            "WARN": validate_bars("WARN", self._warned_bars(), SNAP,
                                  volume_outlier_multiple=20.0),
        })
        assert "WARN" in s["quality_flags"]
        assert "volume_outlier" in s["quality_flags"]["WARN"]

    def test_fatal_not_in_quality_scores(self):
        s = summary({"BAD": validate_bars("BAD", pd.DataFrame(), SNAP)})
        assert "BAD" not in s["quality_scores"]

    def test_empty_results(self):
        s = summary({})
        assert s["total_tickers"] == 0
        assert s["failure_rate_pct"] == 0.0
        assert s["quality_scores"] == {}

    def test_failure_rate(self):
        s = summary({
            "A": validate_bars("A", _make_bars(200), SNAP),
            "B": validate_bars("B", pd.DataFrame(), SNAP),
            "C": validate_bars("C", pd.DataFrame(), SNAP),
        })
        assert s["failure_rate_pct"] == pytest.approx(66.7, abs=0.2)
