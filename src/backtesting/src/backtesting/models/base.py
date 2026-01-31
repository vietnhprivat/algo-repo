from abc import ABC, abstractmethod
import numpy as np
import pandas as pd


class BaseModel(ABC):
    
    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        pass

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        pass

    @abstractmethod
    def recalibrate_and_forecast_next_day(
        self,
        df: pd.DataFrame,
        calibration_window: int | None,
        next_day_date: pd.Timestamp,
        target_column: str,
        feature_columns: list
    ) -> np.ndarray:
        pass
