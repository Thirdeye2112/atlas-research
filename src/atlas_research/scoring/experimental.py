"""
experimental.py — Four experimental score variants derived from raw features.

Grounded in calibration findings from alpha_score_calibration_runs:
  RSI oversold <30     → +17.5pp 5d edge
  Low ATR <2%          → +14.7pp
  Exhaustion high      → +11.0pp
  Volume HIGH          → −40.9pp (heaviest destroyer)
  RSI overbought >70   → −18.3pp
  Score 80-100 (v1)    → −31.4pp

Scoring philosophy:
  v1 = current behaviour (momentum/trend proxy)
  v2 = mean reversion (rewards beaten-down, penalises extended/high-volume)
  v3 = hybrid (0.4*v1 + 0.6*v2)
  v4 = tier-adjusted (v2 weight varies by quality tier)

All scores return float in [0, 100].
All inputs are raw feature values (floats); None/NaN treated as neutral defaults.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

SCORE_VERSIONS = ["v1_current", "v2_mean_reversion", "v3_hybrid", "v4_tier_adjusted"]
SCORE_BUCKETS  = ["0-20", "20-40", "40-60", "60-80", "80-100"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _f(v: Any, default: float = 0.0) -> float:
    """Safe float coercion. Returns default for None / NaN / Inf."""
    if v is None:
        return default
    try:
        fv = float(v)
        return default if (math.isnan(fv) or math.isinf(fv)) else fv
    except (TypeError, ValueError):
        return default


def bucket(score: float) -> str:
    """Map score [0-100] to bucket label."""
    if score < 20:  return "0-20"
    if score < 40:  return "20-40"
    if score < 60:  return "40-60"
    if score < 80:  return "60-80"
    return "80-100"


# ── Score v1 — current behaviour proxy ───────────────────────────────────────

def score_v1_current(features: dict) -> float:
    """
    Proxy for the existing Atlas Score.

    Rewards: above SMA (trend confirmation), high RSI (momentum).
    This replicates the behaviour that calibration showed underperforms at 5d:
    score 80-100 → 30% hit rate (−31pp edge).

    Component weights mirror the general Atlas Score architecture:
      trend     (0-60): above_sma20*15 + above_sma50*20 + above_sma200*25
      momentum  (0-40): rsi_14 normalised
    """
    a20  = _f(features.get("above_sma20"),  0.0)
    a50  = _f(features.get("above_sma50"),  0.0)
    a200 = _f(features.get("above_sma200"), 0.0)
    rsi  = _f(features.get("rsi_14"),       50.0)

    trend    = a20 * 15 + a50 * 20 + a200 * 25        # 0-60
    momentum = min(max(rsi / 100.0 * 40.0, 0.0), 40.0)  # 0-40
    return min(trend + momentum, 100.0)


# ── Score v2 — mean reversion ─────────────────────────────────────────────────

def score_v2_mean_reversion(features: dict) -> float:
    """
    Mean-reversion score. Derived directly from calibration edge data.

    High score → beaten-down, oversold, low volatility, at OMNI support.
    Low score  → extended, high-volume, overbought.

    Point allocation (max 90):
      RSI zone score     (0-40): oversold=40, mid=20, neutral=10, OB=0
      Volatility score   (0-30): low realized vol = high score
      OMNI proximity     (0-20): price below / near OMNI 82 = higher score
      Volume penalty    (0-20): high volume spike = deducted
    """
    rsi    = _f(features.get("rsi_14"),         50.0)
    vol20  = _f(features.get("realized_vol_20"), 25.0)
    omni_d = _f(features.get("omni_82_distance"),  0.0)
    omni_a = _f(features.get("omni_82_above"),     0.0)
    v_rat  = _f(features.get("volume_ratio_20"),   1.0)

    # RSI zone (calibration: oversold<30 → +17.5pp; overbought>70 → −18.3pp)
    if rsi < 30:   rsi_score = 40.0
    elif rsi < 40: rsi_score = 30.0
    elif rsi < 50: rsi_score = 20.0
    elif rsi < 60: rsi_score = 10.0
    elif rsi < 70: rsi_score = 5.0
    else:          rsi_score = 0.0

    # Volatility stability (calibration: low ATR <2% → +14.7pp)
    # realized_vol_20 is annualised; 15% ≈ low, 40% ≈ high
    vol_norm   = min(max(vol20, 0.0), 80.0) / 80.0
    vol_score  = (1.0 - vol_norm) * 30.0          # 0-30

    # OMNI proximity (calibration: volume_component/low → +6.1pp; exhaustion context)
    # Below OMNI (omni_82_above=0) or near support is bullish for mean reversion
    if omni_a == 0.0:
        omni_score = 20.0   # below OMNI = potential bounce
    elif omni_d < 0.05:
        omni_score = 10.0   # just above OMNI
    else:
        omni_score = 0.0    # extended above OMNI

    # Volume penalty (calibration: volume_component/high → −40.9pp edge)
    if v_rat > 3.0:    vol_penalty = 20.0
    elif v_rat > 2.0:  vol_penalty = 10.0
    else:              vol_penalty = 0.0

    raw = rsi_score + vol_score + omni_score - vol_penalty
    return float(min(max(raw, 0.0), 90.0))


# ── Score v3 — hybrid ─────────────────────────────────────────────────────────

def score_v3_hybrid(features: dict) -> float:
    """
    Hybrid: 40% v1 momentum + 60% v2 mean-reversion.

    Captures trend context while tilting toward mean-reversion alpha.
    Calibration showed v1 destroys alpha at high scores; v2 restores it.
    60/40 blend preserves some trend signal for regime filtering.
    """
    v1 = score_v1_current(features)
    v2 = score_v2_mean_reversion(features)
    return 0.4 * v1 + 0.6 * v2


# ── Score v4 — tier-adjusted ──────────────────────────────────────────────────

def score_v4_tier_adjusted(features: dict) -> float:
    """
    Tier-adjusted blending.

    Large/mid cap: heavy v2 (mean reversion works; institutional quality stocks bounce).
    Small cap: equal blend (more speculative; some momentum relevance).
    Micro cap: lean v1 (momentum-driven; mean reversion less reliable).

    Tier:  1(large)   2(mid)   3(small)  4(micro)
    v1 wt:   0.20      0.30      0.50      0.65
    v2 wt:   0.80      0.70      0.50      0.35
    """
    tier = int(_f(features.get("quality_tier"), 2.0))
    v1 = score_v1_current(features)
    v2 = score_v2_mean_reversion(features)

    weights = {1: (0.20, 0.80), 2: (0.30, 0.70), 3: (0.50, 0.50), 4: (0.65, 0.35)}
    w1, w2 = weights.get(tier, (0.40, 0.60))
    return float(w1 * v1 + w2 * v2)


# ── Batch computation ─────────────────────────────────────────────────────────

_SCORE_FNS = {
    "v1_current":        score_v1_current,
    "v2_mean_reversion": score_v2_mean_reversion,
    "v3_hybrid":         score_v3_hybrid,
    "v4_tier_adjusted":  score_v4_tier_adjusted,
}


def compute_all_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute all 4 score variants for each row in a wide-format DataFrame.

    Input:  DataFrame with feature columns (raw feature values).
    Output: Input DataFrame + columns score_v1/v2/v3/v4 and bucket_v1/v2/v3/v4.
    """
    out = df.copy()
    for name, fn in _SCORE_FNS.items():
        col = f"score_{name}"
        out[col] = out.apply(
            lambda row: fn(row.to_dict()),
            axis=1,
        )
        out[f"bucket_{name}"] = out[col].apply(bucket)
    return out
