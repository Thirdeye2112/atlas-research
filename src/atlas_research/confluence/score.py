"""Final confluence score computation (0-100)."""
from __future__ import annotations

from atlas_research.confluence.alignment import AlignmentResult
from atlas_research.confluence.components.base import ComponentResult
from atlas_research.confluence.components import regime as regime_mod


def compute_score(
    components: list[ComponentResult],
    alignment: AlignmentResult,
) -> float:
    """
    Returns a 0-100 quality score measuring how strongly historically validated
    signals agree on a direction.

    NOT a directional score — 80 can be bullish or bearish.
    80-100: multiple strong signals tightly aligned, good regime fit, low risk
    60-80 : moderate agreement, some divergence
    40-60 : weak or mixed signals
    0-40  : few signals available, strong disagreement, or high risk
    """
    non_risk = [c for c in components if c.available and c.name != "risk"]

    if not non_risk:
        return 0.0

    if alignment.dominant_direction == 0:
        # No consensus direction = low confidence regardless of individual signal strength
        base = 20.0 + max(0.0, 20.0 - alignment.conflicting_count * 4.0)
        return _apply_risk_penalty(base, components)

    # Weighted average strength of components aligned with dominant direction
    aligned = [
        c for c in non_risk
        if c.direction == alignment.dominant_direction and c.name != "regime"
    ]
    if not aligned:
        return _apply_risk_penalty(20.0, components)

    total_w  = sum(c.weight for c in aligned)
    avg_str  = sum(c.strength * c.weight for c in aligned) / total_w if total_w else 0

    # Alignment quality: what fraction of available signals agree?
    align_q  = alignment.alignment_ratio

    # Base score: blend of signal strength and alignment breadth
    base = (0.65 * avg_str + 0.35 * align_q) * 100.0

    # Regime fitness multiplier: does the market environment suit the direction?
    regime_comp = next((c for c in components if c.name == "regime" and c.available), None)
    fitness = regime_mod.direction_fitness(
        regime_comp, alignment.dominant_direction
    ) if regime_comp else 0.90
    regime_adjusted = base * fitness

    return _apply_risk_penalty(regime_adjusted, components)


def _apply_risk_penalty(score: float, components: list[ComponentResult]) -> float:
    risk = next((c for c in components if c.name == "risk" and c.available), None)
    if risk is None:
        return max(0.0, min(100.0, score))
    penalty = float(risk.details.get("total_penalty", 0.0))
    return max(0.0, min(100.0, score - penalty))
