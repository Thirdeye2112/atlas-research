"""Feature IC component: uses per-regime IC stats to assess feature alignment."""
from __future__ import annotations

from datetime import date

from sqlalchemy import text

from atlas_research.confluence.components.base import ComponentResult
from atlas_research.db.connection import get_connection

WEIGHT = 0.10

_IC_SIGNAL_THRESH = 0.008   # min |IC| for a feature to contribute a directional signal
_MIN_FEATURES     = 5       # need at least 5 scoreable features


def compute(
    ticker: str,
    snap_date: date,
    feature_row: dict,
    current_regime: str,
) -> ComponentResult:
    """
    For the current market regime, queries feature_regime_performance to find
    features with meaningful IC. Then checks whether the ticker's current feature
    values point in the expected direction.

    Rules:
    - IC > 0 and feature_value > 0 -> bullish contribution
    - IC > 0 and feature_value < 0 -> bearish contribution
    - IC < 0 (mean reversion): reversed — high value -> bearish, low value -> bullish
    """
    sql = text("""
        SELECT feature_name, mean_ic, rank_ic, sign_stability, classification
        FROM feature_regime_performance
        WHERE regime = :regime
          AND ABS(mean_ic) >= :ic_thresh
          AND classification IN ('Always Useful', 'Regime Sensitive')
        ORDER BY ABS(rank_ic) DESC
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, {
            "regime": current_regime,
            "ic_thresh": _IC_SIGNAL_THRESH,
        }).fetchall()

    if not rows:
        return ComponentResult.unavailable("feature_ic", WEIGHT)

    bullish_ic = 0.0
    bearish_ic = 0.0
    scored      = 0

    for feature_name, mean_ic, rank_ic, sign_stability, classification in rows:
        val = feature_row.get(feature_name)
        if val is None:
            continue
        try:
            val = float(val)
        except (TypeError, ValueError):
            continue

        ic  = float(mean_ic or 0)
        ic_abs = abs(ic)
        scored += 1

        # Positive IC: larger value -> better forward return
        # Negative IC: larger value -> worse forward return (mean reversion)
        sign = 1 if (ic > 0) == (val > 0) else -1
        weighted_ic = ic_abs * sign * float(sign_stability or 0.5)

        if weighted_ic > 0:
            bullish_ic += weighted_ic
        else:
            bearish_ic += abs(weighted_ic)

    if scored < _MIN_FEATURES:
        return ComponentResult.unavailable("feature_ic", WEIGHT)

    total = bullish_ic + bearish_ic
    if total == 0:
        return ComponentResult.unavailable("feature_ic", WEIGHT)

    bull_frac = bullish_ic / total
    bear_frac = bearish_ic / total

    if bull_frac >= 0.60:
        signal, direction = "bullish", +1
    elif bear_frac >= 0.60:
        signal, direction = "bearish", -1
    else:
        signal, direction = "neutral", 0

    strength = abs(bull_frac - bear_frac)
    score    = strength * 100.0 if direction != 0 else 30.0

    return ComponentResult(
        name="feature_ic", signal=signal, direction=direction,
        strength=strength, score=score, weight=WEIGHT, available=True,
        details={
            "regime": current_regime,
            "scored_features": scored,
            "bullish_ic_weight": round(bull_frac, 3),
            "bearish_ic_weight": round(bear_frac, 3),
        },
    )
