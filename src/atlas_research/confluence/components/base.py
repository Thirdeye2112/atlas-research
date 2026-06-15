"""Base types shared across all confluence components."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ComponentResult:
    name: str
    signal: str           # bullish | bearish | neutral
    direction: int        # +1 bull, -1 bear, 0 neutral
    strength: float       # 0.0–1.0  (confidence in this component's signal)
    score: float          # 0–100 quality contribution
    weight: float         # fraction of final score this component controls
    available: bool       # False when required data is absent
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.strength = max(0.0, min(1.0, self.strength))
        self.score    = max(0.0, min(100.0, self.score))

    @classmethod
    def unavailable(cls, name: str, weight: float) -> "ComponentResult":
        return cls(
            name=name, signal="neutral", direction=0,
            strength=0.0, score=0.0, weight=weight, available=False,
        )
