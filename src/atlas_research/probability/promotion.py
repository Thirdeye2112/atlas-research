"""
atlas_research.probability.promotion
--------------------------------------
Signal promotion: evaluate whether a backtest result meets quality criteria
and write passing specs to promoted_signals.

Promotion criteria (defaults)
------------------------------
  min_n          : 30 events minimum
  min_hit_5d     : 55% win rate at 5-day horizon
  min_avg_5d     : +0.3% average return at 5-day horizon
  robustness_req : must pass all robustness checks

Usage
-----
    from atlas_research.probability.promotion import evaluate_promotion, promote_spec

    passed, score, reasons = evaluate_promotion(events, stats, robustness)
    if passed:
        promote_spec(spec_id, score, reasons)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import text

from atlas_research.db.connection import get_connection
from .robustness import RobustnessReport


# ── Criteria ──────────────────────────────────────────────────────────────────

@dataclass
class PromotionCriteria:
    min_n: int = 30
    min_hit_5d: float = 0.55       # fraction (0-1)
    min_avg_5d: float = 0.30       # percent
    require_robustness: bool = True


DEFAULT_CRITERIA = PromotionCriteria()


# ── Evaluation ────────────────────────────────────────────────────────────────

def evaluate_promotion(
    events: list[dict],
    stats: dict,
    robustness: Optional[RobustnessReport],
    criteria: Optional[PromotionCriteria] = None,
    n_override: Optional[int] = None,
) -> tuple[bool, float, list[str]]:
    """
    Evaluate whether a backtest result should be promoted.

    Parameters
    ----------
    events      : per-signal outcome dicts (used for count; may be empty)
    stats       : {horizon: stats_dict} from stats_by_horizon()
    robustness  : RobustnessReport from check_robustness()
    n_override  : use this as event count instead of len(events)

    Returns
    -------
    (promoted: bool, score: float, reasons: list[str])
        reasons is empty when promoted=True; lists failures otherwise.
    """
    if criteria is None:
        criteria = DEFAULT_CRITERIA

    # n_override lets callers avoid storing full events list
    n    = n_override if n_override is not None else (
               robustness.n_events if robustness is not None
               else (stats.get(5, {}).get("n") or len(events))
           )
    s5   = stats.get(5, {})
    hr5  = s5.get("hit_rate")  or 0.0
    avg5 = s5.get("avg_return") or 0.0

    failures: list[str] = []

    if n < criteria.min_n:
        failures.append(f"n={n} < {criteria.min_n}")

    if hr5 < criteria.min_hit_5d:
        failures.append(f"5d hit rate {hr5*100:.1f}% < {criteria.min_hit_5d*100:.0f}%")

    if avg5 < criteria.min_avg_5d:
        failures.append(f"5d avg return {avg5:.2f}% < {criteria.min_avg_5d:.2f}%")

    if criteria.require_robustness:
        if robustness is None:
            failures.append("robustness not evaluated")
        elif not robustness.passed:
            failures.extend(robustness.reasons_failed)

    promoted = len(failures) == 0

    # Score (0-100): weight hit rate, avg return, N, robustness
    import math
    if n > 0 and avg5 > 0 and hr5 > 0:
        raw_score = avg5 * hr5 * 100 * math.log2(n + 1)
        rob_bonus = 1.0 if (robustness and robustness.passed) else 0.7
        score = round(min(raw_score * rob_bonus, 100.0), 2)
    else:
        score = 0.0

    return promoted, score, failures


# ── DB persistence ────────────────────────────────────────────────────────────

def promote_spec(
    spec_id: int,
    ticker: str,
    score: float,
    reasons: list[str],
    recent_signal_date: Optional[str] = None,
    exploratory: bool = False,
) -> bool:
    """
    Mark a spec as promoted in backtest_runs and optionally add to
    promoted_signals.

    Guard: refuses to write promoted_signals with n < 30 unless
    exploratory=True. Non-exploratory promotions with small samples raise
    ValueError so the caller can catch and re-classify the signal.

    Parameters
    ----------
    exploratory : if True, save with signal_status='exploratory' even if n<30
    """
    notes = "; ".join(reasons) if reasons else "passed all criteria"

    with get_connection() as conn:
        # ── n < 30 guard ──────────────────────────────────────────────────────
        run_row = conn.execute(text("""
            SELECT n_events FROM backtest_runs
            WHERE spec_id = :sid
            ORDER BY run_date DESC, id DESC
            LIMIT 1
        """), {"sid": spec_id}).fetchone()

        n_events = int(run_row[0]) if run_row else 0

        if n_events < 30 and not exploratory:
            raise ValueError(
                f"promote_spec: spec_id={spec_id} has n={n_events} < 30. "
                f"Call with exploratory=True to save as an exploratory signal."
            )

        status = "exploratory" if (exploratory or n_events < 30) else "promoted"

        # ── Mark the most recent run as promoted ──────────────────────────────
        conn.execute(text("""
            UPDATE backtest_runs
            SET promoted = TRUE, promoted_at = now(),
                robustness_notes = :notes
            WHERE spec_id = :sid
              AND id = (
                  SELECT id FROM backtest_runs
                  WHERE spec_id = :sid
                  ORDER BY run_date DESC, id DESC
                  LIMIT 1
              )
        """), {"sid": spec_id, "notes": notes})

        if recent_signal_date is None:
            return False

        # ── Insert / update promoted_signals ──────────────────────────────────
        row = conn.execute(text("""
            INSERT INTO promoted_signals
                (spec_id, ticker, signal_date, promotion_score,
                 robustness_notes, exploratory, signal_status)
            VALUES (:sid, :ticker, :date, :score, :notes, :expl, :status)
            ON CONFLICT (spec_id, ticker, signal_date) DO UPDATE SET
                promotion_score  = EXCLUDED.promotion_score,
                robustness_notes = EXCLUDED.robustness_notes,
                exploratory      = EXCLUDED.exploratory,
                signal_status    = EXCLUDED.signal_status,
                promoted_at      = now()
            RETURNING id
        """), {
            "sid":    spec_id,
            "ticker": ticker,
            "date":   recent_signal_date,
            "score":  score,
            "notes":  notes,
            "expl":   exploratory or n_events < 30,
            "status": status,
        }).fetchone()

    return row is not None


# ── Console output ────────────────────────────────────────────────────────────

def print_promotion_result(
    label: str,
    promoted: bool,
    score: float,
    reasons: list[str],
) -> None:
    """Print one-line promotion verdict."""
    if promoted:
        print(f"  PROMOTED  {label:<40}  score={score:.1f}")
    else:
        short = reasons[0][:60] if reasons else "?"
        print(f"  REJECTED  {label:<40}  ({short})")
