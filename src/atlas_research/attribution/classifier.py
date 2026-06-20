"""
Error classifier — assigns a failure_class to each matured prediction.

Classification priority order (first match wins for is_primary):
  1. event_gap             — large unexpected price gap
  2. model_overconfidence  — high probability but wrong
  3. regime_mismatch       — regime environment contradicted signal
  4. conflicting_signal_ignored — had 2+ conflicting signals
  5. weak_confluence       — score or conviction below useful threshold
  6. momentum_exhaustion   — stock extended at prediction time (RSI)
  7. mean_reversion_failure — predicted reversal but trend continued
  8. low_liquidity_failure — low volume relative to ADV
  9. unknown               — none of the above

Correct predictions receive failure_class='correct' with confidence=1.0.
"""
from __future__ import annotations

import json
import math
from datetime import date
from typing import Any

import pandas as pd

from atlas_research.attribution import repository
from atlas_research.db.connection import get_connection
from atlas_research.utils.logging import get_logger
from sqlalchemy import text

log = get_logger(__name__)

# Thresholds
_EVENT_GAP_THRESHOLD       = 0.04    # > 4% next-day move = event gap
_OVERCONFIDENCE_THRESHOLD  = 0.70    # ML prob > 70% but wrong
_CONFLICTING_SIGNAL_MIN    = 2       # >= 2 conflicting signals
_WEAK_CONFLUENCE_MAX       = 40.0    # score < 40 = weak
_WEAK_CONVICTION_LEVEL     = "LOW"
_MOMENTUM_RSI_OVERBOUGHT   = 70.0
_MOMENTUM_RSI_OVERSOLD     = 30.0
_TREND_STRONG_THRESHOLD    = 0.65    # trend feature > 0.65 = strong uptrend
_LOW_VOLUME_RATIO          = 0.50    # volume < 50% of ADV = low liquidity
_MIN_N_FOR_RELIABLE_VOLUME = 10      # need 10+ days of history


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def attribute_errors(
    as_of: date | None = None,
    batch_size: int = 5000,
) -> int:
    """
    Classify all matured, un-attributed outcomes.
    Returns total number of attributions written.
    """
    df = repository.get_matured_outcomes_without_attribution(limit=batch_size)
    if df.empty:
        log.info("attribution.classifier.nothing_to_classify")
        return 0

    # Bulk-load feature data for these tickers/dates to avoid N+1 queries
    tickers      = df["ticker"].tolist()
    pred_dates   = pd.to_datetime(df["prediction_date"]).dt.date.tolist()
    feature_map  = _load_features_bulk(tickers, pred_dates)
    volume_map   = _load_volume_ratios_bulk(tickers, pred_dates)

    count = 0
    for _, row in df.iterrows():
        key = (row["ticker"], str(row["prediction_date"]))
        features = feature_map.get(key, {})
        volume_ratio = volume_map.get(key)

        classes = _classify(row.to_dict(), features, volume_ratio)
        for i, (cls, conf, details) in enumerate(classes):
            repository.insert_attribution({
                "outcome_id":     int(row["outcome_id"]),
                "ticker":         row["ticker"],
                "prediction_date": row["prediction_date"],
                "horizon_days":   int(row["horizon_days"]),
                "hit_or_miss":    bool(row["hit_or_miss"]) if row["hit_or_miss"] is not None else None,
                "failure_class":  cls,
                "confidence":     conf,
                "details":        details,
                "is_primary":     (i == 0),
            })
        count += 1

    log.info("attribution.classifier.complete", n=count)
    return count


# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------

def _classify(
    row: dict[str, Any],
    features: dict[str, float],
    volume_ratio: float | None,
) -> list[tuple[str, float, dict]]:
    """
    Return list of (failure_class, confidence, details) sorted by priority.
    First element is the primary classification.
    """
    hit = row.get("hit_or_miss")
    if hit is True:
        return [("correct", 1.0, {})]

    results: list[tuple[str, float, dict]] = []

    # 1. Event gap — large unexpected intraday gap on first day of horizon
    actual_ret = _f(row.get("actual_return"))
    if actual_ret is not None and abs(actual_ret) > _EVENT_GAP_THRESHOLD:
        results.append(("event_gap", 0.90, {
            "actual_return": round(actual_ret, 4),
            "threshold": _EVENT_GAP_THRESHOLD,
        }))

    # 2. Model overconfidence
    prob = _f(row.get("predicted_probability"))
    if prob is not None and prob > _OVERCONFIDENCE_THRESHOLD:
        results.append(("model_overconfidence", 0.85, {
            "predicted_probability": round(prob, 3),
            "threshold": _OVERCONFIDENCE_THRESHOLD,
        }))

    # 3. Regime mismatch — bear/high_vol regime with bullish prediction that failed
    regime    = row.get("regime", "")
    vol_regime = row.get("vol_regime", "")
    pred_dir  = row.get("predicted_direction", "neutral")
    if regime and _is_regime_mismatch(pred_dir, regime, vol_regime):
        results.append(("regime_mismatch", 0.80, {
            "regime": regime,
            "vol_regime": vol_regime,
            "predicted_direction": pred_dir,
        }))

    # 4. Conflicting signal ignored
    conflicting_cnt = _safe_int(row.get("conflicting_count"))
    if conflicting_cnt is not None and conflicting_cnt >= _CONFLICTING_SIGNAL_MIN:
        results.append(("conflicting_signal_ignored", 0.75, {
            "conflicting_count": conflicting_cnt,
        }))

    # 5. Weak confluence
    score = _f(row.get("confluence_score"))
    conv_level = row.get("conviction_level") or ""
    if (score is not None and score < _WEAK_CONFLUENCE_MAX) or conv_level == _WEAK_CONVICTION_LEVEL:
        results.append(("weak_confluence", 0.70, {
            "confluence_score": round(score, 1) if score is not None else None,
            "conviction_level": conv_level,
        }))

    # 6. Momentum exhaustion — RSI overbought/oversold at prediction
    rsi = _f(features.get("rsi_14"))
    if rsi is not None:
        if pred_dir == "bullish" and rsi > _MOMENTUM_RSI_OVERBOUGHT:
            results.append(("momentum_exhaustion", 0.72, {
                "rsi_14": round(rsi, 1),
                "condition": "overbought",
                "threshold": _MOMENTUM_RSI_OVERBOUGHT,
            }))
        elif pred_dir == "bearish" and rsi < _MOMENTUM_RSI_OVERSOLD:
            results.append(("momentum_exhaustion", 0.72, {
                "rsi_14": round(rsi, 1),
                "condition": "oversold",
                "threshold": _MOMENTUM_RSI_OVERSOLD,
            }))

    # 7. Mean reversion failure — predicted reversal against strong trend
    trend_score = _f(features.get("trend_strength_20d"))
    if trend_score is None:
        # Fallback: use SMA ratio as trend proxy
        sma_ratio = _f(features.get("sma_20_50_ratio"))
        trend_score = sma_ratio

    if trend_score is not None:
        if pred_dir == "bearish" and trend_score > _TREND_STRONG_THRESHOLD:
            results.append(("mean_reversion_failure", 0.65, {
                "trend_score": round(trend_score, 3),
                "predicted_direction": pred_dir,
                "note": "predicted reversal against strong uptrend",
            }))
        elif pred_dir == "bullish" and trend_score < (1.0 - _TREND_STRONG_THRESHOLD):
            results.append(("mean_reversion_failure", 0.65, {
                "trend_score": round(trend_score, 3),
                "predicted_direction": pred_dir,
                "note": "predicted reversal against strong downtrend",
            }))

    # 8. Low liquidity
    if volume_ratio is not None and volume_ratio < _LOW_VOLUME_RATIO:
        results.append(("low_liquidity_failure", 0.60, {
            "volume_vs_adv": round(volume_ratio, 2),
            "threshold": _LOW_VOLUME_RATIO,
        }))

    # 9. Unknown fallback
    if not results:
        results.append(("unknown", 0.40, {}))

    # Sort by confidence descending; primary is index 0
    results.sort(key=lambda x: x[1], reverse=True)
    return results


def _is_regime_mismatch(pred_dir: str, regime: str, vol_regime: str) -> bool:
    """Check if the prediction direction conflicts with the market regime."""
    if pred_dir == "bullish":
        # Bullish prediction in a bear or high-vol regime is a potential mismatch
        return regime in ("bear_market", "below_200dma") or vol_regime == "high_vol"
    if pred_dir == "bearish":
        # Bearish prediction in a strong bull regime is a potential mismatch
        return regime in ("bull_market", "above_200dma") and vol_regime == "low_vol"
    return False


# ---------------------------------------------------------------------------
# Bulk data loaders
# ---------------------------------------------------------------------------

def _load_features_bulk(
    tickers: list[str],
    pred_dates: list[date],
) -> dict[tuple[str, str], dict[str, float]]:
    """Load relevant features for all (ticker, date) pairs at once."""
    if not tickers:
        return {}
    target_features = ["rsi_14", "trend_strength_20d", "sma_20_50_ratio",
                        "volume_ratio_20d", "atr_14_pct"]
    sql = text("""
        SELECT ticker, date::text, feature_name, feature_value
        FROM feature_snapshots
        WHERE ticker      = ANY(:tickers)
          AND date        = ANY(:dates)
          AND feature_name = ANY(:features)
    """)
    with get_connection() as conn:
        rows = conn.execute(sql, {
            "tickers":  tickers,
            "dates":    [str(d) for d in pred_dates],
            "features": target_features,
        }).fetchall()

    result: dict[tuple[str, str], dict[str, float]] = {}
    for ticker, dt, name, value in rows:
        key = (ticker, dt)
        if key not in result:
            result[key] = {}
        if value is not None:
            result[key][name] = float(value)
    return result


def _load_volume_ratios_bulk(
    tickers: list[str],
    pred_dates: list[date],
) -> dict[tuple[str, str], float]:
    """Compute volume / ADV ratio for each (ticker, prediction_date)."""
    if not tickers:
        return {}
    sql = text("""
        WITH pred AS (
            SELECT unnest(:tickers::text[]) AS ticker,
                   unnest(:dates::date[]) AS pred_date
        ),
        daily_vol AS (
            SELECT rb.ticker, rb.date, rb.volume,
                   AVG(rb.volume) OVER (
                       PARTITION BY rb.ticker
                       ORDER BY rb.date
                       ROWS BETWEEN 21 PRECEDING AND 1 PRECEDING
                   ) AS adv_20
            FROM raw_bars rb
            JOIN pred p ON p.ticker = rb.ticker
        )
        SELECT dv.ticker, dv.date::text, dv.volume, dv.adv_20
        FROM daily_vol dv
        JOIN pred p ON p.ticker = dv.ticker AND p.pred_date = dv.date
        WHERE dv.adv_20 > 0
    """)
    try:
        with get_connection() as conn:
            rows = conn.execute(sql, {
                "tickers": tickers,
                "dates":   [str(d) for d in pred_dates],
            }).fetchall()
    except Exception:
        return {}

    result: dict[tuple[str, str], float] = {}
    for ticker, dt, volume, adv_20 in rows:
        if adv_20 and adv_20 > 0 and volume is not None:
            result[(ticker, dt)] = float(volume) / float(adv_20)
    return result


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
