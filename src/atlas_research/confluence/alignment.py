"""Alignment engine: counts how many components agree on a direction."""
from __future__ import annotations

from dataclasses import dataclass

from atlas_research.confluence.components.base import ComponentResult


@dataclass
class AlignmentResult:
    dominant_direction: int      # +1 bull, -1 bear, 0 neutral
    dominant_signal: str         # bullish | bearish | neutral
    aligned_count: int           # components agreeing with dominant direction
    conflicting_count: int       # components pointing the other way
    neutral_count: int           # components with no directional signal
    total_available: int

    @property
    def alignment_ratio(self) -> float:
        if self.total_available == 0:
            return 0.0
        return self.aligned_count / self.total_available


def compute_alignment(components: list[ComponentResult]) -> AlignmentResult:
    """
    Counts bullish / bearish / neutral signals from available, non-risk components.
    Risk component is excluded — it is a penalty, not a directional signal.
    """
    active = [c for c in components if c.available and c.name != "risk"]

    bull_weight = sum(c.strength * c.weight for c in active if c.direction == +1)
    bear_weight = sum(c.strength * c.weight for c in active if c.direction == -1)
    bull_count  = sum(1 for c in active if c.direction == +1)
    bear_count  = sum(1 for c in active if c.direction == -1)
    neut_count  = sum(1 for c in active if c.direction == 0)

    if bull_weight > bear_weight * 1.15:
        dominant_dir    = +1
        dominant_signal = "bullish"
        aligned         = bull_count
        conflicting     = bear_count
    elif bear_weight > bull_weight * 1.15:
        dominant_dir    = -1
        dominant_signal = "bearish"
        aligned         = bear_count
        conflicting     = bull_count
    else:
        dominant_dir    = 0
        dominant_signal = "neutral"
        aligned         = max(bull_count, bear_count)
        conflicting     = min(bull_count, bear_count)

    return AlignmentResult(
        dominant_direction=dominant_dir,
        dominant_signal=dominant_signal,
        aligned_count=aligned,
        conflicting_count=conflicting,
        neutral_count=neut_count,
        total_available=len(active),
    )
