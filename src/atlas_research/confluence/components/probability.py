"""Probability component: signals promoted via the alpha signal calibration pipeline."""
from __future__ import annotations

from datetime import date

from sqlalchemy import text

from atlas_research.confluence.components.base import ComponentResult
from atlas_research.db.connection import get_connection

WEIGHT = 0.20

_MIN_SIGNALS     = 2       # need at least 2 promoted signals for the component to fire
_MIN_HIT_RATE    = 0.55
_MIN_N_RESOLVED  = 30


def compute(ticker: str, snap_date: date, feature_row: dict) -> ComponentResult:
    """
    Queries alpha_signal_calibrations for promoted signals and checks whether
    the ticker's current feature state matches those signals.

    In v1 we read aggregate statistics and infer direction from the majority
    of promoted, statistically robust signals.
    """
    sql = text("""
        SELECT signal_type, signal_key, hit_rate_5d, avg_return_5d,
               n_resolved, sanity_pass, permutation_p_value
        FROM alpha_signal_calibrations
        WHERE status = 'promoted'
          AND sanity_pass = TRUE
          AND n_resolved >= :min_n
          AND hit_rate_5d >= :min_hr
        ORDER BY avg_return_5d DESC
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, {
            "min_n": _MIN_N_RESOLVED,
            "min_hr": _MIN_HIT_RATE,
        }).fetchall()

    if len(rows) < _MIN_SIGNALS:
        return ComponentResult.unavailable("probability", WEIGHT)

    bullish_weight = 0.0
    bearish_weight = 0.0
    total_weight   = 0.0
    active_count   = 0

    for signal_type, signal_key, hit_rate_5d, avg_return_5d, n_resolved, sanity_pass, perm_p in rows:
        if not _signal_active(signal_type, signal_key, feature_row):
            continue
        active_count += 1
        # Weight by hit-rate advantage above 0.5 and sample size
        w = float(hit_rate_5d - 0.5) * min(1.0, float(n_resolved) / 200.0)
        total_weight += abs(w)
        if float(avg_return_5d or 0) > 0:
            bullish_weight += abs(w)
        else:
            bearish_weight += abs(w)

    if active_count < _MIN_SIGNALS or total_weight == 0:
        return ComponentResult.unavailable("probability", WEIGHT)

    bull_frac = bullish_weight / total_weight
    bear_frac = bearish_weight / total_weight

    if bull_frac >= 0.60:
        signal, direction = "bullish", +1
    elif bear_frac >= 0.60:
        signal, direction = "bearish", -1
    else:
        signal, direction = "neutral", 0

    strength = abs(bull_frac - bear_frac)
    score    = strength * 100.0 if direction != 0 else 30.0

    return ComponentResult(
        name="probability", signal=signal, direction=direction,
        strength=strength, score=score, weight=WEIGHT, available=True,
        details={
            "active_signals": active_count,
            "bullish_weight": round(bull_frac, 3),
            "bearish_weight": round(bear_frac, 3),
        },
    )


def _signal_active(signal_type: str, signal_key: str, row: dict) -> bool:
    """
    Returns True if the calibrated signal is currently active for this ticker/date.
    Maps calibration signal_type/signal_key onto available feature row fields.
    """
    try:
        if signal_type == "direction":
            # Atlas direction signal — check current ML/atlas direction proxy
            atlas_dir = row.get("atlas_direction")
            return atlas_dir is not None and str(atlas_dir) == signal_key

        if signal_type == "score_bucket":
            score = row.get("atlas_score") or row.get("rank_percentile")
            if score is None:
                return False
            score = float(score) * 100 if float(score) <= 1.0 else float(score)
            low, high = (float(x) for x in signal_key.split("-"))
            return low <= score <= high

        if signal_type == "pattern":
            patterns = row.get("patterns")
            if patterns is None:
                return False
            pattern_list = patterns if isinstance(patterns, list) else []
            return signal_key in pattern_list

        if signal_type == "exhaustion":
            # Exhaustion signal: check exhaustion_signal column
            ex = row.get("exhaustion_signal")
            return ex is not None and str(ex) == signal_key

        if signal_type == "smart_gate":
            gate = row.get("smart_gate_enter")
            return gate is not None and str(gate).lower() == signal_key.lower()

    except (TypeError, ValueError, KeyError):
        pass

    return False
