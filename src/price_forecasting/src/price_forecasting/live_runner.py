import time
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from price_forecasting.configs import ExperimentConfig
from price_forecasting.data.preprocessor import DataPreprocessor
from price_forecasting.data.clickhouse_loader import load_dataset
from price_forecasting.backtesting import BacktestEngine
from price_forecasting.models import BaseModel, get_model


@dataclass
class LiveResult:
    """Enriched result from a live prediction run."""

    prediction: pd.Series
    data_start_utc: datetime
    data_end_utc: datetime
    training_duration_seconds: float
    trained_models: dict  # window_size -> BaseModel
    target_date: str = ""  # the date actually forecast (resolved when not given)


class LiveRunner:
    def __init__(self, config: ExperimentConfig):
        self.config = config

    def _get_model_factory(self):
        def factory() -> BaseModel:
            model = get_model(self.config.model_type, **self.config.model_params)
            model._config = self.config
            return model

        return factory

    def _get_model_factory_with_seed(self, seed: int):
        def factory():
            params = dict(self.config.model_params)
            params["random_seed"] = seed
            model = get_model(self.config.model_type, **params)
            model._config = self.config
            return model

        return factory

    def _load_and_preprocess_data(
        self, target_date: str, dataframe: pd.DataFrame | None = None
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        preprocessor = DataPreprocessor(self.config)
        features, targets = preprocessor.build_dataset_for_prediction(
            target_date, dataframe
        )
        return features, targets

    def run_live_with_metadata(
        self, target_date: str | None = None, dataframe: pd.DataFrame | None = None
    ) -> LiveResult:
        # No explicit target: forecast the most recent day with complete inputs.
        if target_date is None:
            if dataframe is None:
                dataframe = load_dataset(self.config)
            target_date = (
                DataPreprocessor(self.config)
                .latest_complete_target(dataframe)
                .strftime("%Y-%m-%d")
            )
        features, targets = self._load_and_preprocess_data(target_date, dataframe)
        target_timestamp = pd.to_datetime(target_date)
        model_factory = self._get_model_factory()
        engine = BacktestEngine(self.config)

        if target_timestamp not in features.index:
            raise ValueError("Target date not found in available data.")

        t0 = time.perf_counter()
        if self.config.model_type == "dnn" and self.config.n_dnn_ensemble > 1:
            preds = []
            trained_models: dict = {}
            for seed in range(self.config.n_dnn_ensemble):
                seed_factory = self._get_model_factory_with_seed(seed)
                seed_engine = BacktestEngine(self.config)
                preds.append(seed_engine._ensemble_forecast(
                    seed_factory, features, targets, target_timestamp
                ))
                for ws, state in seed_engine._window_state.items():
                    trained_models[(seed, ws)] = state.model
            prediction = np.mean(preds, axis=0)
        else:
            prediction = engine._ensemble_forecast(
                model_factory, features, targets, target_timestamp
            )
            trained_models = {
                ws: state.model for ws, state in engine._window_state.items()
            }
        training_duration = time.perf_counter() - t0

        n_periods = len(prediction)
        output_index = [f"p{p}" for p in range(n_periods)]
        prediction_series = pd.Series(prediction, index=output_index, name=target_date)

        data_start_utc = features.index.min().to_pydatetime().replace(tzinfo=timezone.utc)
        data_end_utc = features.index.max().to_pydatetime().replace(tzinfo=timezone.utc)

        return LiveResult(
            prediction=prediction_series,
            data_start_utc=data_start_utc,
            data_end_utc=data_end_utc,
            training_duration_seconds=training_duration,
            trained_models=trained_models,
            target_date=target_date,
        )

    def run_live(
        self, target_date: str | None = None, dataframe: pd.DataFrame | None = None
    ) -> pd.Series:
        result = self.run_live_with_metadata(target_date, dataframe)
        return result.prediction
