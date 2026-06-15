"""Regime component: classifies the current market environment."""
from __future__ import annotations

from datetime import date

from atlas_research.confluence.components.base import ComponentResult

WEIGHT = 0.15

# How much the regime favours the predicted direction
# (multiplier applied to the pre-regime score in score.py)
_REGIME_FITNESS = {
    # (market_regime, signal_direction): fitness multiplier
    ("bull",    +1): 1.00,
    ("bull",    -1): 0.72,   # short signals in bull market: lower quality
    ("bull",     0): 0.85,
    ("bear",    -1): 1.00,
    ("bear",    +1): 0.72,
    ("bear",     0): 0.85,
    ("range",   +1): 0.88,
    ("range",   -1): 0.88,
    ("range",    0): 0.80,
}


def compute(ticker: str, snap_date: date, feature_row: dict) -> ComponentResult:
    """
    Derives market regime from feature row values and returns a ComponentResult
    capturing current environmental conditions.  Also exposes `direction_fitness`
    in details so score.py can apply regime penalty.
    """
    spy_above = _safe_float(feature_row.get("spy_above_sma200"))
    mkt_trend = _safe_float(feature_row.get("market_trend"))
    rv20      = _safe_float(feature_row.get("realized_vol_20"))
    rv60      = _safe_float(feature_row.get("realized_vol_60"))

    if spy_above is None and mkt_trend is None:
        return ComponentResult.unavailable("regime", WEIGHT)

    # Market regime
    if mkt_trend is not None:
        if mkt_trend > 0:
            market_regime = "bull"
        elif mkt_trend < 0:
            market_regime = "bear"
        else:
            market_regime = "range"
    elif spy_above is not None:
        market_regime = "bull" if spy_above > 0.5 else "bear"
    else:
        market_regime = "range"

    # Volatility regime
    if rv20 is not None and rv60 is not None:
        vol_regime = "high_vol" if rv20 > rv60 * 1.25 else "low_vol"
    else:
        vol_regime = "unknown"

    # SPY position
    above_200 = (spy_above is not None and spy_above > 0.5)

    # The regime itself provides a directional signal
    if market_regime == "bull" and above_200:
        signal, direction = "bullish", +1
    elif market_regime == "bear" and not above_200:
        signal, direction = "bearish", -1
    else:
        signal, direction = "neutral", 0

    strength = 0.7 if direction != 0 else 0.3
    score    = 65.0 if direction != 0 else 40.0

    return ComponentResult(
        name="regime", signal=signal, direction=direction,
        strength=strength, score=score, weight=WEIGHT, available=True,
        details={
            "market_regime": market_regime,
            "vol_regime": vol_regime,
            "spy_above_sma200": spy_above,
            "market_trend": mkt_trend,
            # direction_fitness is read by score.py after alignment is determined
            "fitness_table": _REGIME_FITNESS,
        },
    )


def direction_fitness(regime_result: ComponentResult, dominant_direction: int) -> float:
    """Returns the regime fitness multiplier for the dominant signal direction."""
    if not regime_result.available:
        return 0.90   # no regime data — moderate penalty
    mkt = regime_result.details.get("market_regime", "range")
    table = regime_result.details.get("fitness_table", _REGIME_FITNESS)
    return table.get((mkt, dominant_direction), 0.85)


def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
