"""Random-forest habitat-suitability model (development phase P3).

The estimator for the suggested-fish layer: cheap, interpretable and robust
to modest occurrence counts. Suitability is the (calibrated) probability of
presence given environmental features, clamped to [0, 1].

FEATURE CONTRACT - train/serve parity is the rule
-------------------------------------------------
The features here are exactly the ones the SERVING path can supply for every
grid cell, so a model trained by scripts/train_habitat.py can be applied live
without a silent mismatch:

  sst_c                  live sea-surface temperature at the cell
                         (training: OBIS reanalysis field - the one
                         documented product shift)
  distance_to_shore_km   training: OBIS `shoredistance`;
                         serving: computed from the ocean mask
  month_sin, month_cos   calendar position (cyclic)

Chlorophyll, bathymetry, salinity and currents were earlier candidates and
are deliberately NOT features: none can be supplied live without a new data
source, and a feature present in training but absent - or defaulted - at
inference is how a model silently degrades. They remain useful as diagnostics
in the training table.

`modelling_path` in the species registry still describes the paper's blended
design (learned tendency + habitat fallback); until a tendency model exists,
this habitat estimate is what the suggestion layer uses, and the API response
says which method produced a zone.
"""
from __future__ import annotations

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

FEATURE_ORDER = ["sst_c", "distance_to_shore_km", "month_sin", "month_cos"]

ARTIFACT_VERSION = 2


def build_features(sst_c: float, distance_to_shore_km: float,
                   month: int) -> np.ndarray:
    """One feature row, in FEATURE_ORDER."""
    ang = 2.0 * np.pi * float(month) / 12.0
    return np.array([[float(sst_c), float(distance_to_shore_km),
                      np.sin(ang), np.cos(ang)]])


class HabitatModel:
    def __init__(self, n_estimators: int = 400, max_depth: int = 12,
                 seed: int = 42):
        self.clf = RandomForestClassifier(
            n_estimators=n_estimators, max_depth=max_depth,
            random_state=seed, n_jobs=-1, class_weight="balanced_subsample")
        self.calibrator = None          # optional isotonic map raw -> probability
        self.metadata: dict = {}

    # -- sklearn-compatible surface ---------------------------------------
    def fit(self, X: np.ndarray, y: np.ndarray) -> "HabitatModel":
        self.clf.fit(X, y)
        return self

    def _raw(self, X: np.ndarray) -> np.ndarray:
        proba = self.clf.predict_proba(X)
        idx = list(self.clf.classes_).index(1)
        return np.clip(proba[:, idx], 0.0, 1.0)

    def suitability(self, X: np.ndarray) -> np.ndarray:
        """Probability of presence in [0, 1], calibrated when a calibrator
        is attached (isotonic regression fitted on out-of-fold predictions)."""
        if X.ndim == 1:
            X = X.reshape(1, -1)
        raw = self._raw(X)
        if self.calibrator is not None:
            try:
                return np.clip(self.calibrator.predict(raw), 0.0, 1.0)
            except Exception:  # noqa: BLE001 - fall back to raw probabilities
                return raw
        return raw

    # -- persistence --------------------------------------------------------
    def save(self, path: str) -> None:
        joblib.dump({"version": ARTIFACT_VERSION, "features": FEATURE_ORDER,
                     "clf": self.clf, "calibrator": self.calibrator,
                     "metadata": self.metadata}, path)

    @classmethod
    def load(cls, path: str) -> "HabitatModel":
        """Load an artifact; also accepts a bare estimator written by an
        older version of this module."""
        payload = joblib.load(path)
        model = cls.__new__(cls)
        if isinstance(payload, dict) and "clf" in payload:
            model.clf = payload["clf"]
            model.calibrator = payload.get("calibrator")
            model.metadata = payload.get("metadata") or {}
        else:
            model.clf = payload
            model.calibrator = None
            model.metadata = {}
        return model
