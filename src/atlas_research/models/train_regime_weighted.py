"""
Regime-balanced training — Approach A of the regime-aware rebuild.

WHY: the OOS diagnosis (reports/diagnostics/OOS_GENERALIZATION_DIAGNOSIS.md
in the research/oos-diagnosis branch) found the embargoed-year failure
concentrated in bull_high_vol (the model's weakest regime, only ~11-17% of
training history) while bull_low_vol (the model's best-known regime, ~40-46%
of training) is over-represented in training relative to its share of the
embargoed year. This module reweights training ROWS by inverse regime
frequency so no single regime can dominate the loss the way bull_low_vol
currently does — a minimal, principled change to the SAMPLE WEIGHTING only.

Same features, same LightGBM params (LGBM_PARAMS_REGRESSOR/CLASSIFIER from
config.settings, untouched), same 10%-of-training early-stopping carve, same
Platt-on-ES-holdout calibration as train.py. The only addition is a per-row
`weight` passed to lgb.Dataset.

This is a NEW, PARALLEL path. train.py / dataset.py / walk_forward.py are
NOT edited — this module imports their utilities (cross_sectional_normalize,
_fit_platt, CALIBRATION_MIN_STD, etc.) rather than duplicating or modifying
them.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from atlas_research.utils.logging import get_logger
from atlas_research.models.train import _fit_platt, CALIBRATION_MIN_STD

log = get_logger(__name__)

try:
    import lightgbm as lgb
    _LGB_AVAILABLE = True
except ImportError:
    lgb = None  # type: ignore[assignment]
    _LGB_AVAILABLE = False

VOL_THRESHOLD: float = 0.30  # same threshold as the OOS diagnosis / compute_feature_reliability.py


def _require_lgb() -> None:
    if not _LGB_AVAILABLE:
        raise ImportError("lightgbm is required. Install with: pip install lightgbm")


def tag_regime(df: pd.DataFrame) -> pd.Series:
    """
    6-bucket regime tag, identical definition to the OOS diagnosis (Angle 2)
    and scripts/compute_feature_reliability.py:load_regime_context. Must be
    called on RAW (pre-cross-sectional-normalize) market_trend / realized_vol_20
    — normalization ranks realized_vol_20 to a percentile, which would break
    the absolute 0.30 threshold. market_trend is exempt from normalization
    (it's a ternary flag, excluded by cross_sectional_normalize already), but
    we read both as raw here for clarity and safety.
    """
    regime_market = np.where(df["market_trend"] > 0, "bull",
                     np.where(df["market_trend"] < 0, "bear", "range"))
    regime_vol = np.where(df["realized_vol_20"] > VOL_THRESHOLD, "high_vol", "low_vol")
    return pd.Series(
        np.char.add(np.char.add(regime_market.astype(str), "_"), regime_vol.astype(str)),
        index=df.index, name="regime",
    )


def regime_balanced_weights(regime: pd.Series) -> np.ndarray:
    """
    Inverse-frequency weighting computed from THIS regime Series alone (i.e.
    one fold's own training set — no look-ahead, no use of any other fold's
    or the OOS year's regime mix). Each regime bucket receives equal
    AGGREGATE weight (n / n_buckets_present); total weight sums to len(regime),
    same total "mass" as unweighted training so the effective learning rate
    is comparable to V1's.
    """
    counts = regime.value_counts()
    n = len(regime)
    n_buckets = len(counts)
    target_per_bucket = n / n_buckets
    per_row = regime.map(lambda r: target_per_bucket / counts[r])
    return per_row.to_numpy(dtype=np.float64)


def train_regressor_weighted(
    X_train: np.ndarray,
    y_train: np.ndarray,
    w_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    feature_names: list[str],
    params: dict | None = None,
) -> tuple[Any, dict]:
    """Regime-weighted analog of train.train_regressor. Identical recipe, +sample weight."""
    _require_lgb()
    from config.settings import LGBM_PARAMS_REGRESSOR

    p = params or LGBM_PARAMS_REGRESSOR.copy()

    n_es = max(1, int(len(X_train) * 0.10))
    X_es, y_es, w_es = X_train[-n_es:], y_train[-n_es:], w_train[-n_es:]
    X_tr, y_tr, w_tr = X_train[:-n_es], y_train[:-n_es], w_train[:-n_es]

    train_data = lgb.Dataset(X_tr, label=y_tr, weight=w_tr, feature_name=feature_names)

    if len(X_tr) >= 5000:
        es_data = lgb.Dataset(X_es, label=y_es, weight=w_es, feature_name=feature_names,
                               reference=train_data)
        callbacks = [
            lgb.early_stopping(stopping_rounds=20, verbose=False),
            lgb.log_evaluation(period=-1),
        ]
        model = lgb.train(p, train_set=train_data, valid_sets=[es_data], callbacks=callbacks)
    else:
        callbacks = [lgb.log_evaluation(period=-1)]
        model = lgb.train(p, train_set=train_data, callbacks=callbacks)

    importances = {
        "gain":  model.feature_importance(importance_type="gain").tolist(),
        "split": model.feature_importance(importance_type="split").tolist(),
    }
    log.info("train_rw.regressor_done", n_trees=model.num_trees())
    return model, importances


def train_classifier_weighted(
    X_train: np.ndarray,
    y_train: np.ndarray,
    w_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    feature_names: list[str],
    params: dict | None = None,
) -> tuple[Any, Any, dict]:
    """Regime-weighted analog of train.train_classifier. Identical recipe, +sample weight."""
    _require_lgb()
    from config.settings import LGBM_PARAMS_CLASSIFIER

    p = params or LGBM_PARAMS_CLASSIFIER.copy()

    n_es = max(1, int(len(X_train) * 0.10))
    X_es, y_es, w_es = X_train[-n_es:], y_train[-n_es:], w_train[-n_es:]
    X_tr, y_tr, w_tr = X_train[:-n_es], y_train[:-n_es], w_train[:-n_es]

    train_data = lgb.Dataset(X_tr, label=y_tr, weight=w_tr, feature_name=feature_names)

    if len(X_tr) >= 5000:
        es_data = lgb.Dataset(X_es, label=y_es, weight=w_es, feature_name=feature_names,
                               reference=train_data)
        callbacks = [
            lgb.early_stopping(stopping_rounds=20, verbose=False),
            lgb.log_evaluation(period=-1),
        ]
        model = lgb.train(p, train_set=train_data, valid_sets=[es_data], callbacks=callbacks)
    else:
        callbacks = [lgb.log_evaluation(period=-1)]
        model = lgb.train(p, train_set=train_data, callbacks=callbacks)

    importances = {
        "gain":  model.feature_importance(importance_type="gain").tolist(),
        "split": model.feature_importance(importance_type="split").tolist(),
    }

    # Same anti-leak calibration as train.py: Platt fit on the ES holdout,
    # never on X_val. Same degenerate-fold skip rule.
    es_raw = model.predict(X_es)
    raw_std = float(np.std(es_raw))

    if raw_std < CALIBRATION_MIN_STD:
        platt = None
        log.info("train_rw.classifier_done", n_trees=model.num_trees(),
                 calibration="skipped (degenerate)", raw_std=round(raw_std, 5))
    else:
        platt = _fit_platt(es_raw, y_es)
        calib = "platt(es_holdout)" if platt is not None else "none (sklearn missing)"
        log.info("train_rw.classifier_done", n_trees=model.num_trees(), calibration=calib)

    return model, platt, importances
