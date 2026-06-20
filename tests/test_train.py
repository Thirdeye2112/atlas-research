"""
Phase 2 classifier-training tests.

Unlike test_models.py these exercise real LightGBM models (no DB, no file I/O).
Covers: Platt calibration must be fit on the early-stopping holdout, never on
the validation fold it later scores (the original bug this guards against).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytest.importorskip("lightgbm")

from atlas_research.models import train as train_mod
from atlas_research.models.train import train_classifier

FAST_PARAMS = {
    "n_estimators": 50, "learning_rate": 0.1, "max_depth": 3,
    "num_leaves": 15, "min_child_samples": 20, "n_jobs": -1,
    "random_state": 42, "verbose": -1,
}


def _make_classification_data(n=4000, n_features=5, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, n_features))
    logits = X[:, 0] * 2.0 - X[:, 1] * 1.0
    p = 1 / (1 + np.exp(-logits))
    y = (rng.uniform(size=n) < p).astype(np.float64)
    return X, y


class TestPlattNoLeak:
    def test_platt_fit_on_es_holdout_not_val(self, monkeypatch):
        X, y = _make_classification_data()
        split = int(len(X) * 0.7)
        X_train, y_train = X[:split], y[:split]
        X_val, y_val = X[split:], y[split:]

        n_es = max(1, int(len(X_train) * 0.10))
        expected_y_es = y_train[-n_es:]

        captured = {}
        real_fit_platt = train_mod._fit_platt

        def spy_fit_platt(raw_scores, y_true):
            captured["raw_scores"] = raw_scores
            captured["y_true"] = y_true
            return real_fit_platt(raw_scores, y_true)

        monkeypatch.setattr(train_mod, "_fit_platt", spy_fit_platt)

        _, platt, _ = train_classifier(
            X_train, y_train, X_val, y_val,
            feature_names=[f"f{i}" for i in range(X.shape[1])],
            params=FAST_PARAMS,
        )

        assert platt is not None, "raw scores were degenerate for this seed/params"
        assert "y_true" in captured, "Platt calibrator was never fit"
        # Must be fit on the early-stopping holdout slice...
        assert len(captured["y_true"]) == n_es
        np.testing.assert_array_equal(captured["y_true"], expected_y_es)
        # ...and NOT on the validation fold it is later scored against.
        assert len(captured["y_true"]) != len(y_val)

    def test_degenerate_raw_std_skips_calibration(self):
        # Zero-variance features force every prediction to the same leaf,
        # i.e. raw_std == 0 < CALIBRATION_MIN_STD -> calibration must be skipped
        # rather than fitting a near-zero-slope scaler on constant input.
        n = 200
        X = np.zeros((n, 3))
        y = np.array([0.0, 1.0] * (n // 2))
        degenerate_params = {
            "n_estimators": 1, "learning_rate": 0.01, "max_depth": 1,
            "num_leaves": 2, "min_child_samples": 1, "n_jobs": -1,
            "random_state": 42, "verbose": -1,
        }

        _, platt, _ = train_classifier(
            X[:150], y[:150], X[150:], y[150:],
            feature_names=["a", "b", "c"], params=degenerate_params,
        )

        assert platt is None
