"""
Atlas Prediction Error Attribution System
==========================================
Closes the learning loop by tracking predictions against realized outcomes,
classifying why predictions succeeded or failed, and computing rolling signal
reliability to feed adaptive weighting recommendations.

Pipeline (run nightly after labels are computed):
    1. tracker.record_predictions_from_snapshots()  -- capture today's scores
    2. outcomes.compute_matured_outcomes()          -- fill actual returns (horizon elapsed)
    3. classifier.attribute_errors()                -- classify each matured outcome
    4. reliability.compute_signal_reliability()     -- rolling metrics per signal
    5. recommendations.generate_recommendations()   -- adaptive weight suggestions

All recommendations are stored and require human review before any weight changes.
"""
from atlas_research.attribution.tracker import record_prediction, record_predictions_from_snapshots
from atlas_research.attribution.outcomes import compute_matured_outcomes
from atlas_research.attribution.classifier import attribute_errors
from atlas_research.attribution.reliability import compute_signal_reliability
from atlas_research.attribution.recommendations import generate_recommendations

__all__ = [
    "record_prediction",
    "record_predictions_from_snapshots",
    "compute_matured_outcomes",
    "attribute_errors",
    "compute_signal_reliability",
    "generate_recommendations",
]
