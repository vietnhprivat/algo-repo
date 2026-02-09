import json
from pathlib import Path
from typing import Callable

import pandas as pd

from backtesting.configs.experiment import ExperimentConfig
from backtesting.data.preprocessor import DataPreprocessor
from backtesting.evaluation import (
    build_weekly_naive,
    compute_metrics_per_hour,
    compute_metrics_summary,
)
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

        outputs = self._prepare_outputs(forecasts, actuals)
        self._save_outputs(outputs)
        return outputs

    def _save_outputs(self, outputs: dict[str, pd.DataFrame]) -> None:
        results_directory = Path(self.config.results_dir)
        results_directory.mkdir(parents=True, exist_ok=True)

        forecasts = outputs["forecasts"]
        actuals = outputs["actuals"]

        forecasts_path = (
            results_directory / f"{self.config.experiment_name}_forecasts.csv"
        )
        actuals_path = results_directory / f"{self.config.experiment_name}_actuals.csv"
        forecasts.to_csv(forecasts_path)
        actuals.to_csv(actuals_path)

        naive_forecasts = build_weekly_naive(actuals)
        metrics_summary = compute_metrics_summary(forecasts, actuals, naive_forecasts)
        metrics_per_hour = compute_metrics_per_hour(forecasts, actuals, naive_forecasts)

        metrics_summary_path = (
            results_directory / f"{self.config.experiment_name}_metrics.json"
        )
        metrics_per_hour_path = (
            results_directory / f"{self.config.experiment_name}_metrics_per_hour.csv"
        )

        metrics_summary_path.write_text(json.dumps(metrics_summary, indent=2))
        metrics_per_hour.to_csv(metrics_per_hour_path, index=False)

        print(f"Saved forecasts to {forecasts_path}")
        print(f"Saved actuals to {actuals_path}")
        print(f"Saved metrics to {metrics_summary_path}")
        print(f"Saved per-hour metrics to {metrics_per_hour_path}")


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
