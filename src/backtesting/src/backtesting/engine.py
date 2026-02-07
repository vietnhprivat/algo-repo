from dataclasses import dataclass
from typing import Callable, Dict, Tuple

import numpy as np
import pandas as pd

from backtesting.configs.experiment import ExperimentConfig
from backtesting.data.preprocessor import DataPreprocessor
from backtesting.models import BaseModel

ModelFactory = Callable[[], BaseModel]


@dataclass
class WindowState:
    last_fit_date: pd.Timestamp
    model: BaseModel
    preprocessor: DataPreprocessor

class BacktestEngine:
    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.windows = config.calibration_windows
        self.refit_interval_days = config.refit_interval_days
        self._window_state: Dict[int, WindowState] = {}

    def _slice_data(
        self,
        features: pd.DataFrame,
        targets: pd.DataFrame,
        target_date: pd.Timestamp,
        window_size: int,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        if target_date not in features.index:
            raise ValueError(f"Target date {target_date.date()} not found in feature index.")

        start_date = target_date - pd.Timedelta(days=window_size)
        end_date = target_date - pd.Timedelta(days=1)

        train_mask = (features.index >= start_date) & (features.index <= end_date)
        features_train_frame = features.loc[train_mask]     # shape: (window_size, num_features)
        targets_train_frame = targets.loc[train_mask]       # shape: (window_size, 24)
        features_test_frame = features.loc[[target_date]]   # shape: (1, num_features)

        if len(features_train_frame) < window_size:
            raise ValueError(
                f"Not enough training data for window={window_size} "
                f"on target date {target_date.date()}."
            )

        return (
            features_train_frame.to_numpy(),
            targets_train_frame.to_numpy(),
            features_test_frame.to_numpy(),
        )

    def _get_test_features(self, features: pd.DataFrame, target_date: pd.Timestamp) -> np.ndarray:
        if target_date not in features.index:
            raise ValueError(f"Target date {target_date.date()} not found in feature index.")
        return features.loc[[target_date]].to_numpy()

    def _fit_and_predict_window(
        self,
        model_factory: ModelFactory,
        features: pd.DataFrame,
        targets: pd.DataFrame,
        target_date: pd.Timestamp,
        window_size: int,
    ) -> np.ndarray:
        state = self._window_state.get(window_size)
        if state is None:
            days_since_last_fit = None
        else:
            days_since_last_fit = (target_date - state.last_fit_date).days

        needs_refit: bool = (
            state is None
            or days_since_last_fit is None
            or days_since_last_fit >= self.refit_interval_days
        )

        if needs_refit:
            features_train, targets_train, features_test = self._slice_data(
                features, targets, target_date, window_size
            )
            preprocessor = DataPreprocessor(self.config)
            features_train_scaled, targets_train_scaled, features_test_scaled = preprocessor.transform_data(
                features_train, targets_train, features_test
            )
            model = model_factory()
            model.fit(features_train_scaled, targets_train_scaled)
            prediction_scaled = model.predict_day(features_test_scaled)
            prediction = preprocessor.inverse_transform_predictions(prediction_scaled)

            self._window_state[window_size] = WindowState(
                last_fit_date=target_date,
                model=model,
                preprocessor=preprocessor,
            )
            return prediction

        features_test = self._get_test_features(features, target_date)
        features_test_scaled = state.preprocessor.transform_features(features_test)
        prediction_scaled = state.model.predict_day(features_test_scaled)
        return state.preprocessor.inverse_transform_predictions(prediction_scaled)

    def _ensemble_forecast(
        self,
        model_factory: ModelFactory,
        features: pd.DataFrame,
        targets: pd.DataFrame,
        date: pd.Timestamp,
    ) -> np.ndarray:
        window_forecasts = []

        for window_size in self.windows:
            prediction = self._fit_and_predict_window(
                model_factory, features, targets, date, window_size
            )
            
            window_forecasts.append(prediction)

        if not window_forecasts:
            raise ValueError(f"No valid windows for target date {date.date()}.")

        return np.mean(window_forecasts, axis=0)

    def run(
        self,
        model_factory: ModelFactory,
        features: pd.DataFrame,
        targets: pd.DataFrame,
        test_dates: pd.DatetimeIndex,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        self._window_state.clear()
        forecasts = []
        actuals = []

        print(f"Starting backtest on {len(test_dates)} days...")

        for date in test_dates:
            daily_prediction = self._ensemble_forecast(
                model_factory, features, targets, date
            )
            forecasts.append(daily_prediction)
            actuals.append(targets.loc[date].to_numpy())

            print(f"Forecasted {date.date()}")

        columns = [f"h{i}" for i in range(24)]
        forecast_df = pd.DataFrame(forecasts, index=test_dates, columns=columns)
        actuals_df = pd.DataFrame(actuals, index=test_dates, columns=columns)
        return forecast_df, actuals_df
