"""
Atlas Intraday Similarity Feature Vector v2 - Behavior-Aware
=============================================================
Extends the 16-dim v1 vector with a 20-dim behavior intensity vector
to produce a 36-dim combined feature vector.

Vector layout:
  dims  0-15 : v1 features (candle shape, volume, trend, momentum, time, daily context)
  dims 16-35 : behavior intensities [0,1] in alphabetical behavior_id order

Four comparison variants (feature masks + weight arrays):
  raw_candle      - dims  0-6   (shape + volume only, 7 dims)
  technical       - dims  0-12  (shape + vol + trend + momentum, 13 dims, no daily ctx)
  behavior_aware  - dims  0-35  (all 36, behaviors weighted 1.5x)
  behavior_plus_ctx - dims 0-35 (all 36, behaviors 2.0x + daily ctx 3.0x)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .features import (
    DEFAULT_WEIGHTS,
    N_FEATURES,
    build_feature_vector,
    build_vectors_batch,
    FEATURE_NAMES,
)

# ---------------------------------------------------------------------------
# Behavior IDs -- alphabetical order; index in this list = index in dim 16+N
# ---------------------------------------------------------------------------
BEHAVIOR_IDS: list[str] = sorted([
    "ABOVE_ALL_EMAS",
    "ATR_EXPANSION",
    "ATR_SQUEEZE",
    "BELOW_ALL_EMAS",
    "DEATH_CROSS",
    "GAP_DOWN_LARGE",
    "GAP_DOWN_SMALL",
    "GAP_UP_LARGE",
    "GAP_UP_SMALL",
    "GOLDEN_CROSS",
    "INSIDE_DAY",
    "LARGE_DAILY_RANGE",
    "LOW_VOL_DRIFT_UP",
    "MACD_BEAR_CROSS",
    "MACD_BULL_CROSS",
    "NEAR_52W_HIGH",
    "RSI_OVERBOUGHT",
    "RSI_OVERSOLD_RECLAIM",
    "VOL_SURGE_BEAR",
    "VOL_SURGE_BULL",
])
BEHAVIOR_INDEX: dict[str, int] = {b: i for i, b in enumerate(BEHAVIOR_IDS)}
N_BEHAVIORS:   int = len(BEHAVIOR_IDS)
N_FEATURES_V2: int = N_FEATURES + N_BEHAVIORS   # 16 + 20 = 36

FEATURE_NAMES_V2: list[str] = FEATURE_NAMES + [f"b_{b.lower()}" for b in BEHAVIOR_IDS]

# Default behavior feature weights (behaviors are daily context, slightly downweighted vs time)
_BEHAVIOR_WEIGHTS: np.ndarray = np.full(N_BEHAVIORS, 1.5, dtype=np.float64)

DEFAULT_WEIGHTS_V2: np.ndarray = np.concatenate([DEFAULT_WEIGHTS, _BEHAVIOR_WEIGHTS])

# ---------------------------------------------------------------------------
# Variant definitions: (name, feature_indices, weight_array)
# ---------------------------------------------------------------------------

def _mask_weights(indices: list[int], base_weights: np.ndarray) -> np.ndarray:
    return base_weights[np.array(indices)]


# Raw candle: shape + volume only (dims 0-6)
RAW_CANDLE_DIMS    = list(range(7))
RAW_CANDLE_WEIGHTS = _mask_weights(RAW_CANDLE_DIMS, DEFAULT_WEIGHTS_V2)

# Technical: shape + vol + trend + momentum (dims 0-11), skip time + daily ctx + behavior
TECHNICAL_DIMS    = list(range(12))
TECHNICAL_WEIGHTS = _mask_weights(TECHNICAL_DIMS, DEFAULT_WEIGHTS_V2)

# Behavior-aware: full 36-dim, behavior at 1.5x
BEHAVIOR_AWARE_DIMS    = list(range(N_FEATURES_V2))
BEHAVIOR_AWARE_WEIGHTS = DEFAULT_WEIGHTS_V2.copy()

# Behavior + boosted daily context: same dims, behaviors at 2.0x, daily ctx (13,14,15) at 3.0x
BEHAVIOR_CTX_WEIGHTS             = DEFAULT_WEIGHTS_V2.copy()
BEHAVIOR_CTX_WEIGHTS[13:16]      = 3.0   # conviction, regime, vix
BEHAVIOR_CTX_WEIGHTS[N_FEATURES:] = 2.0  # all 20 behavior dims
BEHAVIOR_CTX_DIMS = list(range(N_FEATURES_V2))

VARIANTS: dict[str, dict] = {
    "raw_candle": {
        "dims":    RAW_CANDLE_DIMS,
        "weights": RAW_CANDLE_WEIGHTS,
        "label":   "Raw Candle (shape+volume, 7 dims)",
    },
    "technical": {
        "dims":    TECHNICAL_DIMS,
        "weights": TECHNICAL_WEIGHTS,
        "label":   "Technical (shape+vol+trend+momentum, 12 dims)",
    },
    "behavior_aware": {
        "dims":    BEHAVIOR_AWARE_DIMS,
        "weights": BEHAVIOR_AWARE_WEIGHTS,
        "label":   "Behavior-Aware (36 dims, behavior 1.5x)",
    },
    "behavior_plus_ctx": {
        "dims":    BEHAVIOR_CTX_DIMS,
        "weights": BEHAVIOR_CTX_WEIGHTS,
        "label":   "Behavior+Context (36 dims, behavior 2.0x, ctx 3.0x)",
    },
}

# ---------------------------------------------------------------------------
# Build functions
# ---------------------------------------------------------------------------

def build_behavior_vector(
    behavior_events: "list[dict] | None",
) -> np.ndarray:
    """
    Build a 20-dim behavior intensity vector from a list of behavior event dicts.
    Each dict has keys: behavior_id (str), intensity (float 0-1).
    Missing behaviors default to 0.0.
    """
    vec = np.zeros(N_BEHAVIORS, dtype=np.float64)
    if behavior_events:
        for evt in behavior_events:
            idx = BEHAVIOR_INDEX.get(evt.get("behavior_id", ""))
            if idx is not None:
                val = float(evt.get("intensity", 0.0))
                if val == val:  # NaN guard
                    vec[idx] = min(1.0, max(0.0, val))
    return vec


def build_feature_vector_v2(
    row: "pd.Series | dict",
    behavior_events: "list[dict] | None" = None,
) -> np.ndarray:
    """
    Build a 36-dim v2 feature vector.
    row           : same input as v1 build_feature_vector()
    behavior_events: list of {behavior_id, intensity} dicts for this candle's date
    """
    v1  = build_feature_vector(row)
    beh = build_behavior_vector(behavior_events)
    return np.concatenate([v1, beh])


def build_vectors_v2_batch(
    df: pd.DataFrame,
    behavior_map: "dict[tuple[str, object], list[dict]] | None" = None,
) -> np.ndarray:
    """
    Vectorized batch build for v2.
    df           : DataFrame with v1 feature columns
    behavior_map : {(ticker, candle_date) -> list[{behavior_id, intensity}]}

    Returns (N, 36) float64 array.
    """
    n    = len(df)
    v1   = build_vectors_batch(df)                       # (N, 16)
    beh  = np.zeros((n, N_BEHAVIORS), dtype=np.float64)  # (N, 20)

    if behavior_map and "ticker" in df.columns and "ts" in df.columns:
        dates = pd.to_datetime(df["ts"]).dt.date.values
        ticks = df["ticker"].values
        for i in range(n):
            key    = (ticks[i], dates[i])
            events = behavior_map.get(key)
            if events:
                beh[i] = build_behavior_vector(events)

    return np.concatenate([v1, beh], axis=1)


def extract_variant_matrix(
    full_matrix: np.ndarray,
    variant: str,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Slice a (N, 36) full matrix to the feature subset for a given variant.
    Returns (sliced_matrix, weight_array) ready for KNN.
    """
    spec = VARIANTS[variant]
    dims = np.array(spec["dims"])
    w    = spec["weights"]
    return full_matrix[:, dims], w
