from typing import Callable

import pandas as pd

from backtesting.configs.experiment import ExperimentConfig
from backtesting.data.preprocessor import DataPreprocessor
from backtesting.engine import BacktestEngine
from backtesting.models import BaseModel, get_model


class BaseRunner:
    def __init__(self, config: ExperimentConfig):
        self.config = config

    def _get_model_factory(self) -> Callable[[], BaseModel]:
        def factory() -> BaseModel:
            return get_model(self.config.model_type, **self.config.model_params)

        return factory

    def _load_and_preprocess_data(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        preprocessor = DataPreprocessor(self.config)
        features, targets = preprocessor.build_dataset()
        return features, targets


class BacktestRunner(BaseRunner):
    def _build_test_dates(self, index: pd.DatetimeIndex) -> pd.DatetimeIndex:
        start_date = pd.to_datetime(self.config.test_start_date)
        end_date = pd.to_datetime(self.config.test_end_date)
        test_dates = index[(index >= start_date) & (index <= end_date)]

        if len(test_dates) == 0:
            raise ValueError(
                "No test dates found in dataset for the configured test range."
            )

        return test_dates

    def _prepare_outputs(
        self,
        forecasts: pd.DataFrame,
        actuals: pd.DataFrame,
    ) -> dict[str, pd.DataFrame]:
        return {"forecasts": forecasts, "actuals": actuals}

    def execute(self):
        print(f"Running Experiment: {self.config.experiment_name}")

        features, targets = self._load_and_preprocess_data()
        test_dates = self._build_test_dates(features.index)
        model_factory = self._get_model_factory()
        engine = BacktestEngine(self.config)

        forecasts, actuals = engine.run(model_factory, features, targets, test_dates)
        print("Backtest completed.")

        return self._prepare_outputs(forecasts, actuals)


class LiveRunner(BaseRunner):
    def run_live(self, target_date: str) -> pd.Series:
        features, targets = self._load_and_preprocess_data()
        target_timestamp = pd.to_datetime(target_date)
        model_factory = self._get_model_factory()
        engine = BacktestEngine(self.config)

        if target_timestamp not in features.index:
            raise ValueError("Target date not found in available data.")

        prediction = engine._ensemble_forecast(
            model_factory, features, targets, target_timestamp
        )

        output_index = [f"hour{hour}" for hour in range(24)]
        return pd.Series(prediction, index=output_index, name=target_date)
