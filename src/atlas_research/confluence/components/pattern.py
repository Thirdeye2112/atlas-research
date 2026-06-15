"""Pattern component: historically validated conditional patterns."""
from __future__ import annotations

from datetime import date

from sqlalchemy import text

from atlas_research.confluence.components.base import ComponentResult
from atlas_research.db.connection import get_connection

WEIGHT = 0.20

_HIT_RATE_THRESHOLD = 0.55     # min hit rate to count pattern as signal
_MIN_SAMPLE         = 20       # min historical occurrences


def compute(ticker: str, snap_date: date, feature_row: dict) -> ComponentResult:
    """
    Evaluates conditional patterns against the current ticker's feature state.

    In v1 this queries aggregate statistics from conditional_pattern_results
    and checks which calendar/market-wide patterns are historically significant.
    Ticker-specific pattern triggers are evaluated where feature data is available.
    """
    sql = text("""
        SELECT
            cp.name,
            cp.condition_type,
            cp.condition_params,
            cpr.hit_rate,
            cpr.avg_return,
            cpr.sample_size
        FROM conditional_patterns cp
        JOIN conditional_pattern_results cpr
          ON cpr.pattern_id = cp.id
         AND cpr.horizon_days = 5
        WHERE cpr.sample_size >= :min_sample
          AND cpr.ticker IS NULL          -- market-wide patterns
        ORDER BY cpr.sample_size DESC
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, {"min_sample": _MIN_SAMPLE}).fetchall()

    if not rows:
        return ComponentResult.unavailable("pattern", WEIGHT)

    bullish_count  = 0
    bearish_count  = 0
    active_count   = 0
    hit_rates: list[float] = []

    for name, condition_type, params, hit_rate, avg_return, sample_size in rows:
        if not _is_triggered(condition_type, params or {}, feature_row):
            continue
        active_count += 1
        if hit_rate is None or avg_return is None:
            continue
        if hit_rate >= _HIT_RATE_THRESHOLD and avg_return > 0:
            bullish_count += 1
            hit_rates.append(float(hit_rate))
        elif hit_rate >= _HIT_RATE_THRESHOLD and avg_return < 0:
            bearish_count += 1
            hit_rates.append(float(hit_rate))

    if active_count == 0:
        return ComponentResult.unavailable("pattern", WEIGHT)

    net = bullish_count - bearish_count
    if net > 0:
        signal, direction = "bullish", +1
    elif net < 0:
        signal, direction = "bearish", -1
    else:
        signal, direction = "neutral", 0

    avg_hit = sum(hit_rates) / len(hit_rates) if hit_rates else 0.5
    aligned  = max(bullish_count, bearish_count)
    strength = min(1.0, aligned / max(active_count, 1) * (avg_hit - 0.5) * 4.0) if direction != 0 else 0.0
    score    = strength * 100.0 if direction != 0 else 30.0

    return ComponentResult(
        name="pattern", signal=signal, direction=direction,
        strength=max(0.0, strength), score=score, weight=WEIGHT, available=True,
        details={
            "active_patterns": active_count,
            "bullish_patterns": bullish_count,
            "bearish_patterns": bearish_count,
            "avg_hit_rate": round(avg_hit, 4),
        },
    )


def _is_triggered(condition_type: str, params: dict, row: dict) -> bool:
    """
    Lightweight pattern trigger evaluation from feature row values.
    Returns True if the pattern condition is satisfied.
    """
    try:
        if condition_type == "consecutive_down":
            n = int(params.get("n_days", 3))
            # return_Nd < 0 means consecutive-down-like
            key = f"return_{n}d" if n <= 5 else "return_5d"
            val = row.get(key)
            return val is not None and float(val) < 0

        if condition_type == "consecutive_up":
            n = int(params.get("n_days", 3))
            key = f"return_{n}d" if n <= 5 else "return_5d"
            val = row.get(key)
            return val is not None and float(val) > 0

        if condition_type == "oversold_rsi":
            thresh = float(params.get("threshold", 30))
            val = row.get("rsi_14")
            return val is not None and float(val) <= thresh

        if condition_type == "overbought_rsi":
            thresh = float(params.get("threshold", 70))
            val = row.get("rsi_14")
            return val is not None and float(val) >= thresh

        if condition_type == "gap_down":
            min_gap = float(params.get("min_gap_pct", 2.0)) / 100.0
            val = row.get("return_1d")
            return val is not None and float(val) <= -min_gap

        if condition_type == "near_52w_low":
            within = float(params.get("within_pct", 5.0)) / 100.0
            val = row.get("dist_52w_low")
            return val is not None and float(val) <= within

        if condition_type == "near_52w_high":
            within = float(params.get("within_pct", 5.0)) / 100.0
            val = row.get("dist_52w_high")
            return val is not None and float(val) <= within

        if condition_type == "high_volume":
            mult = float(params.get("multiplier", 2.0))
            val = row.get("rvol_20")
            return val is not None and float(val) >= mult

    except (TypeError, ValueError, KeyError):
        pass

    return False
