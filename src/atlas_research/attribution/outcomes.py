"""
Outcome calculator — fills actual_return, hit_or_miss, max_runup, max_drawdown
once a prediction's horizon has elapsed.

Sources of truth:
  - labels table: return_5d, return_10d, return_20d, max_runup_20d, max_drawdown_20d
  - raw_bars: used for event_gap detection and intra-horizon path metrics
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

import pandas as pd

from atlas_research.attribution import repository
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)

_RETURN_COL = {5: "return_5d", 10: "return_10d", 20: "return_20d"}
_FLAT_THRESHOLD = 0.001   # < 0.1% treated as flat


def _direction_from_return(ret: float | None) -> str:
    if ret is None or math.isnan(ret):
        return "flat"
    if ret > _FLAT_THRESHOLD:
        return "up"
    if ret < -_FLAT_THRESHOLD:
        return "down"
    return "flat"


def _prediction_direction_to_outcome_dir(pred_dir: str) -> str:
    """Map 'bullish'→'up', 'bearish'→'down', 'neutral'→'flat'."""
    return {"bullish": "up", "bearish": "down", "neutral": "flat"}.get(pred_dir, "flat")


def compute_matured_outcomes(
    as_of: date | None = None,
    horizons: list[int] | None = None,
    engine_version: str = "v1",
) -> dict[str, int]:
    """
    Find predictions whose horizon has elapsed and fill in realized outcomes.

    Parameters
    ----------
    as_of    : treat this as 'today' (default: date.today())
    horizons : which horizon buckets to process (default: [5, 10, 20])

    Returns
    -------
    Dict mapping horizon → number of outcomes computed
    """
    if as_of is None:
        as_of = date.today()
    if horizons is None:
        horizons = [5, 10, 20]

    totals: dict[str, int] = {}

    for h in horizons:
        df = repository.get_pending_outcomes(h, as_of)
        if df.empty:
            totals[f"{h}d"] = 0
            continue

        return_col = _RETURN_COL.get(h, "return_5d")
        n_computed = 0

        for _, row in df.iterrows():
            actual_ret = _safe_float(row.get(return_col))
            if actual_ret is None:
                continue  # label not yet available

            actual_dir = _direction_from_return(actual_ret)
            pred_dir   = _prediction_direction_to_outcome_dir(
                str(row.get("predicted_direction", "neutral"))
            )
            hit = (pred_dir != "flat") and (actual_dir == pred_dir)

            pred_prob = _safe_float(row.get("predicted_probability"))
            actual_outcome = 1.0 if (actual_ret is not None and actual_ret > 0) else 0.0
            brier_error = (pred_prob - actual_outcome) ** 2 if pred_prob is not None else None

            # max_runup / max_drawdown — use 20d labels as best available proxy
            max_runup    = _safe_float(row.get("max_runup_20d"))
            max_drawdown = _safe_float(row.get("max_drawdown_20d"))

            outcome_date_val = _outcome_date(row["prediction_date"], h)

            repository.update_outcome(
                outcome_id       = int(row["id"]),
                outcome_date     = outcome_date_val,
                actual_return    = actual_ret,
                actual_direction = actual_dir,
                hit_or_miss      = hit,
                prediction_error = brier_error,
                max_runup        = max_runup,
                max_drawdown     = max_drawdown,
            )
            n_computed += 1

        log.info("attribution.outcomes.computed",
                 horizon=h, n=n_computed, as_of=str(as_of))
        totals[f"{h}d"] = n_computed

    return totals


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _outcome_date(pred_date: Any, horizon_days: int) -> date:
    """Approximate outcome_date as prediction_date + horizon_days (calendar days)."""
    from datetime import timedelta
    if isinstance(pred_date, str):
        pred_date = date.fromisoformat(pred_date)
    elif isinstance(pred_date, pd.Timestamp):
        pred_date = pred_date.date()
    return pred_date + timedelta(days=horizon_days)
