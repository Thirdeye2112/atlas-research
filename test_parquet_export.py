"""
Data validation layer — severity-based.

SEVERITY MODEL
--------------
Every check is classified as FATAL or WARNING.

  FATAL   — ticker is skipped entirely for this date.
            Feature computation on corrupt data produces corrupt features.
            Examples: no bars, missing columns, zero/negative prices,
            duplicate dates (corrupt primary key), NaN rate > 10%.

  WARNING — ticker proceeds through feature computation.
            The issue is recorded and surfaced in two ways:
              1. data_quality_score  (float 0.0–1.0; 1.0 = clean)
                 Written as a feature column in the parquet export matrix.
              2. data_quality_flags  (pipe-separated string)
                 Written as a metadata column in the parquet export matrix.
            Phase 2 models can optionally condition on data_quality_score
            to discount predictions from lower-quality bars.

SCORE FORMULA
-------------
    score = 1.0 - (sum of warning_weights for triggered warnings)
    clamped to [0.0, 1.0]

Warning weights (tunable in settings):
    nan_prices_low   (< 2%):   0.05
    nan_prices_high  (≥ 2%):   FATAL (skip entirely)
    date_gap:                  0.10
    volume_outlier:            0.15
    flat_prices:               FATAL
    adjustment_anomaly:        0.20
    future_date:               0.05

ARCHITECTURE NOTE
-----------------
This module has no I/O and no side effects.
validate_bars() is a pure function: result = f(data).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Severity classification
# ---------------------------------------------------------------------------

class Severity(Enum):
    FATAL   = "fatal"    # ticker skipped; features not computed
    WARNING = "warning"  # ticker proceeds; score and flags recorded


# Warning penalty weights — sum determines quality score deduction.
# All weights must be in [0.0, 1.0].
_WARNING_WEIGHTS: dict[str, float] = {
    "nan_prices_low":       0.05,   # NaN rate < 2%
    "date_gap":             0.10,   # gap > 5 calendar days between bars
    "volume_outlier":       0.15,   # today volume > 20x 20-day mean
    "adjustment_anomaly":   0.20,   # adj/raw ratio looks wrong
    "future_date":          0.05,   # last bar timestamped after snap_date
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    ticker:    str
    snap_date: date
    ok:        bool          # False means FATAL — skip this ticker
    bars_checked: int = 0

    # Per-severity issue lists
    fatal_issues:   list[str] = field(default_factory=list)
    warning_issues: list[str] = field(default_factory=list)

    # Derived from warnings — written to parquet matrix
    data_quality_score: float = 1.0   # 1.0 = clean; lower = more warnings
    data_quality_flags: str   = ""    # pipe-separated warning flag names

    # Legacy property so existing callers (summary, pipeline) still work
    @property
    def issues(self) -> list[str]:
        return self.fatal_issues + self.warning_issues

    def add_fatal(self, flag: str, message: str) -> None:
        self.fatal_issues.append(f"{flag}: {message}")
        self.ok = False

    def add_warning(self, flag: str, message: str) -> None:
        self.warning_issues.append(f"{flag}: {message}")
        penalty = _WARNING_WEIGHTS.get(flag, 0.05)
        self.data_quality_score = max(0.0, self.data_quality_score - penalty)
        if self.data_quality_flags:
            self.data_quality_flags += f"|{flag}"
        else:
            self.data_quality_flags = flag

    def severity(self) -> Severity:
        return Severity.FATAL if not self.ok else Severity.WARNING


# ---------------------------------------------------------------------------
# Main validation function
# ---------------------------------------------------------------------------

def validate_bars(
    ticker: str,
    bars: pd.DataFrame,
    snap_date: date,
    *,
    min_bars: int = 15,
    max_gap_days: int = 5,
    volume_outlier_multiple: float = 20.0,
    price_flatness_window: int = 10,
    nan_fatal_threshold_pct: float = 2.0,
) -> ValidationResult:
    """
    Validate a bar DataFrame for one ticker before feature computation.

    Args:
        ticker:                   Ticker symbol.
        bars:                     DataFrame: date, open, high, low, close,
                                  adjusted_close, volume. Ascending by date.
        snap_date:                Date being processed.
        min_bars:                 Minimum bars for features (FATAL if below).
        max_gap_days:             Max calendar-day gap between consecutive bars
                                  before flagging as WARNING.
        volume_outlier_multiple:  Flag if today volume > N × 20-day mean (WARNING).
        price_flatness_window:    Bars to check for stuck prices (FATAL if all identical).
        nan_fatal_threshold_pct:  NaN rate above this → FATAL; below → WARNING.

    Returns:
        ValidationResult.  ok=False means FATAL — do not compute features.
        ok=True with warnings means proceed; use data_quality_score downstream.
    """
    result = ValidationResult(ticker=ticker, snap_date=snap_date, ok=True)

    # ── FATAL: no data at all ─────────────────────────────────
    if bars is None or bars.empty:
        result.add_fatal("no_bars", "DataFrame is empty or None")
        return result

    result.bars_checked = len(bars)

    # ── FATAL: minimum bar count ──────────────────────────────
    if len(bars) < min_bars:
        result.add_fatal("insufficient_bars", f"{len(bars)} bars < minimum {min_bars}")
        return result

    # ── FATAL: required columns ───────────────────────────────
    required = {"date", "open", "high", "low", "close", "adjusted_close", "volume"}
    missing  = required - set(bars.columns)
    if missing:
        result.add_fatal("missing_columns", f"{sorted(missing)}")
        return result

    # Extract arrays for numpy checks
    adj_close = bars["adjusted_close"].to_numpy(dtype=np.float64)
    raw_close = bars["close"].to_numpy(dtype=np.float64)
    volume    = bars["volume"].to_numpy(dtype=np.float64)
    dates     = bars["date"]

    valid_prices = adj_close[~np.isnan(adj_close)]

    # ── FATAL / WARNING: NaN prices ───────────────────────────
    nan_count = int(np.isnan(adj_close).sum())
    if nan_count > 0:
        nan_pct = nan_count / len(adj_close) * 100
        if nan_pct >= nan_fatal_threshold_pct:
            result.add_fatal(
                "nan_prices_high",
                f"{nan_count} NaN adjusted_close ({nan_pct:.1f}%) ≥ {nan_fatal_threshold_pct}% threshold"
            )
            return result   # skip remaining checks; data too corrupt
        else:
            result.add_warning(
                "nan_prices_low",
                f"{nan_count} NaN adjusted_close ({nan_pct:.1f}%) — below fatal threshold"
            )

    # ── FATAL: zero or negative prices ───────────────────────
    if len(valid_prices) > 0 and float(valid_prices.min()) <= 0:
        result.add_fatal(
            "nonpositive_price",
            f"min adjusted_close = {float(valid_prices.min()):.4f}"
        )
        return result

    # ── FATAL: duplicate dates ────────────────────────────────
    if hasattr(dates, "duplicated"):
        dup_count = int(dates.duplicated().sum())
    else:
        dup_count = len(dates) - len(set(dates))
    if dup_count > 0:
        result.add_fatal("duplicate_dates", f"{dup_count} duplicate date rows")
        return result

    # ── FATAL: flat / stuck prices ────────────────────────────
    if len(valid_prices) >= price_flatness_window:
        window = valid_prices[-price_flatness_window:]
        if float(window.std()) == 0.0:
            result.add_fatal(
                "flat_prices",
                f"adjusted_close identical for last {price_flatness_window} bars — feed stuck"
            )
            return result

    # ── WARNING: date gaps ────────────────────────────────────
    date_vals = sorted(dates.tolist())
    for i in range(1, len(date_vals)):
        a, b = date_vals[i - 1], date_vals[i]
        # Handle both date objects and Timestamps
        a = a.date() if hasattr(a, "date") and callable(a.date) else a
        b = b.date() if hasattr(b, "date") and callable(b.date) else b
        gap_days = (b - a).days
        if gap_days > max_gap_days:
            result.add_warning(
                "date_gap",
                f"{gap_days}-day gap between {a} and {b}"
            )
            break   # report first gap only

    # ── WARNING: future dates ─────────────────────────────────
    last = dates.iloc[-1]
    last = last.date() if hasattr(last, "date") and callable(last.date) else last
    if last > snap_date:
        result.add_warning("future_date", f"last bar {last} is after snap_date {snap_date}")

    # ── WARNING: volume outliers ──────────────────────────────
    valid_vol = volume[~np.isnan(volume)]
    if len(valid_vol) >= 21:
        vol_mean_20 = float(valid_vol[-21:-1].mean())
        today_vol   = float(valid_vol[-1])
        if vol_mean_20 > 0 and today_vol > volume_outlier_multiple * vol_mean_20:
            result.add_warning(
                "volume_outlier",
                f"today {today_vol:.0f} is {today_vol/vol_mean_20:.1f}x 20-day mean"
            )

    # ── WARNING: split / adjustment anomaly ──────────────────
    valid_mask = (~np.isnan(adj_close)) & (~np.isnan(raw_close)) & (raw_close > 0)
    if valid_mask.sum() > 0:
        ratios = adj_close[valid_mask] / raw_close[valid_mask]
        max_ratio = float(ratios.max())
        if max_ratio > 3.0:
            result.add_warning(
                "adjustment_anomaly",
                f"max adj/raw ratio = {max_ratio:.2f} (expected < 3.0)"
            )

    return result


# ---------------------------------------------------------------------------
# Universe-level helpers
# ---------------------------------------------------------------------------

def validate_universe_bars(
    tickers_bars: dict[str, pd.DataFrame],
    snap_date: date,
) -> dict[str, ValidationResult]:
    """Validate bars for all tickers. Returns {ticker: ValidationResult}."""
    return {
        ticker: validate_bars(ticker, bars, snap_date)
        for ticker, bars in tickers_bars.items()
    }


def summary(results: dict[str, ValidationResult]) -> dict:
    """
    Aggregate summary dict for logging and research_runs records.

    Returns counts, failure rate, and per-ticker issue details.
    Also returns per-ticker data_quality_score for the pipeline to
    pass through to the parquet matrix builder.
    """
    total    = len(results)
    fatal    = sum(1 for r in results.values() if not r.ok)
    warnings = sum(1 for r in results.values() if r.ok and r.warning_issues)
    ok_clean = total - fatal - warnings

    quality_scores: dict[str, float] = {
        ticker: r.data_quality_score
        for ticker, r in results.items()
        if r.ok
    }
    quality_flags: dict[str, str] = {
        ticker: r.data_quality_flags
        for ticker, r in results.items()
        if r.ok and r.data_quality_flags
    }
    fatal_issues: dict[str, list[str]] = {
        ticker: r.fatal_issues
        for ticker, r in results.items()
        if not r.ok
    }

    return {
        "total_tickers":    total,
        "clean":            ok_clean,
        "warnings":         warnings,
        "fatal":            fatal,
        "passed":           total - fatal,          # clean + warnings both "passed"
        "failed":           fatal,                  # legacy key; same as fatal
        "failure_rate_pct": round(fatal / total * 100, 1) if total else 0.0,
        "fatal_issues":     fatal_issues,
        "quality_scores":   quality_scores,
        "quality_flags":    quality_flags,
    }
