"""
LightGBM model training — Phase 2.

Two models per training run:
    1. return_regressor   — predicts label_return_5d (float)
    2. positive_classifier — predicts label_positive_5d (0/1 probability)

Both use the same feature set (TRAIN_FEATURES from settings).
Each trained model is saved as a joblib artifact and registered in
model_registry via repository.upsert_model_registry().

ARTIFACT STORAGE
----------------
/models/{model_name}_{version}_{train_end}/model.joblib

The artifact filename encodes the training cutoff so that any saved model
can be matched to its exact training window for reproducibility.

CALIBRATION
-----------
The classifier output (raw LightGBM sigmoid probability) is already
reasonably calibrated for most datasets, but we apply Platt scaling
(LogisticRegression on the OOF predictions) on the validation set
before writing final probabilities.

EARLY STOPPING
--------------
10% of training data is held back as an early-stopping set (not the
validation fold — that must remain unseen).  This prevents the model
from simply memorising the training data.
"""

from __future__ import annotations

import hashlib
import os
import pickle
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from atlas_research.utils.logging import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Try importing lightgbm — graceful import error for environments without it
# ---------------------------------------------------------------------------
try:
    import lightgbm as lgb
    _LGB_AVAILABLE = True
except ImportError:
    lgb = None              # type: ignore[assignment]
    _LGB_AVAILABLE = False


def _require_lgb() -> None:
    if not _LGB_AVAILABLE:
        raise ImportError(
            "lightgbm is required for Phase 2 model training. "
            "Install with: pip install lightgbm"
        )


# ---------------------------------------------------------------------------
# Model artifact helpers
# ---------------------------------------------------------------------------

def artifact_path(
    model_name: str,
    model_version: str,
    train_end: date,
    model_dir: Path,
) -> Path:
    """Canonical path for a model artifact."""
    slug = f"{model_name}_{model_version}_{train_end.isoformat()}"
    return model_dir / slug / "model.joblib"


def save_model(model: Any, path: Path) -> str:
    """Save model to disk and return SHA-256 hash of the file."""
    import joblib
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    log.info("train.model_saved", path=str(path), sha256=sha256[:16])
    return sha256


def load_model(path: Path) -> Any:
    """Load a saved model artifact."""
    import joblib
    if not path.exists():
        raise FileNotFoundError(f"Model artifact not found: {path}")
    return joblib.load(path)


# ---------------------------------------------------------------------------
# LightGBM training
# ---------------------------------------------------------------------------

def train_regressor(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    feature_names: list[str],
    params: dict | None = None,
) -> tuple[Any, dict]:
    """
    Train a LightGBM regression model.

    Uses 10% of training data as early-stopping set (not the validation fold).
    Returns the fitted model and a dict of feature importances.

    Args:
        X_train:       Training feature matrix (n_train, n_features).
        y_train:       Training targets.
        X_val:         Validation feature matrix (unseen during training).
        y_val:         Validation targets (used only for final metric logging).
        feature_names: Ordered feature names matching X columns.
        params:        LightGBM params dict.  Defaults to settings.LGBM_PARAMS_REGRESSOR.

    Returns:
        (model, importances)
        importances: dict with 'gain' and 'split' arrays aligned to feature_names.
    """
    _require_lgb()
    from config.settings import LGBM_PARAMS_REGRESSOR

    p = params or LGBM_PARAMS_REGRESSOR.copy()

    # Carve out early-stopping set (10%) from training data
    n_es = max(1, int(len(X_train) * 0.10))
    X_es, y_es = X_train[-n_es:], y_train[-n_es:]
    X_tr, y_tr = X_train[:-n_es], y_train[:-n_es]

    train_data = lgb.Dataset(X_tr, label=y_tr, feature_name=feature_names)
    es_data    = lgb.Dataset(X_es, label=y_es, feature_name=feature_names,
                              reference=train_data)

    callbacks = [
        lgb.early_stopping(stopping_rounds=50, verbose=False),
        lgb.log_evaluation(period=-1),
    ]

    model = lgb.train(
        p,
        train_set=train_data,
        valid_sets=[es_data],
        callbacks=callbacks,
    )

    importances = {
        "gain":  model.feature_importance(importance_type="gain").tolist(),
        "split": model.feature_importance(importance_type="split").tolist(),
    }

    # Log validation RMSE for monitoring
    val_pred = model.predict(X_val)
    val_rmse = float(np.sqrt(np.mean((y_val - val_pred) ** 2)))
    log.info("train.regressor_done",
             n_trees=model.num_trees(), val_rmse=round(val_rmse, 6))

    return model, importances


def train_classifier(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    feature_names: list[str],
    params: dict | None = None,
) -> tuple[Any, Any, dict]:
    """
    Train a LightGBM binary classification model with Platt scaling calibration.

    Returns the fitted LightGBM model, the Platt scaler, and importances.

    Platt scaling fits a logistic regression on (val_raw_prob, y_val) so that
    final probabilities are better calibrated on the validation distribution.

    Returns:
        (lgbm_model, platt_scaler, importances)
        platt_scaler: sklearn LogisticRegression.  None if sklearn not available.
    """
    _require_lgb()
    from config.settings import LGBM_PARAMS_CLASSIFIER

    p = params or LGBM_PARAMS_CLASSIFIER.copy()

    n_es = max(1, int(len(X_train) * 0.10))
    X_es, y_es = X_train[-n_es:], y_train[-n_es:]
    X_tr, y_tr = X_train[:-n_es], y_train[:-n_es]

    train_data = lgb.Dataset(X_tr, label=y_tr, feature_name=feature_names)
    es_data    = lgb.Dataset(X_es, label=y_es, feature_name=feature_names,
                              reference=train_data)

    callbacks = [
        lgb.early_stopping(stopping_rounds=50, verbose=False),
        lgb.log_evaluation(period=-1),
    ]

    model = lgb.train(
        p,
        train_set=train_data,
        valid_sets=[es_data],
        callbacks=callbacks,
    )

    importances = {
        "gain":  model.feature_importance(importance_type="gain").tolist(),
        "split": model.feature_importance(importance_type="split").tolist(),
    }

    # Platt calibration on validation fold
    val_raw = model.predict(X_val)
    platt = _fit_platt(val_raw, y_val)

    if platt is not None:
        val_prob = platt.predict_proba(val_raw.reshape(-1, 1))[:, 1]
        from atlas_research.models.evaluate import brier_score, roc_auc
        log.info(
            "train.classifier_done",
            n_trees=model.num_trees(),
            val_auc=round(roc_auc(y_val, val_prob), 4),
            val_brier=round(brier_score(y_val, val_prob), 4),
        )
    else:
        log.info("train.classifier_done",
                 n_trees=model.num_trees(), calibration="none (sklearn missing)")

    return model, platt, importances


def _fit_platt(raw_scores: np.ndarray, y_true: np.ndarray) -> Any | None:
    """Fit a Platt scaler (logistic regression on raw scores)."""
    try:
        from sklearn.linear_model import LogisticRegression
        platt = LogisticRegression(C=1.0, solver="lbfgs", max_iter=500)
        platt.fit(raw_scores.reshape(-1, 1), y_true)
        return platt
    except ImportError:
        log.warning("train.platt_skipped", reason="sklearn not installed")
        return None


def predict_regressor(model: Any, X: np.ndarray) -> np.ndarray:
    """Generate predictions from a trained LightGBM regressor."""
    return model.predict(X).astype(np.float64)


def predict_classifier(
    model: Any,
    platt: Any | None,
    X: np.ndarray,
) -> np.ndarray:
    """
    Generate calibrated probabilities from a trained LightGBM classifier.
    Returns raw sigmoid probabilities if platt is None.
    """
    raw = model.predict(X)
    if platt is not None:
        return platt.predict_proba(raw.reshape(-1, 1))[:, 1].astype(np.float64)
    return raw.astype(np.float64)


# ---------------------------------------------------------------------------
# Bundled model container (both models in one artifact)
# ---------------------------------------------------------------------------

class TrainedModelBundle:
    """
    Container for both the regressor and classifier from one training run.
    Saved as a single joblib artifact so prediction only loads one file.
    """
    def __init__(
        self,
        regressor: Any,
        classifier: Any,
        platt: Any | None,
        feature_names: list[str],
        train_end: date,
        model_version: str,
        reg_importances: dict,
        clf_importances: dict,
    ) -> None:
        self.regressor       = regressor
        self.classifier      = classifier
        self.platt           = platt
        self.feature_names   = feature_names
        self.train_end       = train_end
        self.model_version   = model_version
        self.reg_importances = reg_importances
        self.clf_importances = clf_importances

    def predict_return(self, X: np.ndarray) -> np.ndarray:
        return predict_regressor(self.regressor, X)

    def predict_prob(self, X: np.ndarray) -> np.ndarray:
        return predict_classifier(self.classifier, self.platt, X)
