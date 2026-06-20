"""
Prediction tracker — writes a prediction_outcomes row for each scored ticker.
Called from the confluence engine or nightly pipeline after score_ticker() runs.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from atlas_research.attribution import repository
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)

# Default horizons to track.  Each prediction is written once per horizon.
DEFAULT_HORIZONS = [5, 10, 20]

_COMPONENT_NAMES = {"ml", "pattern", "probability", "feature_ic", "regime"}


def record_prediction(
    score_result: dict[str, Any],
    snap_date: date,
    snapshot_id: int | None = None,
    horizons: list[int] = DEFAULT_HORIZONS,
    engine_version: str = "v1",
) -> list[int]:
    """
    Record a prediction from a score_ticker() result dict.

    Parameters
    ----------
    score_result : dict returned by confluence.engine.score_ticker()
    snap_date    : the date this score was produced (= prediction_date)
    snapshot_id  : id in confluence_score_snapshots (FK, optional)
    horizons     : list of horizon_days to record (default 5, 10, 20)

    Returns
    -------
    list of inserted prediction_outcomes.id (one per horizon)
    """
    ticker    = score_result.get("ticker", "")
    direction = score_result.get("confluence_direction", "neutral")
    score     = score_result.get("confluence_score")
    conv_level = score_result.get("conviction_level")
    conv_score = score_result.get("conviction_score")

    components = score_result.get("components", {})
    ml_comp    = components.get("ml", {})
    ml_prob    = ml_comp.get("details", {}).get("probability_positive") if isinstance(ml_comp, dict) else None
    exp_ret    = ml_comp.get("details", {}).get("expected_return")       if isinstance(ml_comp, dict) else None

    # Derive signal lists from supporting/conflicting details stored in result
    aligned_names     = [s["name"] for s in score_result.get("supporting_signals", [])
                         if s.get("name") in _COMPONENT_NAMES]
    conflicting_names = [s["name"] for s in score_result.get("conflicting_signal_details", [])
                         if s.get("name") in _COMPONENT_NAMES]
    neutral_names     = [n for n in score_result.get("neutral_signals", [])
                         if n in _COMPONENT_NAMES]

    aligned_cnt    = score_result.get("aligned_signals", len(aligned_names))
    conflicting_cnt = score_result.get("conflicting_signals", len(conflicting_names))

    # Extract regime from components if available
    regime_comp = components.get("regime", {})
    if isinstance(regime_comp, dict):
        regime_details = regime_comp.get("details", {})
        regime     = regime_details.get("market_regime")
        vol_regime = regime_details.get("vol_regime")
    else:
        regime = vol_regime = None

    inserted_ids = []
    for h in horizons:
        row: dict[str, Any] = {
            "ticker":               ticker,
            "prediction_date":      snap_date,
            "horizon_days":         h,
            "predicted_direction":  direction,
            "predicted_probability": ml_prob,
            "expected_return":      exp_ret,
            "confluence_score":     score,
            "conviction_level":     conv_level,
            "conviction_score":     conv_score,
            "aligned_count":        aligned_cnt,
            "conflicting_count":    conflicting_cnt,
            "neutral_count":        len(neutral_names),
            "aligned_signals":      aligned_names or None,
            "conflicting_signals":  conflicting_names or None,
            "neutral_signals":      neutral_names or None,
            "regime":               regime,
            "vol_regime":           vol_regime,
            "quality_tier":         conv_level,   # alias
            "feature_set_version":  "v1",
            "model_version":        "v1",
            "engine_version":       engine_version,
            "snapshot_id":          snapshot_id,
        }
        try:
            row_id = repository.upsert_prediction(row)
            inserted_ids.append(row_id)
        except Exception as exc:
            log.warning("attribution.tracker.skip", ticker=ticker, date=str(snap_date),
                        horizon=h, error=str(exc))

    if inserted_ids:
        log.debug("attribution.tracker.recorded",
                  ticker=ticker, date=str(snap_date), n_horizons=len(inserted_ids))
    return inserted_ids


def record_predictions_from_snapshots(
    snap_date: date,
    engine_version: str = "v1",
    horizons: list[int] = DEFAULT_HORIZONS,
) -> int:
    """
    Backfill prediction_outcomes from the confluence_score_snapshots table.
    Useful for populating historical predictions from already-scored data.
    Returns number of records written.
    """
    from atlas_research.db.connection import get_connection
    from sqlalchemy import text

    sql = text("""
        SELECT
            s.id                        AS snapshot_id,
            s.ticker,
            s.snapshot_date,
            s.confluence_score,
            s.confluence_direction,
            s.confluence_probability,
            s.confluence_expected_return,
            s.aligned_signal_count,
            s.conflicting_signal_count,
            s.neutral_signal_count,
            s.regime,
            s.vol_regime,
            -- conviction fields (may not exist in older snapshots)
            NULL::text                  AS conviction_level,
            NULL::double precision      AS conviction_score
        FROM confluence_score_snapshots s
        WHERE s.snapshot_date = :snap_date
          AND s.engine_version = :ver
    """)

    with get_connection() as conn:
        rows = conn.execute(sql, {"snap_date": snap_date, "ver": engine_version}).fetchall()

    if not rows:
        log.info("attribution.tracker.no_snapshots", date=str(snap_date))
        return 0

    count = 0
    for row in rows:
        (snapshot_id, ticker, snapshot_date, confluence_score, direction,
         ml_prob, exp_ret, aligned_cnt, conflicting_cnt, neutral_cnt,
         regime, vol_regime, conviction_level, conviction_score) = row

        for h in horizons:
            rec: dict[str, Any] = {
                "ticker":               ticker,
                "prediction_date":      snapshot_date,
                "horizon_days":         h,
                "predicted_direction":  direction,
                "predicted_probability": ml_prob,
                "expected_return":      exp_ret,
                "confluence_score":     confluence_score,
                "conviction_level":     conviction_level,
                "conviction_score":     conviction_score,
                "aligned_count":        aligned_cnt,
                "conflicting_count":    conflicting_cnt,
                "neutral_count":        neutral_cnt,
                "aligned_signals":      None,
                "conflicting_signals":  None,
                "neutral_signals":      None,
                "regime":               regime,
                "vol_regime":           vol_regime,
                "quality_tier":         conviction_level,
                "feature_set_version":  "v1",
                "model_version":        "v1",
                "engine_version":       engine_version,
                "snapshot_id":          snapshot_id,
            }
            try:
                repository.upsert_prediction(rec)
                count += 1
            except Exception as exc:
                log.debug("attribution.backfill.skip",
                          ticker=ticker, error=str(exc))

    log.info("attribution.tracker.backfill_complete",
             date=str(snap_date), n=count, horizons=horizons)
    return count
