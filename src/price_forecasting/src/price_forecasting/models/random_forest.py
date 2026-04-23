from sklearn.base import BaseEstimator
from sklearn.ensemble import RandomForestRegressor

from price_forecasting.models.sklearn_base import SklearnModel


class RandomForestModel(SklearnModel):
    """
    Random Forest for day-ahead electricity price forecasting.

    RF natively supports multi-output regression (single shared forest across all periods).
    Do NOT use GBTModel for RF — that would train n_periods separate forests.
    """

    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: int | None = None,
        min_samples_leaf: int = 1,
        max_features: float = 1.0,
        random_state: int = 42,
        n_jobs: int = -1,
    ) -> None:
        super().__init__()
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.min_samples_leaf = min_samples_leaf
        self.max_features = max_features
        self.random_state = random_state
        self.n_jobs = n_jobs

    def _build_estimator(self) -> BaseEstimator:
        return RandomForestRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            min_samples_leaf=self.min_samples_leaf,
            max_features=self.max_features,
            random_state=self.random_state,
            n_jobs=self.n_jobs,
        )
