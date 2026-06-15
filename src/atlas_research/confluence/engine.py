"""
Atlas Confluence Engine v1
Orchestrates 6 signal components and produces a 0-100 quality score
measuring how many historically validated signals agree.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd

from atlas_research.confluence import repository
from atlas_research.confluence.alignment import compute_alignment
from atlas_research.confluence.components import ml, pattern, probability, feature_ic, regime, risk
from atlas_research.confluence.score import compute_score
from atlas_research.utils.logging import get_logger

log = get_logger(__name__)

ENGINE_VERSION = "v1"


def score_ticker(
    ticker: str,
    snap_date: date,
    feature_row: dict,
    run_id: int,
) -> dict:
    """
    Score a single ticker and persist the result.

    Parameters
    ----------
    ticker      : ticker symbol
    snap_date   : date to score
    feature_row : flat dict of feature values from the parquet file
    run_id      : ID of the current scoring run

    Returns
    -------
    dict with confluence_score, confluence_direction, and component breakdown
    """
    # Determine current market regime (needed by feature_ic and regime component)
    regime_result = regime.compute(ticker, snap_date, feature_row)
    current_regime = regime_result.details.get("market_regime", "range")
    vol_regime_str = regime_result.details.get("vol_regime")

    # Map market regime to feature_regime_performance regime name
    spy_above = feature_row.get("spy_above_sma200")
    if spy_above is not None:
        try:
            spy_above = float(spy_above)
            regime_key = "above_200dma" if spy_above > 0.5 else "below_200dma"
        except (TypeError, ValueError):
            regime_key = current_regime
    else:
        regime_key = current_regime

    # Compute all components
    ml_result          = ml.compute(ticker, snap_date)
    pattern_result     = pattern.compute(ticker, snap_date, feature_row)
    probability_result = probability.compute(ticker, snap_date, feature_row)
    feature_ic_result  = feature_ic.compute(ticker, snap_date, feature_row, regime_key)
    risk_result        = risk.compute(ticker, snap_date, feature_row)

    components = [
        ml_result,
        pattern_result,
        probability_result,
        feature_ic_result,
        regime_result,
        risk_result,
    ]

    alignment    = compute_alignment(components)
    final_score  = compute_score(components, alignment)

    # Pull ML fields for snapshot summary
    ml_prob    = ml_result.details.get("probability_positive") if ml_result.available else None
    ml_exp_ret = ml_result.details.get("expected_return")      if ml_result.available else None
    risk_level = risk_result.details.get("risk_level")         if risk_result.available else None

    # Persist snapshot
    snapshot_id = repository.upsert_snapshot(
        run_id=run_id,
        ticker=ticker,
        snap_date=snap_date,
        score=final_score,
        direction=alignment.dominant_signal,
        ml_prob=ml_prob,
        ml_exp_ret=ml_exp_ret,
        risk_level=risk_level,
        aligned=alignment.aligned_count,
        conflicting=alignment.conflicting_count,
        neutral=alignment.neutral_count,
        total=alignment.total_available,
        market_regime=current_regime,
        vol_regime=vol_regime_str,
        engine_version=ENGINE_VERSION,
    )
    repository.upsert_components(snapshot_id, ticker, snap_date, components)

    log.info(
        "confluence.scored",
        ticker=ticker,
        date=str(snap_date),
        score=round(final_score, 1),
        direction=alignment.dominant_signal,
        aligned=alignment.aligned_count,
        conflicting=alignment.conflicting_count,
    )

    return {
        "ticker":               ticker,
        "snapshot_date":        str(snap_date),
        "confluence_score":     round(final_score, 2),
        "confluence_direction": alignment.dominant_signal,
        "aligned_signals":      alignment.aligned_count,
        "conflicting_signals":  alignment.conflicting_count,
        "components": {
            c.name: {
                "signal": c.signal,
                "strength": round(c.strength, 3),
                "score": round(c.score, 1),
                "available": c.available,
            }
            for c in components
        },
    }


def run_confluence(
    snap_date: date,
    parquet_dir: Path,
    tickers: list[str] | None = None,
    notes: str | None = None,
) -> pd.DataFrame:
    """
    Score all (or selected) tickers in the parquet for snap_date.

    Returns a DataFrame of scored tickers sorted by confluence_score DESC.
    """
    fpath = parquet_dir / f"feature_matrix_{snap_date.isoformat()}.parquet"
    if not fpath.exists():
        log.error("confluence.no_parquet", date=str(snap_date), path=str(fpath))
        return pd.DataFrame()

    df = pd.read_parquet(fpath, engine="pyarrow")
    if tickers:
        df = df[df["ticker"].isin(tickers)]

    if df.empty:
        log.warning("confluence.empty_parquet", date=str(snap_date))
        return pd.DataFrame()

    run_id = repository.create_run(snap_date, ENGINE_VERSION, notes)
    results = []

    for _, row in df.iterrows():
        ticker = str(row.get("ticker", ""))
        if not ticker:
            continue
        try:
            feature_row = row.to_dict()
            result = score_ticker(ticker, snap_date, feature_row, run_id)
            results.append(result)
        except Exception as exc:
            log.error("confluence.ticker_error", ticker=ticker, error=str(exc))

    repository.update_run_count(run_id, len(results))
    log.info("confluence.run_complete", date=str(snap_date), scored=len(results), run_id=run_id)

    if not results:
        return pd.DataFrame()

    out = pd.DataFrame([{
        "ticker":               r["ticker"],
        "confluence_score":     r["confluence_score"],
        "confluence_direction": r["confluence_direction"],
        "aligned_signals":      r["aligned_signals"],
        "conflicting_signals":  r["conflicting_signals"],
    } for r in results])
    return out.sort_values("confluence_score", ascending=False).reset_index(drop=True)
