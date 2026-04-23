from __future__ import annotations

from abc import abstractmethod

import numpy as np
from sklearn.base import BaseEstimator

from price_forecasting.models.base import BaseModel


class SklearnModel(BaseModel):
    """
    Abstract base for sklearn estimators with native multi-output support.

    Use this for models that accept a 2-D target matrix directly (e.g. RandomForest).
    For single-output estimators that need per-period training, use GBTModel instead.
    """

    def __init__(self) -> None:
        self._estimator: BaseEstimator | None = None

    @abstractmethod
    def _build_estimator(self) -> BaseEstimator:
        """Return an unfitted sklearn multi-output-capable estimator."""

    def fit(self, features: np.ndarray, targets: np.ndarray) -> None:
        self._estimator = self._build_estimator()
        self._estimator.fit(features, targets)

    def predict_day(self, features: np.ndarray) -> np.ndarray:
        if self._estimator is None:
            raise RuntimeError(f"{self.__class__.__name__} must be fit before prediction.")
        return self._estimator.predict(features).squeeze(axis=0)
