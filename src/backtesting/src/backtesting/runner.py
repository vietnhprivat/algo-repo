from typing import Callable

import pandas as pd

from backtesting.configs.experiment import ExperimentConfig
from backtesting.data.preprocessor import DataPreprocessor
from backtesting.engine import BacktestEngine
from backtesting.models import BaseModel, get_model

class BacktestRunner:
    def __init__(self, config: ExperimentConfig):
        self.config = config

    def _get_model_factory(self) -> Callable[[], BaseModel]:
        """Return a factory so each calibration window gets a fresh model."""
        def factory() -> BaseModel:
            return get_model(self.config.model_type, **self.config.model_params)
        
        return factory

    def _build_test_dates(self, index: pd.DatetimeIndex) -> pd.DatetimeIndex:
        start_date = pd.to_datetime(self.config.test_start_date)
        end_date = pd.to_datetime(self.config.test_end_date)
        test_dates = index[(index >= start_date) & (index <= end_date)]
        
        if len(test_dates) == 0:
            raise ValueError(
                "No test dates found in dataset for the configured test range."
            )
        
        return test_dates

    def _load_and_preprocess_data(self) -> tuple[pd.DataFrame, pd.DataFrame, pd.DatetimeIndex]:
        preprocessor = DataPreprocessor(self.config)
        features, targets = preprocessor.build_dataset()
        test_dates = self._build_test_dates(features.index)

        return features, targets, test_dates

    def _prepare_outputs(
        self,
        forecasts: pd.DataFrame,
        actuals: pd.DataFrame,
    ) -> dict[str, pd.DataFrame]:
        return {"forecasts": forecasts, "actuals": actuals}

    def execute(self):
        print(f"Running Experiment: {self.config.experiment_name}")
        
        features, targets, test_dates = self._load_and_preprocess_data()
        model_factory = self._get_model_factory()
        engine = BacktestEngine(self.config)

        forecasts, actuals = engine.run(model_factory, features, targets, test_dates)
        print("Backtest completed.")

        return self._prepare_outputs(forecasts, actuals)
