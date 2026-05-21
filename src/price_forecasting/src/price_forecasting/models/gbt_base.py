from __future__ import annotations

from abc import abstractmethod

import numpy as np

from price_forecasting.models.base import BaseModel


class GBTModel(BaseModel):
    """
    Abstract base for gradient boosted tree models (currently: XGBoost).

    Trains one estimator per output period — correct for single-output libraries.
    Subclasses implement _build_estimator() and override _fit_period() to add
    native early stopping via eval_set.
    """

    def __init__(self, validation_fraction: float = 0.2) -> None:
        self.validation_fraction = validation_fraction
        self._period_models: dict[int, object] = {}

    @abstractmethod
    def _build_estimator(self) -> object:
        """Return a fresh unfitted single-output sklearn-API regressor."""

    def _fit_period(
        self,
        estimator: object,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
    ) -> None:
        """Fit one period's estimator. Override to add eval_set early stopping."""
        estimator.fit(X_train, y_train)  # type: ignore[union-attr]

    def fit(self, features: np.ndarray, targets: np.ndarray) -> None:
        n_samples = features.shape[0]
        n_periods = targets.shape[1]

        n_val = max(1, int(n_samples * self.validation_fraction))
        n_train = n_samples - n_val

        X_train, X_val = features[:n_train], features[n_train:]
        y_train, y_val = targets[:n_train], targets[n_train:]

        self._period_models = {}
        for i in range(n_periods):
            estimator = self._build_estimator()
            self._fit_period(estimator, X_train, y_train[:, i], X_val, y_val[:, i])
            self._period_models[i] = estimator

    def predict_day(self, features: np.ndarray) -> np.ndarray:
        if not self._period_models:
            raise RuntimeError(f"{self.__class__.__name__} must be fit before prediction.")
        return np.array([
            self._period_models[i].predict(features).item()  # type: ignore[union-attr]
            for i in range(len(self._period_models))
        ])
