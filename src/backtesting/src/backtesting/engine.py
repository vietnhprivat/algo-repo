import pandas as pd
import numpy as np
from typing import List, Tuple
from backtesting.models.base import BaseModel
from backtesting.configs.experiment import ExperimentConfig

class BacktestEngine:
    def __init__(self, config: ExperimentConfig):
        self.windows: List[int] = config.calibration_windows
        self.refit_interval: int = config.refit_interval

    def _get_window_slice(self, df: pd.DataFrame, date: pd.Timestamp, size: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        pass

    def _run_ensemble_forecast(self, model: BaseModel, df: pd.DataFrame, date: pd.Timestamp) -> np.ndarray:
        pass

    def run(self, model: BaseModel, df: pd.DataFrame, test_dates: pd.DatetimeIndex) -> pd.DataFrame:
        pass