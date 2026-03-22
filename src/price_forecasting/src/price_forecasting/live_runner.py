import pandas as pd

from price_forecasting.configs import ExperimentConfig
from price_forecasting.data.preprocessor import DataPreprocessor
from price_forecasting.backtesting import BacktestEngine
from price_forecasting.models import BaseModel, get_model


class LiveRunner:
    def __init__(self, config: ExperimentConfig):
        self.config = config

    def _get_model_factory(self):
        def factory() -> BaseModel:
            return get_model(self.config.model_type, **self.config.model_params)

        return factory

    def _load_and_preprocess_data(
        self, dataframe: pd.DataFrame | None = None
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        preprocessor = DataPreprocessor(self.config)
        features, targets = preprocessor.build_dataset(dataframe)
        return features, targets

    def run_live(
        self, target_date: str, dataframe: pd.DataFrame | None = None
    ) -> pd.Series:
        features, targets = self._load_and_preprocess_data(dataframe)
        target_timestamp = pd.to_datetime(target_date)
        model_factory = self._get_model_factory()
        engine = BacktestEngine(self.config)

        if target_timestamp not in features.index:
            raise ValueError("Target date not found in available data.")

        prediction = engine._ensemble_forecast(
            model_factory, features, targets, target_timestamp
        )

        n_periods = len(prediction)
        output_index = [f"p{p}" for p in range(n_periods)]
        return pd.Series(prediction, index=output_index, name=target_date)
