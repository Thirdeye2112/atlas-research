"""Risk component: penalises low-quality, illiquid, or high-drawdown tickers."""
from __future__ import annotations

from datetime import date

from atlas_research.confluence.components.base import ComponentResult

WEIGHT = 0.05   # risk is a penalty, not a positive contributor

_MAX_PENALTY = 25.0  # maximum points that can be deducted from final score


def compute(ticker: str, snap_date: date, feature_row: dict) -> ComponentResult:
    """
    Computes a risk penalty (0–25) from feature row values.
    A penalty of 0 means no risk flags; 25 means severe risk — deducted from final score.
    The component signal is always 'neutral'; it does not influence direction.
    """
    penalty = 0.0
    flags: list[str] = []

    # 1. Data quality penalty
    dq = _f(feature_row.get("data_quality_score"))
    if dq is not None:
        if dq < 0.70:
            penalty += 10.0; flags.append("low_data_quality")
        elif dq < 0.80:
            penalty += 4.0;  flags.append("moderate_data_quality")

    # 2. Liquidity penalty (dollar volume)
    dv = _f(feature_row.get("dollar_volume_20"))
    if dv is not None:
        if dv < 1_000_000:
            penalty += 10.0; flags.append("illiquid")
        elif dv < 5_000_000:
            penalty += 4.0;  flags.append("low_liquidity")

    # 3. Expected drawdown penalty
    ed = _f(feature_row.get("expected_drawdown"))
    if ed is not None and ed < 0:
        if ed < -0.05:
            penalty += 5.0; flags.append("high_expected_drawdown")
        elif ed < -0.02:
            penalty += 2.0; flags.append("moderate_drawdown")

    # 4. Volatility extreme penalty
    atr = _f(feature_row.get("atr_pct"))
    if atr is not None and atr > 0.06:
        penalty += 3.0; flags.append("extreme_atr")

    penalty = min(penalty, _MAX_PENALTY)

    # Normalise risk to 0-1
    risk_level = penalty / _MAX_PENALTY

    return ComponentResult(
        name="risk", signal="neutral", direction=0,
        strength=risk_level, score=0.0,
        weight=WEIGHT, available=True,
        details={
            "total_penalty": round(penalty, 2),
            "risk_level": round(risk_level, 3),
            "flags": flags,
            "data_quality_score": dq,
            "dollar_volume_20": dv,
            "expected_drawdown": ed,
            "atr_pct": atr,
        },
    )


def _f(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
