"""
Adaptive Confidence Calibrator
================================
Loads historical accuracy from prediction_outcomes, builds per-context accuracy
buckets, and adjusts raw model confidence based on how well each context has
historically predicted direction.

Usage (standalone):
    cal = ConfidenceCalibrator.from_db(engine)
    result = cal.calibrate(row)   # row is a dict with context fields

Usage (in predict.py):
    cal = ConfidenceCalibrator.from_db(engine)
    predictions = cal.apply(predictions_df, parquet_df)

Context buckets used (all available at predict time from parquet):
    quality_tier        1-4 (from INFERENCE_EXTRA_COLS)
    vix_regime          low / moderate / high (from realized_vol_20)
    sector_regime       bull / bear / range (from market_trend)
    above_sma200        True / False
    jarvis_green        True / False / None (from jarvis_quality_adjusted)

Calibration formula:
    multiplier = smooth(context_accuracy) / baseline_accuracy
    multiplier = clip(multiplier, floor=CAP_FLOOR, ceil=CAP_CEIL)
    calibrated_confidence = raw_confidence * multiplier

Safety rules (conservative by design):
    - Tier 3/4 contexts cannot receive multiplier > 1.0 unless n >= PROVEN_MIN_N
      AND context_accuracy > baseline + PROVEN_MARGIN
    - VIX high context follows the same rule
    - If n < MIN_N, fall back to baseline (multiplier = 1.0)
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_N           = 100       # minimum sample to use a bucket
PROVEN_MIN_N    = 500       # minimum to allow boost for risky contexts
PROVEN_MARGIN   = 0.02      # must exceed baseline by 2% to be boosted
CAP_CEIL        = 1.50      # maximum calibration multiplier
CAP_FLOOR       = 0.50      # minimum calibration multiplier
SMOOTHING_ALPHA = 50        # Bayesian smoothing: n_pseudo_obs at baseline


# ---------------------------------------------------------------------------
# VIX / sector regime helpers (identical to compute_prediction_outcomes.py)
# ---------------------------------------------------------------------------

def _vix_regime(rv20: float) -> str:
    if math.isnan(rv20):
        return "unknown"
    if rv20 > 0.40:
        return "high"
    if rv20 > 0.20:
        return "moderate"
    return "low"


def _sector_regime(market_trend: float) -> str:
    if math.isnan(market_trend):
        return "unknown"
    if market_trend > 0:
        return "bull"
    if market_trend < 0:
        return "bear"
    return "range"


# ---------------------------------------------------------------------------
# Bucket key builder
# ---------------------------------------------------------------------------

def _build_context_key(**kwargs) -> str:
    """Serialise context fields into a stable string key."""
    parts = []
    for k in sorted(kwargs):
        v = kwargs[k]
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        parts.append(f"{k}={v}")
    return "|".join(parts)


# ---------------------------------------------------------------------------
# Single-dimension bucket stats
# ---------------------------------------------------------------------------

@dataclass
class BucketStats:
    key:          str
    n:            int
    accuracy:     float          # historical 5d direction hit rate
    smoothed:     float          # Bayesian-smoothed accuracy
    multiplier:   float          # smoothed / baseline, clamped
    is_dangerous: bool = False   # Tier3/4 or VIX high
    is_proven:    bool = False   # enough data + margin to trust dangerous boost


# ---------------------------------------------------------------------------
# Main calibrator
# ---------------------------------------------------------------------------

@dataclass
class ConfidenceCalibrator:
    buckets:          dict[str, BucketStats]   # key → stats
    baseline_accuracy: float
    _lookup_cache:    dict[str, BucketStats] = field(default_factory=dict, repr=False)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_db(cls, engine) -> "ConfidenceCalibrator":
        """
        Build calibrator from the prediction_outcomes table.
        Falls back to a no-op calibrator (multiplier=1.0 everywhere) if the
        table is empty or the DB is unreachable.
        """
        try:
            from sqlalchemy import text
            sql = text("""
                SELECT
                    quality_tier,
                    vix_regime,
                    sector_regime,
                    above_sma200,
                    jarvis_green,
                    COUNT(*)                                             AS n,
                    AVG(direction_correct_5d::int)                       AS accuracy
                FROM prediction_outcomes
                WHERE direction_correct_5d IS NOT NULL
                GROUP BY quality_tier, vix_regime, sector_regime,
                         above_sma200, jarvis_green
            """)
            with engine.connect() as conn:
                rows = conn.execute(sql).fetchall()
                baseline_row = conn.execute(text("""
                    SELECT AVG(direction_correct_5d::int) AS baseline
                    FROM prediction_outcomes
                    WHERE direction_correct_5d IS NOT NULL
                """)).fetchone()
        except Exception:
            return cls._noop()

        if not rows:
            return cls._noop()

        baseline = float(baseline_row[0]) if baseline_row and baseline_row[0] else 0.52

        buckets: dict[str, BucketStats] = {}
        for row in rows:
            qt    = row[0]
            vix   = row[1]
            sec   = row[2]
            sma   = row[3]
            jarv  = row[4]
            n     = int(row[5])
            acc   = float(row[6]) if row[6] is not None else baseline

            key = _build_context_key(
                quality_tier=str(qt) if qt is not None else None,
                vix_regime=vix,
                sector_regime=sec,
                above_sma200=str(bool(sma)) if sma is not None else None,
                jarvis_green=str(bool(jarv)) if jarv is not None else None,
            )

            is_dangerous = (
                (qt is not None and int(qt) >= 3) or
                (vix == "high")
            )

            smoothed = _smooth(acc, n, baseline)

            if n < MIN_N:
                mult = 1.0
                proven = False
            elif is_dangerous:
                proven = (n >= PROVEN_MIN_N and smoothed > baseline + PROVEN_MARGIN)
                mult = min(CAP_CEIL, max(CAP_FLOOR, smoothed / baseline)) if proven else min(1.0, smoothed / baseline)
            else:
                proven = True
                mult = min(CAP_CEIL, max(CAP_FLOOR, smoothed / baseline))

            buckets[key] = BucketStats(
                key=key, n=n, accuracy=acc, smoothed=smoothed,
                multiplier=mult, is_dangerous=is_dangerous, is_proven=proven,
            )

        return cls(buckets=buckets, baseline_accuracy=baseline)

    @classmethod
    def _noop(cls) -> "ConfidenceCalibrator":
        return cls(buckets={}, baseline_accuracy=0.52)

    # ------------------------------------------------------------------
    # Single-row calibration
    # ------------------------------------------------------------------

    def calibrate(
        self,
        raw_confidence: float,
        quality_tier: Optional[float],
        vix_regime: Optional[str],
        sector_regime: Optional[str],
        above_sma200: Optional[float],
        jarvis_green: Optional[float],
    ) -> dict:
        """
        Return calibration result dict for one prediction row.

        Keys: raw_confidence, calibrated_confidence, confidence_context,
              confidence_sample_size, confidence_adjustment_reason
        """
        key = _build_context_key(
            quality_tier=str(int(quality_tier)) if quality_tier is not None and not math.isnan(quality_tier) else None,
            vix_regime=vix_regime,
            sector_regime=sector_regime,
            above_sma200=str(bool(above_sma200 > 0.5)) if above_sma200 is not None and not math.isnan(above_sma200) else None,
            jarvis_green=str(bool(jarvis_green > 0)) if jarvis_green is not None and not math.isnan(jarvis_green) else None,
        )

        stats = self.buckets.get(key)

        if stats is None or stats.n < MIN_N:
            multiplier  = 1.0
            sample_size = stats.n if stats else 0
            reason      = "fallback_baseline: insufficient_history" if (stats is None or stats.n < MIN_N) else "baseline"
        else:
            multiplier  = stats.multiplier
            sample_size = stats.n
            delta_pct   = (stats.smoothed - self.baseline_accuracy) * 100
            direction   = "boost" if multiplier > 1.0 else ("penalty" if multiplier < 1.0 else "neutral")
            reason_parts = [f"{direction}({multiplier:.2f}x)"]
            reason_parts.append(f"hist_acc={stats.smoothed:.3f}")
            reason_parts.append(f"baseline={self.baseline_accuracy:.3f}")
            reason_parts.append(f"delta={delta_pct:+.1f}%")
            if stats.is_dangerous and not stats.is_proven:
                reason_parts.append("dangerous_ctx_capped")
            reason = " ".join(reason_parts)

        calibrated = float(np.clip(raw_confidence * multiplier, 0.0, 1.0))

        return {
            "raw_confidence":             float(raw_confidence),
            "calibrated_confidence":      calibrated,
            "confidence_context":         key,
            "confidence_sample_size":     sample_size,
            "confidence_adjustment_reason": reason,
        }

    # ------------------------------------------------------------------
    # DataFrame-level application
    # ------------------------------------------------------------------

    def apply(self, preds: pd.DataFrame, parquet_df: pd.DataFrame) -> pd.DataFrame:
        """
        Merge parquet context columns into preds, compute calibrated confidence,
        and return preds enriched with calibration columns.

        parquet_df must have ticker as key column and optionally:
            quality_tier, jarvis_quality_adjusted, realized_vol_20, market_trend, above_sma200
        preds must have ticker column and confidence column.
        """
        # Pull context cols from parquet
        ctx_cols = ["ticker", "quality_tier", "jarvis_quality_adjusted",
                    "realized_vol_20", "market_trend", "above_sma200"]
        avail = [c for c in ctx_cols if c in parquet_df.columns]
        ctx = parquet_df[avail].copy()

        merged = preds.merge(ctx, on="ticker", how="left")

        results = []
        for _, row in merged.iterrows():
            raw_conf = float(row.get("confidence", 0.0) or 0.0)

            qt   = _safe_float(row.get("quality_tier"))
            rv20 = _safe_float(row.get("realized_vol_20"))
            mt   = _safe_float(row.get("market_trend"))
            sma  = _safe_float(row.get("above_sma200"))
            jarv = _safe_float(row.get("jarvis_quality_adjusted"))

            vix = _vix_regime(rv20) if rv20 is not None else None
            sec = _sector_regime(mt) if mt is not None else None

            results.append(self.calibrate(raw_conf, qt, vix, sec, sma, jarv))

        cal_df = pd.DataFrame(results, index=preds.index)

        for col in ["raw_confidence", "calibrated_confidence",
                    "confidence_context", "confidence_sample_size",
                    "confidence_adjustment_reason"]:
            preds = preds.copy()
            preds[col] = cal_df[col].values

        return preds

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def summary(self) -> dict:
        if not self.buckets:
            return {"status": "noop", "baseline": self.baseline_accuracy, "buckets": 0}
        multipliers = [b.multiplier for b in self.buckets.values()]
        return {
            "status":          "active",
            "baseline":        round(self.baseline_accuracy, 4),
            "buckets":         len(self.buckets),
            "boosted":         sum(1 for m in multipliers if m > 1.0),
            "penalised":       sum(1 for m in multipliers if m < 1.0),
            "avg_multiplier":  round(float(np.mean(multipliers)), 4),
            "max_multiplier":  round(max(multipliers), 4),
            "min_multiplier":  round(min(multipliers), 4),
        }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _smooth(accuracy: float, n: int, baseline: float) -> float:
    """Bayesian smoothing: pull small-n estimates toward baseline."""
    return (n * accuracy + SMOOTHING_ALPHA * baseline) / (n + SMOOTHING_ALPHA)


def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None
