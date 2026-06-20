"""
Atlas Conviction Layer
======================
Computes conviction_score (0-100) and conviction_level as first-class
outputs alongside confluence_score.

Does NOT change confluence score weights, component logic, or formula.

Design
------
Primary driver  : alignment_count — how many components agree on a direction.
                  Research confirmed this is more predictive than score bucket.
Secondary inputs: ML confidence, probability endorsement, feature IC agreement,
                  regime context. These differentiate quality within a tier.

Levels
------
VERY_HIGH : score >= 68  (all 4-5 aligned, non-neutral dominant direction)
HIGH      : score >= 51  (all 3-aligned, non-neutral dominant direction)
MODERATE  : score >= 34  (all 2-aligned)
LOW       : score <  34  (0-1 aligned, or high-aligned with neutral direction)

Vectorized form is used in the backtest; single-ticker form integrates with
the live confluence engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

# ── Level thresholds ────────────────────────────────────────────────────────────
VERY_HIGH_THRESH: float = 68.0   # min score for 4-aligned: (4/5)*100*0.85 = 68
HIGH_THRESH:      float = 51.0   # min score for 3-aligned: (3/5)*100*0.85 = 51
MODERATE_THRESH:  float = 34.0   # min score for 2-aligned: (2/5)*100*0.85 = 34

LEVEL_ORDER: list[str] = ["LOW", "MODERATE", "HIGH", "VERY_HIGH"]

# Alignment count drives 85% of the score; quality modifies the remaining 15%.
# This ensures tier placement is dominated by how many components agree,
# not by secondary quality indicators (which avoids the inverse-ordering bug where
# additive bonuses could push weak-ML 3-aligned stocks into the same tier as
# strong 4-aligned stocks).
_ALIGN_WEIGHT:   float = 0.85
_QUALITY_WEIGHT: float = 0.15

# Neutrality penalty: no consensus direction → halve the score
_NEUTRAL_MULT: float = 0.50

# Kept for backward compatibility (no longer used in formula)
_COUNT_BASE: list[float] = [0.0, 15.0, 30.0, 48.0, 65.0, 80.0]


@dataclass
class ConvictionResult:
    """Per-ticker conviction output — additive to, not replacing, confluence output."""
    ticker: str
    conviction_score: float
    conviction_level: str
    supporting_signals: list[dict[str, Any]] = field(default_factory=list)
    conflicting_signals: list[dict[str, Any]] = field(default_factory=list)
    neutral_signals: list[str] = field(default_factory=list)
    # Populated when level_stats are supplied (from prior backtest run)
    historical_hit_rate: float | None = None
    historical_expectancy: float | None = None
    sample_size: int | None = None


def get_level(score: float) -> str:
    """Map a conviction score (0-100) to its level label."""
    if score >= VERY_HIGH_THRESH:
        return "VERY_HIGH"
    if score >= HIGH_THRESH:
        return "HIGH"
    if score >= MODERATE_THRESH:
        return "MODERATE"
    return "LOW"


# ── Vectorized form (for backtest) ──────────────────────────────────────────────

def compute_conviction_vec(
    aligned_count: np.ndarray,
    dominant_dir:  np.ndarray,    # +1 bull, -1 bear, 0 neutral
    ml_prob:       np.ndarray,    # [0,1] raw probability output
    ml_rank:       np.ndarray,    # [0,1] cross-sectional rank percentile
    prob_dir:      np.ndarray,    # probability component direction (-1/0/+1)
    feat_ic_dir:   np.ndarray,    # feature IC component direction
    regime_dir:    np.ndarray,    # regime component direction
    regime_avail:  np.ndarray,    # bool: regime data available for this row
) -> tuple[np.ndarray, np.ndarray]:
    """
    Vectorized conviction score for all rows in a scored DataFrame.

    Returns
    -------
    conviction_score : float ndarray, shape (n,), values 0-100
    conviction_level : str ndarray, shape (n,), "LOW"/"MODERATE"/"HIGH"/"VERY_HIGH"
    """
    # 1. Alignment base: primary driver (85% weight, 0-100 pts)
    #    Scaled linearly by fraction of max components (5).
    #    Anchors tier placement firmly to alignment count:
    #      0→0, 1→20, 2→40, 3→60, 4→80, 5→100
    #    This prevents quality modifiers from inverting tier ordering
    #    (e.g. a weak 3-aligned stock should never score above a 4-aligned stock).
    ac         = np.clip(aligned_count, 0, 5).astype(int)
    align_base = (ac / 5.0) * 100.0

    # 2. Quality score: secondary modifier (15% weight, 0-100 pts)

    # ML confidence (0-40 pts): rewards distance from neutral prob and extreme rank.
    ml_dist   = np.clip(np.abs(ml_prob - 0.5), 0.0, 0.5)
    rank_dist = np.clip(np.abs(ml_rank - 0.5), 0.0, 0.5)
    ml_str    = 0.6 * ml_dist * 2.0 + 0.4 * rank_dist * 2.0   # [0, 1]

    # Probability component endorsement (0-25 pts):
    # fires for rank_pct in [40%, 80%) — partial independence from ML threshold.
    prob_endorses = (dominant_dir != 0) & (prob_dir == dominant_dir)

    # Feature IC endorsement (0-20 pts): regime-calibrated IC features agree.
    ic_endorses = (dominant_dir != 0) & (feat_ic_dir == dominant_dir)

    # Regime quality (0-15 pts): 1.0=agrees, 0.5=neutral, 0.0=conflicts.
    regime_agrees    = regime_avail & (dominant_dir != 0) & (regime_dir == dominant_dir)
    regime_conflicts = regime_avail & (dominant_dir != 0) & (regime_dir == -dominant_dir)
    regime_q = np.where(regime_agrees, 1.0, np.where(regime_conflicts, 0.0, 0.5))

    quality_score = (
        ml_str                        * 40.0
        + prob_endorses.astype(float) * 25.0
        + ic_endorses.astype(float)   * 20.0
        + regime_q                    * 15.0
    )  # [0, 100]

    # 3. Combine: alignment dominates, quality refines within tier
    raw_combined = _ALIGN_WEIGHT * align_base + _QUALITY_WEIGHT * quality_score

    # 4. Neutral penalty: no directional consensus → inherently LOW conviction
    neutral_mult = np.where(dominant_dir == 0, _NEUTRAL_MULT, 1.0)

    score = np.round(np.clip(raw_combined * neutral_mult, 0.0, 100.0), 2)

    level = np.where(score >= VERY_HIGH_THRESH, "VERY_HIGH",
            np.where(score >= HIGH_THRESH,      "HIGH",
            np.where(score >= MODERATE_THRESH,  "MODERATE", "LOW")))

    return score, level


# ── Single-ticker form (for live confluence engine) ─────────────────────────────

def compute_conviction(
    components: list,    # list[ComponentResult]
    alignment,           # AlignmentResult
    ticker: str = "",
    level_stats: dict | None = None,
) -> ConvictionResult:
    """
    Single-ticker conviction computation for integration with the live engine.

    Parameters
    ----------
    components   : component results from confluence engine
    alignment    : AlignmentResult from compute_alignment()
    ticker       : ticker symbol
    level_stats  : optional dict of {level: {hit_rate_5d, avg_return_5d, n}}
                   for historical context (pre-computed from a prior backtest run)
    """
    dom_dir  = alignment.dominant_direction
    comp_map = {c.name: c for c in components}

    ml_c  = comp_map.get("ml")
    pb_c  = comp_map.get("probability")
    ic_c  = comp_map.get("feature_ic")
    rg_c  = comp_map.get("regime")

    ml_prob   = float(ml_c.details.get("probability_positive", 0.5)) if ml_c  and ml_c.available  else 0.5
    ml_rank   = float(ml_c.details.get("rank_percentile",      0.5)) if ml_c  and ml_c.available  else 0.5
    prob_dir  = pb_c.direction if pb_c and pb_c.available else 0
    feat_dir  = ic_c.direction if ic_c and ic_c.available else 0
    reg_dir   = rg_c.direction if rg_c and rg_c.available else 0
    reg_avail = rg_c is not None and rg_c.available

    score_arr, level_arr = compute_conviction_vec(
        aligned_count = np.array([alignment.aligned_count]),
        dominant_dir  = np.array([dom_dir]),
        ml_prob       = np.array([ml_prob]),
        ml_rank       = np.array([ml_rank]),
        prob_dir      = np.array([prob_dir]),
        feat_ic_dir   = np.array([feat_dir]),
        regime_dir    = np.array([reg_dir]),
        regime_avail  = np.array([reg_avail]),
    )
    score = float(score_arr[0])
    level = str(level_arr[0])

    # Build human-readable evidence lists
    supporting, conflicting, neutral = [], [], []
    for c in components:
        if c.name == "risk" or not c.available:
            continue
        if c.direction == dom_dir and dom_dir != 0:
            supporting.append({
                "name":     c.name,
                "signal":   c.signal,
                "strength": round(c.strength, 3),
                "note":     _component_note(c),
            })
        elif c.direction == -dom_dir and dom_dir != 0:
            conflicting.append({
                "name":     c.name,
                "signal":   c.signal,
                "strength": round(c.strength, 3),
                "note":     _component_note(c),
            })
        else:
            neutral.append(c.name)

    hr = exp_ret = n_hist = None
    if level_stats and level in level_stats:
        s      = level_stats[level]
        hr     = s.get("hit_rate_5d")
        exp_ret = s.get("avg_return_5d")
        n_hist = s.get("n")

    return ConvictionResult(
        ticker=ticker,
        conviction_score=round(score, 2),
        conviction_level=level,
        supporting_signals=supporting,
        conflicting_signals=conflicting,
        neutral_signals=neutral,
        historical_hit_rate=hr,
        historical_expectancy=exp_ret,
        sample_size=n_hist,
    )


def _component_note(c) -> str:
    if c.name == "ml":
        prob = c.details.get("probability_positive", "?")
        rank = c.details.get("rank_percentile", "?")
        return f"prob={float(prob):.2f}, rank_pct={float(rank):.2f}"
    if c.name == "pattern":
        return f"strength={c.strength:.2f}"
    if c.name == "probability":
        return f"rank-tier signal ({c.strength:.2f} weight fraction)"
    if c.name == "feature_ic":
        bull = c.details.get("bullish_ic_weight", "?")
        return f"{float(bull):.0%} of regime IC features agree"
    if c.name == "regime":
        mr = c.details.get("market_regime", "?")
        return f"{mr} market environment"
    return ""
