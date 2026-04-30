import numpy as np
from xgboost import XGBRegressor

from price_forecasting.models.gbt_base import GBTModel


def _cuda_available() -> bool:
    try:
        import xgboost
        return xgboost.build_info().get("USE_CUDA", False)
    except Exception:
        return False


class XGBoostModel(GBTModel):
    """
    XGBoost for day-ahead electricity price forecasting.

    Trains one XGBRegressor per output period with native early stopping via eval_set.
    """

    def __init__(
        self,
        n_estimators: int = 300,
        max_depth: int = 6,
        learning_rate: float = 0.05,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        early_stopping_rounds: int = 25,
        random_state: int = 42,
        n_jobs: int = 12,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self.early_stopping_rounds = early_stopping_rounds
        self.random_state = random_state
        self.n_jobs = n_jobs

    def _build_estimator(self) -> XGBRegressor:
        return XGBRegressor(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            subsample=self.subsample,
            colsample_bytree=self.colsample_bytree,
            early_stopping_rounds=self.early_stopping_rounds,
            random_state=self.random_state,
            n_jobs=self.n_jobs,
            verbosity=0,
        )

    def _fit_period(
        self,
        estimator: XGBRegressor,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
    ) -> None:
        estimator.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
