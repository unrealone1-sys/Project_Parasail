"""Random-forest habitat-suitability model (development phase P3).

The fallback estimator for data-poor taxa: cheap, interpretable and robust
to modest occurrence counts. Suitability is the calibrated probability of
presence given environmental features; output is clamped to [0, 1] and used
as H-hat in the catch composite C = lambda*Chat + (1 - lambda)*Hhat.
"""
from __future__ import annotations

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

FEATURE_ORDER = [
    "sst_c", "sst_anomaly_k", "chlorophyll_a", "depth_m",
    "wind_stress", "month_sin", "month_cos",
]


def build_features(sst_c: float, climatology_c: float, chlorophyll_a: float,
                   depth_m: float, wind_ms: float, month: int) -> np.ndarray:
    return np.array([[
        sst_c,
        sst_c - climatology_c,
        chlorophyll_a,
        depth_m,
        wind_ms ** 2 * 1.225e-3,          # wind_stress (bulk, linear cd)
        np.sin(2 * np.pi * month / 12.0),
        np.cos(2 * np.pi * month / 12.0),
    ]])


class HabitatModel:
    def __init__(self, n_estimators: int = 400, max_depth: int = 12,
                 seed: int = 42):
        self.clf = RandomForestClassifier(
            n_estimators=n_estimators, max_depth=max_depth,
            random_state=seed, n_jobs=-1, class_weight="balanced_subsample")

    # -- sklearn-compatible surface ---------------------------------------
    def fit(self, X: np.ndarray, y: np.ndarray) -> "HabitatModel":
        self.clf.fit(X, y)
        return self

    def suitability(self, X: np.ndarray) -> np.ndarray:
        """Probability of presence, in [0, 1]."""
        if X.ndim == 1:
            X = X.reshape(1, -1)
        proba = self.clf.predict_proba(X)
        idx = list(self.clf.classes_).index(1)
        return np.clip(proba[:, idx], 0.0, 1.0)

    # -- persistence --------------------------------------------------------
    def save(self, path: str) -> None:
        joblib.dump(self.clf, path)

    @classmethod
    def load(cls, path: str) -> "HabitatModel":
        model = cls.__new__(cls)
        model.clf = joblib.load(path)
        return model
