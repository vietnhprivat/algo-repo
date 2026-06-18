from typing import Dict, Iterable

import numpy as np
from sklearn.linear_model import Lasso, LassoCV
from sklearn.model_selection import TimeSeriesSplit

from price_forecasting.models.base import BaseModel


class LearModel(BaseModel):
    def __init__(
        self,
        alpha: float | None = 0.01,
        maximum_iterations: int = 5000,
        cross_validation_folds: int = 5,
        lasso_alphas: Iterable[float] | None = None,
    ) -> None:
        self.alpha = alpha
        self.maximum_iterations = maximum_iterations
        self.cross_validation_folds = cross_validation_folds
        self.lasso_alphas = list(lasso_alphas) if lasso_alphas is not None else None

        self.hourly_models: Dict[int, Lasso] = {}
        self.best_alphas: Dict[int, float] = {}

    def fit(self, features: np.ndarray, targets: np.ndarray) -> None:
        n_periods = targets.shape[1]
        for period in range(n_periods):
            targets_period = targets[:, period]

            if self.alpha in (None, "auto"):
                model = LassoCV(
                    # sklearn deprecates alphas=None (becomes 100 in 1.9); pass
                    # 100 explicitly when no grid is given to keep the same path
                    # and silence the FutureWarning.
                    alphas=self.lasso_alphas if self.lasso_alphas is not None else 100,
                    cv=TimeSeriesSplit(n_splits=self.cross_validation_folds),
                    max_iter=self.maximum_iterations,
                )
                model.fit(features, targets_period)
                self.best_alphas[period] = float(model.alpha_)
                self.hourly_models[period] = model

            else:
                model = Lasso(alpha=self.alpha, max_iter=self.maximum_iterations)
                model.fit(features, targets_period)
                self.hourly_models[period] = model

        self._n_periods = n_periods

    def predict_day(self, features: np.ndarray) -> np.ndarray:
        if not self.hourly_models:
            raise ValueError("LEAR model must be fit before prediction.")

        n_periods = len(self.hourly_models)
        predictions = np.zeros(n_periods)
        for period in range(n_periods):
            predictions[period] = self.hourly_models[period].predict(features).item()

        return predictions
