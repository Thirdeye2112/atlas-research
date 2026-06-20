"""
Adaptive weighting recommendation engine.

Rules (applied per component per window):
  increase_weight   : hit_rate > baseline + 3pp AND n >= 100 AND trend='improving'
  reduce_weight     : hit_rate < baseline - 3pp AND n >= 100 AND trend='degrading'
  invert_signal     : hit_rate < 50% - 3pp AND n >= 100 (anti-correlated)
  require_confirmation: hit_rate near 50% but std is high (inconsistent)
  disable_in_regime : hit_rate < 48% in specific regime with n >= 50
  keep_unchanged    : otherwise

All recommendations are written to adaptive_weight_recommendations with
status='pending'. Humans must explicitly promote them before any weight changes.

Component baseline hit rates (long-run backtest, 2015-2026):
  These are used as reference points for detecting significant deviations.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

import pandas as pd

from atlas_research.attribution import repository
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)

# Baseline expected hit rates per component (from full-period backtest)
_BASELINE_HR: dict[str, float] = {
    "ml":          0.543,
    "pattern":     0.541,
    "probability": 0.542,
    "feature_ic":  0.544,
    "regime":      0.540,
}

# Current confluence weights (from ComponentResult definitions)
_CURRENT_WEIGHTS: dict[str, float] = {
    "ml":          0.30,
    "pattern":     0.20,
    "probability": 0.20,
    "feature_ic":  0.15,
    "regime":      0.10,
}

_IMPROVE_THRESHOLD  = 0.03   # 3pp above baseline = increase_weight candidate
_DEGRADE_THRESHOLD  = 0.03   # 3pp below baseline = reduce_weight candidate
_INVERT_THRESHOLD   = 0.47   # below 47% = anti-correlation
_DISABLE_THRESHOLD  = 0.48   # below 48% in specific regime = disable_in_regime
_MIN_N_GLOBAL       = 100    # min samples for global recommendations
_MIN_N_REGIME       = 50     # min samples for regime-specific recommendations
_WEIGHT_ADJUST_STEP = 0.05   # suggest ±5% weight changes in 5pp steps


def generate_recommendations(
    as_of: date | None = None,
    primary_window: int = 90,
    horizon_days: int = 5,
) -> int:
    """
    Generate adaptive weight recommendations from the latest reliability scores.

    Returns
    -------
    Number of recommendations written.
    """
    if as_of is None:
        as_of = date.today()

    rel_df = repository.get_reliability_snapshot(
        computed_date=as_of,
        window_days=primary_window,
        horizon_days=horizon_days,
    )
    if rel_df.empty:
        log.info("attribution.recommendations.no_reliability_data", as_of=str(as_of))
        return 0

    # Also grab regime-level reliability for disable_in_regime rules
    all_rel_df = _load_reliability_with_regimes(as_of, primary_window, horizon_days)

    count = 0
    for component in _BASELINE_HR:
        baseline = _BASELINE_HR[component]
        weight   = _CURRENT_WEIGHTS.get(component, 0.20)

        # Global recommendation (regime_filter = NULL)
        global_rows = rel_df[
            (rel_df["component_name"] == component) &
            (rel_df["regime_filter"].isna())
        ]
        if not global_rows.empty:
            row      = global_rows.iloc[0]
            hit_rate = _f(row.get("hit_rate"))
            n        = _safe_int(row.get("n_predictions")) or 0
            trend    = str(row.get("trend") or "stable")

            rec = _global_rule(
                component, hit_rate, n, trend, baseline, weight, primary_window
            )
            if rec:
                try:
                    repository.insert_recommendation({
                        **rec,
                        "generated_date": as_of,
                        "horizon_days":   horizon_days,
                        "window_days":    primary_window,
                        "current_weight": weight,
                    })
                    count += 1
                except Exception as exc:
                    log.warning("attribution.recommendations.insert_error",
                                component=component, error=str(exc))

        # Regime-specific recommendations
        if all_rel_df.empty:
            continue
        regime_rows = all_rel_df[
            (all_rel_df["component_name"] == component) &
            (all_rel_df["regime_filter"].notna())
        ]
        for _, r in regime_rows.iterrows():
            hr = _f(r.get("hit_rate"))
            n  = _safe_int(r.get("n_predictions")) or 0
            regime = str(r.get("regime_filter") or "")
            if hr is None or n < _MIN_N_REGIME:
                continue
            if hr < _DISABLE_THRESHOLD:
                rationale = (
                    f"{component} hit_rate={hr:.1%} (n={n}) in {regime} regime "
                    f"is below {_DISABLE_THRESHOLD:.0%} disable threshold "
                    f"(baseline={baseline:.1%})."
                )
                try:
                    repository.insert_recommendation({
                        "generated_date":   as_of,
                        "component_name":   component,
                        "recommendation":   "disable_in_regime",
                        "current_weight":   weight,
                        "suggested_weight": 0.0,
                        "regime_filter":    regime,
                        "horizon_days":     horizon_days,
                        "window_days":      primary_window,
                        "priority":         "normal",
                        "rationale":        rationale,
                        "evidence": {
                            "hit_rate":    round(hr, 4),
                            "n":           n,
                            "baseline_hr": round(baseline, 4),
                            "regime":      regime,
                        },
                    })
                    count += 1
                except Exception as exc:
                    log.warning("attribution.recommendations.regime_error",
                                component=component, regime=regime, error=str(exc))

    log.info("attribution.recommendations.generated",
             as_of=str(as_of), n=count)
    return count


def _global_rule(
    component: str,
    hit_rate: float | None,
    n: int,
    trend: str,
    baseline: float,
    weight: float,
    window: int,
) -> dict[str, Any] | None:
    """Return a recommendation dict or None if no action needed."""
    if hit_rate is None or n < _MIN_N_GLOBAL:
        return None

    delta = hit_rate - baseline

    # Anti-correlated: suggest invert
    if hit_rate < _INVERT_THRESHOLD and n >= _MIN_N_GLOBAL:
        return {
            "component_name":   component,
            "recommendation":   "invert_signal",
            "suggested_weight": weight,  # weight unchanged, signal flipped
            "regime_filter":    None,
            "priority":         "urgent",
            "rationale": (
                f"{component} hit_rate={hit_rate:.1%} (n={n}, window={window}d) "
                f"is anti-correlated with the target (baseline={baseline:.1%}). "
                f"Consider inverting the signal direction before reweighting."
            ),
            "evidence": {
                "hit_rate":    round(hit_rate, 4),
                "n":           n,
                "baseline_hr": round(baseline, 4),
                "delta":       round(delta, 4),
                "trend":       trend,
            },
        }

    # Outperforming: suggest increase
    if delta > _IMPROVE_THRESHOLD and trend == "improving":
        new_weight = round(min(0.45, weight + _WEIGHT_ADJUST_STEP), 3)
        return {
            "component_name":   component,
            "recommendation":   "increase_weight",
            "suggested_weight": new_weight,
            "regime_filter":    None,
            "priority":         "normal",
            "rationale": (
                f"{component} hit_rate={hit_rate:.1%} (+{delta:.1%} vs baseline={baseline:.1%}) "
                f"over {window}d window (n={n}), trend={trend}. "
                f"Signal is outperforming — consider upweighting from {weight:.2f} to {new_weight:.2f}."
            ),
            "evidence": {
                "hit_rate":    round(hit_rate, 4),
                "n":           n,
                "baseline_hr": round(baseline, 4),
                "delta":       round(delta, 4),
                "trend":       trend,
                "current_weight": weight,
                "suggested_weight": new_weight,
            },
        }

    # Underperforming: suggest reduce
    if delta < -_DEGRADE_THRESHOLD and trend == "degrading":
        new_weight = round(max(0.05, weight - _WEIGHT_ADJUST_STEP), 3)
        priority = "urgent" if delta < -0.06 else "normal"
        return {
            "component_name":   component,
            "recommendation":   "reduce_weight",
            "suggested_weight": new_weight,
            "regime_filter":    None,
            "priority":         priority,
            "rationale": (
                f"{component} hit_rate={hit_rate:.1%} ({delta:.1%} vs baseline={baseline:.1%}) "
                f"over {window}d window (n={n}), trend={trend}. "
                f"Signal is underperforming — consider reducing weight from {weight:.2f} to {new_weight:.2f}."
            ),
            "evidence": {
                "hit_rate":    round(hit_rate, 4),
                "n":           n,
                "baseline_hr": round(baseline, 4),
                "delta":       round(delta, 4),
                "trend":       trend,
                "current_weight": weight,
                "suggested_weight": new_weight,
            },
        }

    # Require confirmation: near-baseline but only works with another signal
    if abs(delta) <= 0.01 and n >= _MIN_N_GLOBAL:
        return {
            "component_name":   component,
            "recommendation":   "keep_unchanged",
            "suggested_weight": weight,
            "regime_filter":    None,
            "priority":         "low",
            "rationale": (
                f"{component} hit_rate={hit_rate:.1%} (delta={delta:+.1%} vs baseline, n={n}, "
                f"window={window}d). Performance is stable — no weight change recommended."
            ),
            "evidence": {
                "hit_rate":    round(hit_rate, 4),
                "n":           n,
                "baseline_hr": round(baseline, 4),
                "delta":       round(delta, 4),
                "trend":       trend,
            },
        }

    return None


def _load_reliability_with_regimes(
    as_of: date,
    window: int,
    horizon: int,
) -> pd.DataFrame:
    """Load reliability rows including regime-specific ones."""
    from atlas_research.db.connection import get_connection
    from sqlalchemy import text
    sql = text("""
        SELECT component_name, signal_direction, window_days,
               regime_filter, quality_tier_filter,
               n_predictions, hit_rate, avg_return, ic,
               prior_hit_rate, hit_rate_delta, trend, computed_date::text
        FROM signal_reliability_scores
        WHERE computed_date = :dt
          AND window_days = :window
          AND horizon_days = :horizon
          AND signal_direction = 'all'
          AND regime_filter IS NOT NULL
        ORDER BY component_name, regime_filter
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, {"dt": as_of, "window": window, "horizon": horizon}).fetchall()
    cols = [
        "component_name", "signal_direction", "window_days",
        "regime_filter", "quality_tier_filter",
        "n_predictions", "hit_rate", "avg_return", "ic",
        "prior_hit_rate", "hit_rate_delta", "trend", "computed_date",
    ]
    return pd.DataFrame(rows, columns=cols)


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
