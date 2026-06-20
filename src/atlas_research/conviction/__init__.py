"""Atlas Conviction Layer — evidence-based conviction scoring."""
from atlas_research.conviction.engine import (
    ConvictionResult,
    get_level,
    compute_conviction,
    compute_conviction_vec,
    VERY_HIGH_THRESH,
    HIGH_THRESH,
    MODERATE_THRESH,
    LEVEL_ORDER,
)

__all__ = [
    "ConvictionResult",
    "get_level",
    "compute_conviction",
    "compute_conviction_vec",
    "VERY_HIGH_THRESH",
    "HIGH_THRESH",
    "MODERATE_THRESH",
    "LEVEL_ORDER",
]
