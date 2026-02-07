from typing import Dict, Iterable

import numpy as np
from sklearn.linear_model import Lasso, LassoCV
from sklearn.model_selection import TimeSeriesSplit

from backtesting.models.base import BaseModel


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
        for hour in range(24):
            targets_hour = targets[:, hour]

            if self.alpha in (None, "auto"):
                model = LassoCV(
                    alphas=self.lasso_alphas,
                    cv=TimeSeriesSplit(n_splits=self.cross_validation_folds),
                    max_iter=self.maximum_iterations,
                )
                model.fit(features, targets_hour)
                self.best_alphas[hour] = float(model.alpha_)
                self.hourly_models[hour] = model
            
            else:
                model = Lasso(alpha=self.alpha, max_iter=self.maximum_iterations)
                model.fit(features, targets_hour)
                self.hourly_models[hour] = model

    def predict_day(self, features: np.ndarray) -> np.ndarray:
        if len(self.hourly_models) != 24:
            raise ValueError("LEAR model must be fit before prediction.")

        predictions = np.zeros(24)
        for hour in range(24):
            predictions[hour] = self.hourly_models[hour].predict(features).item()

        return predictions
