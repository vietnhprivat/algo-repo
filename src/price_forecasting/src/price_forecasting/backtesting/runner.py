import json
from pathlib import Path
from typing import Callable

import pandas as pd

from price_forecasting.configs import ExperimentConfig
from price_forecasting.data.preprocessor import DataPreprocessor
from price_forecasting.backtesting.splitting import SplitResult, split_dataset, split_by_dates
from price_forecasting.evaluation import (
    build_weekly_naive,
    compute_metrics_per_hour,
    compute_metrics_summary,
)
from price_forecasting.backtesting.engine import BacktestEngine
from price_forecasting.models import BaseModel, get_model


class BaseRunner:
    def __init__(self, config: ExperimentConfig):
        self.config = config

    def _get_model_factory(self) -> Callable[[], BaseModel]:
        def factory() -> BaseModel:
            return get_model(self.config.model_type, **self.config.model_params)

        return factory

    def _load_and_preprocess_data(
        self, dataframe: pd.DataFrame | None = None
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        preprocessor = DataPreprocessor(self.config)
        features, targets = preprocessor.build_dataset(dataframe)
        return features, targets

    def _split_data(
        self, features: pd.DataFrame, targets: pd.DataFrame
    ) -> SplitResult:
        if self.config.test_start_date and self.config.test_end_date:
            return split_by_dates(
                features,
                targets,
                self.config.test_start_date,
                self.config.test_end_date,
            )
        return split_dataset(
            features,
            targets,
            train_ratio=self.config.train_ratio,
            validation_ratio=self.config.validation_ratio,
            test_ratio=self.config.test_ratio,
        )


class BacktestRunner(BaseRunner):
    def _prepare_outputs(
        self,
        forecasts: pd.DataFrame,
        actuals: pd.DataFrame,
    ) -> dict[str, pd.DataFrame]:
        return {"forecasts": forecasts, "actuals": actuals}

    def execute(self, dataframe: pd.DataFrame | None = None):
        print(f"Running Experiment: {self.config.experiment_name}")

        features, targets = self._load_and_preprocess_data(dataframe)
        split = self._split_data(features, targets)
        test_dates = split.test.dates

        if len(test_dates) == 0:
            raise ValueError("No test dates found after splitting the dataset.")

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
