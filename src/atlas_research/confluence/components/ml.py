"""ML component: derives a signal from the predictions table."""
from __future__ import annotations

from datetime import date

from sqlalchemy import text

from atlas_research.confluence.components.base import ComponentResult
from atlas_research.db.connection import get_connection

WEIGHT = 0.30

_BULL_PROB_THRESH  = 0.55
_BEAR_PROB_THRESH  = 0.45
_STRONG_RANK_HIGH  = 0.80   # top quintile = strong bullish
_STRONG_RANK_LOW   = 0.20   # bottom quintile = strong bearish


def compute(ticker: str, snap_date: date) -> ComponentResult:
    """
    Queries the predictions table for the most recent model output on snap_date.
    Returns a ComponentResult representing the ML signal.
    """
    sql = text("""
        SELECT probability_positive, expected_return, confidence, rank_percentile
        FROM predictions
        WHERE ticker = :ticker
          AND date  = :date
        ORDER BY model_version DESC
        LIMIT 1
    """)
    with get_connection() as conn:
        row = conn.execute(sql, {"ticker": ticker, "date": snap_date}).fetchone()

    if row is None:
        return ComponentResult.unavailable("ml", WEIGHT)

    prob, exp_ret, confidence, rank_pct = (
        float(row[0] or 0.5),
        float(row[1] or 0.0),
        float(row[2] or 0.0),
        float(row[3] or 0.5),
    )

    if prob >= _BULL_PROB_THRESH:
        signal, direction = "bullish", +1
    elif prob <= _BEAR_PROB_THRESH:
        signal, direction = "bearish", -1
    else:
        signal, direction = "neutral", 0

    # Strength = blend of probability extremeness + cross-sectional rank
    prob_strength  = abs(prob - 0.5) * 2.0            # 0 at 0.5, 1 at 0 or 1
    rank_strength  = abs(rank_pct - 0.5) * 2.0
    strength       = 0.6 * prob_strength + 0.4 * rank_strength

    # Score: quality of the ML signal (penalise uncertainty, reward high rank)
    if direction == +1:
        score = 50.0 + rank_pct * 50.0 * confidence
    elif direction == -1:
        score = 50.0 + (1.0 - rank_pct) * 50.0 * confidence
    else:
        score = 30.0

    return ComponentResult(
        name="ml", signal=signal, direction=direction,
        strength=strength, score=score, weight=WEIGHT, available=True,
        details={
            "probability_positive": round(prob, 4),
            "expected_return": round(exp_ret, 6),
            "confidence": round(confidence, 4),
            "rank_percentile": round(rank_pct, 4),
        },
    )
