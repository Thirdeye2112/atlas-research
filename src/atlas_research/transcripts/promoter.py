"""
atlas_research.transcripts.promoter
=====================================
Reads completed hypothesis_results and promotes statistically validated
ideas to promoted_features.

Promotion criteria (all must pass):
  - sample_size  >= 20
  - hit_rate     >= 0.55
  - p_value      <= 0.10
  - composite_score >= 0.40

Promoted features are given a snake_case feature_name and an
implementation_spec JSONB that a developer can use to add the
feature to the feature engineering pipeline.

Usage
-----
    from atlas_research.transcripts.promoter import HypothesisPromoter
    p = HypothesisPromoter()
    n = p.promote_passing()
"""

from __future__ import annotations

import json
import re
from datetime import datetime

import structlog
from sqlalchemy import text

from atlas_research.db.connection import get_connection

log = structlog.get_logger(__name__)

PROMOTION_THRESHOLDS = {
    "min_sample_size": 20,
    "min_hit_rate":    0.55,
    "max_p_value":     0.10,
    "min_composite":   0.40,
}


def _to_snake_case(text: str) -> str:
    """Convert free-form text to a valid snake_case feature name."""
    text = re.sub(r"[^\w\s]", "", text.lower())
    text = re.sub(r"\s+", "_", text.strip())
    text = re.sub(r"_+", "_", text)
    return text[:80]


def _build_feature_name(claim: str, market_object: str, condition: str, horizon: int) -> str:
    """Generate a unique snake_case feature name from hypothesis components."""
    parts = [
        market_object.lower().replace(".", "_"),
        condition[:30],
        f"h{horizon}",
    ]
    base = "_".join(parts)
    return _to_snake_case(base)


def _build_implementation_spec(hyp: dict, result: dict) -> dict:
    """
    Build the implementation_spec JSONB — everything a developer needs to
    implement this feature in the feature engineering pipeline.
    """
    return {
        "hypothesis_id":    hyp["hypothesis_id"],
        "extracted_claim":  hyp["extracted_claim"],
        "market_object":    hyp["market_object"],
        "condition":        hyp["condition"],
        "condition_params": hyp["condition_params"] or {},
        "direction":        hyp["direction"],
        "regime_filter":    hyp["regime_filter"],
        "best_horizon_days": result["horizon_days"],
        "implementation_type": _classify_implementation(hyp["condition"]),
        "feature_type": "binary_event" if hyp["condition"] in (
            "down_n_consecutive_days", "up_n_consecutive_days",
            "near_52w_low", "near_52w_high", "gap_up", "gap_down",
        ) else "continuous",
        "suggested_module":  "atlas_research.features.event_conditions",
        "validation_stats": {
            "hit_rate":       result["hit_rate"],
            "avg_return":     result["avg_return"],
            "sharpe":         result["sharpe"],
            "p_value":        result["p_value"],
            "sample_size":    result["sample_size"],
            "composite_score": result["composite_score"],
        },
    }


def _classify_implementation(condition: str) -> str:
    """Classify the condition type for implementation routing."""
    condition = condition.lower()
    if "consecutive" in condition:
        return "rolling_window_count"
    if "rsi" in condition:
        return "technical_indicator"
    if "volume" in condition:
        return "volume_pattern"
    if "gap" in condition:
        return "price_event"
    if "sma" in condition or "ema" in condition:
        return "trend_condition"
    if "volatility" in condition or "vol" in condition:
        return "volatility_regime"
    if "52w" in condition or "high" in condition or "low" in condition:
        return "price_level"
    return "custom"


class HypothesisPromoter:

    def promote_passing(self) -> int:
        """
        Evaluate all done hypotheses with un-promoted results.
        Promote those meeting statistical thresholds.
        Returns number newly promoted.
        """
        rows = self._fetch_candidates()
        if not rows:
            log.info("promoter.no_candidates")
            return 0

        log.info("promoter.evaluating", n_candidates=len(rows))
        promoted = 0

        for row in rows:
            hid = row["hypothesis_id"]

            # Find best horizon result
            best = self._best_result(hid)
            if best is None:
                continue

            # Evaluate thresholds
            if not self._passes(best):
                log.info(
                    "promoter.rejected",
                    hypothesis_id=hid,
                    reason=self._rejection_reason(best),
                    composite=round(best.get("composite_score") or 0, 3),
                )
                continue

            # Promote
            feature_name = _build_feature_name(
                claim       = row["extracted_claim"],
                market_object = row["market_object"],
                condition   = row["condition"],
                horizon     = best["horizon_days"],
            )
            spec = _build_implementation_spec(dict(row), best)
            self._upsert_promotion(
                hypothesis_id   = hid,
                feature_name    = feature_name,
                description     = row["extracted_claim"],
                category        = _classify_implementation(row["condition"]),
                spec            = spec,
                result          = best,
            )
            self._mark_promoted(hid)
            log.info(
                "promoter.promoted",
                hypothesis_id=hid,
                feature_name=feature_name,
                hit_rate=round(best["hit_rate"], 3),
                sharpe=round(best["sharpe"] or 0, 3),
                p_value=round(best["p_value"] or 1, 4),
                composite=round(best["composite_score"] or 0, 3),
            )
            promoted += 1

        log.info("promoter.done", promoted=promoted)
        return promoted

    # ------------------------------------------------------------------
    # DB helpers
    # ------------------------------------------------------------------

    def _fetch_candidates(self) -> list:
        with get_connection() as conn:
            return conn.execute(text("""
                SELECT h.hypothesis_id, h.extracted_claim,
                       h.market_object, h.condition, h.condition_params,
                       h.direction, h.regime_filter
                FROM research_hypotheses h
                WHERE h.test_status = 'done'
                  AND h.promoted = false
                ORDER BY h.created_at ASC
            """)).mappings().fetchall()

    def _best_result(self, hid: str) -> dict | None:
        """Return the best-scoring result across all horizons."""
        with get_connection() as conn:
            row = conn.execute(text("""
                SELECT r.horizon_days, r.sample_size, r.hit_rate,
                       r.avg_return, r.sharpe, r.p_value, r.rank_ic,
                       r.composite_score
                FROM hypothesis_results r
                JOIN hypothesis_tests t ON t.id = r.test_id
                WHERE r.hypothesis_id = :h
                  AND r.sample_size >= :min_n
                ORDER BY r.composite_score DESC NULLS LAST
                LIMIT 1
            """), {"h": hid, "min_n": PROMOTION_THRESHOLDS["min_sample_size"]}).mappings().fetchone()
        return dict(row) if row else None

    def _passes(self, result: dict) -> bool:
        return (
            (result.get("sample_size") or 0)    >= PROMOTION_THRESHOLDS["min_sample_size"] and
            (result.get("hit_rate") or 0)        >= PROMOTION_THRESHOLDS["min_hit_rate"] and
            (result.get("p_value") or 1)         <= PROMOTION_THRESHOLDS["max_p_value"] and
            (result.get("composite_score") or 0) >= PROMOTION_THRESHOLDS["min_composite"]
        )

    def _rejection_reason(self, result: dict) -> str:
        reasons = []
        if (result.get("sample_size") or 0) < PROMOTION_THRESHOLDS["min_sample_size"]:
            reasons.append(f"sample_size={result.get('sample_size')}<{PROMOTION_THRESHOLDS['min_sample_size']}")
        if (result.get("hit_rate") or 0) < PROMOTION_THRESHOLDS["min_hit_rate"]:
            reasons.append(f"hit_rate={round(result.get('hit_rate') or 0, 3)}<{PROMOTION_THRESHOLDS['min_hit_rate']}")
        if (result.get("p_value") or 1) > PROMOTION_THRESHOLDS["max_p_value"]:
            reasons.append(f"p_value={round(result.get('p_value') or 1, 4)}>{PROMOTION_THRESHOLDS['max_p_value']}")
        if (result.get("composite_score") or 0) < PROMOTION_THRESHOLDS["min_composite"]:
            reasons.append(f"composite={round(result.get('composite_score') or 0, 3)}<{PROMOTION_THRESHOLDS['min_composite']}")
        return "; ".join(reasons) or "unknown"

    def _upsert_promotion(
        self,
        hypothesis_id: str,
        feature_name: str,
        description: str,
        category: str,
        spec: dict,
        result: dict,
    ) -> None:
        def _s(v):
            if v is None:
                return None
            import math
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                return None
            return v

        with get_connection() as conn:
            conn.execute(text("""
                INSERT INTO promoted_features (
                    hypothesis_id, feature_name, feature_description,
                    feature_category, implementation_spec,
                    best_horizon_days, best_hit_rate, best_rank_ic,
                    best_sharpe, sample_size, p_value,
                    promotion_status
                ) VALUES (
                    :hid, :fname, :desc,
                    :cat, CAST(:spec AS jsonb),
                    :hz, :hr, :ic,
                    :sh, :n, :pv,
                    'candidate'
                )
                ON CONFLICT (feature_name) DO UPDATE SET
                    best_hit_rate  = EXCLUDED.best_hit_rate,
                    best_sharpe    = EXCLUDED.best_sharpe,
                    implementation_spec = EXCLUDED.implementation_spec,
                    promoted_at    = now()
            """), {
                "hid":   hypothesis_id,
                "fname": feature_name,
                "desc":  description[:500],
                "cat":   category,
                "spec":  json.dumps(spec),
                "hz":    result.get("horizon_days"),
                "hr":    _s(result.get("hit_rate")),
                "ic":    _s(result.get("rank_ic")),
                "sh":    _s(result.get("sharpe")),
                "n":     result.get("sample_size"),
                "pv":    _s(result.get("p_value")),
            })
            conn.commit()

    def _mark_promoted(self, hid: str) -> None:
        with get_connection() as conn:
            conn.execute(text(
                "UPDATE research_hypotheses SET promoted = true, updated_at = now() WHERE hypothesis_id = :h"
            ), {"h": hid})
            conn.commit()
