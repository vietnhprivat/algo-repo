import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from typing import Tuple

from price_forecasting.configs import ExperimentConfig
from price_forecasting.data.clickhouse_loader import load_dataset


class DataPreprocessor:
    def __init__(self, experiment_config: ExperimentConfig):
        self.experiment_config = experiment_config
        self.exogenous_columns = experiment_config.exogenous_curve_types
        self.feature_scaler = StandardScaler()
        self.target_scaler = StandardScaler()

    def generate_full_feature_matrix(
        self, dataframe: pd.DataFrame | None = None
    ) -> pd.DataFrame:
        if dataframe is None:
            dataframe = load_dataset(self.experiment_config)
        hourly_dataframe = dataframe.copy()
        daily_prices = self._pivot_to_daily(
            hourly_dataframe, self.experiment_config.target_column
        )

        price_lags = self._build_price_lags(daily_prices)
        exogenous_features = self._build_exogenous_features(hourly_dataframe)
        calendar_dummies = self._add_calendar_dummies(daily_prices.index)

        # 3. Concatenate and clean
        full_feature_matrix = pd.concat(
            [price_lags, exogenous_features, calendar_dummies], axis=1
        )
        return full_feature_matrix

    def transform_data(
        self,
        features_train: np.ndarray,
        targets_train: np.ndarray,
        features_test: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        features_train_scaled = self.feature_scaler.fit_transform(features_train)
        features_test_scaled = self.feature_scaler.transform(features_test)
        targets_train_scaled = self.target_scaler.fit_transform(targets_train)

        return features_train_scaled, targets_train_scaled, features_test_scaled

    def transform_features(self, features: np.ndarray) -> np.ndarray:
        return self.feature_scaler.transform(features)

    def inverse_transform_predictions(
        self, targets_pred_scaled: np.ndarray
    ) -> np.ndarray:
        targets_pred_unscaled = self.target_scaler.inverse_transform(
            targets_pred_scaled.reshape(1, -1)
        )
        return targets_pred_unscaled.flatten()

    def _detect_n_periods(self, index: pd.DatetimeIndex) -> int:
        """Detect number of periods per day from the data frequency."""
        delta = index.to_series().diff().median()
        if delta <= pd.Timedelta(minutes=15):
            return 96
        return 24

    def _pivot_to_daily(
        self, dataframe_copy: pd.DataFrame, column: str
    ) -> pd.DataFrame:
        dataframe_copy: pd.DataFrame = dataframe_copy[[column]].copy()

        index: pd.DatetimeIndex = dataframe_copy.index
        n_periods = self._detect_n_periods(index)

        dataframe_copy["date"] = index.date
        dataframe_copy["period"] = (index.hour * 60 + index.minute) // (
            1440 // n_periods
        )

        pivoted: pd.DataFrame = dataframe_copy.pivot(
            index="date", columns="period", values=column
        )
        pivoted.columns = [f"{column}_p{p}" for p in range(n_periods)]

        return pivoted

    def _build_price_lags(self, daily_prices: pd.DataFrame) -> pd.DataFrame:
        """
        Creates the 96 price features (Lags: d-1, d-2, d-3, d-7).
        This follow the LEAR model paper
        """
        lags = [1, 2, 3, 7]
        blocks = []
        for lag in lags:
            block = daily_prices.shift(lag).add_prefix(f"p_lag{lag}_")
            blocks.append(block)
        return pd.concat(blocks, axis=1)

    def _build_exogenous_features(self, hourly_dataframe: pd.DataFrame) -> pd.DataFrame:
        """
        Creates the exogenous features (d0 forecast, d-1 lag, d-7 lag).
        For each exogenous column: 3 blocks x n_periods = features per column.
        """
        if not self.exogenous_columns:
            return pd.DataFrame()

        all_blocks = []
        for column in self.exogenous_columns:
            if column not in hourly_dataframe.columns:
                continue
            daily = self._pivot_to_daily(hourly_dataframe, column)
            all_blocks.append(daily.copy().add_prefix(f"{column}_d0_"))
            all_blocks.append(daily.shift(1).add_prefix(f"{column}_d1_"))
            all_blocks.append(daily.shift(7).add_prefix(f"{column}_d7_"))
        return pd.concat(all_blocks, axis=1) if all_blocks else pd.DataFrame()

    def _add_calendar_dummies(self, index: pd.Index) -> pd.DataFrame:
        """Creates 7 binary columns for day-of-week seasonality"""
        dates = pd.to_datetime(index)
        dummies = pd.get_dummies(dates.dayofweek, prefix="day")
        dummies.index = index
        return dummies

    def build_dataset(
        self, dataframe: pd.DataFrame | None = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        if dataframe is None:
            dataframe = load_dataset(self.experiment_config)

        features = self.generate_full_feature_matrix(dataframe)
        targets = self._pivot_to_daily(
            dataframe, self.experiment_config.target_column
        )

        features.index = pd.to_datetime(features.index)
        targets.index = pd.to_datetime(targets.index)

        common_index = features.index.intersection(targets.index)
        features = features.loc[common_index].sort_index()
        targets = targets.loc[common_index].sort_index()

        valid_mask = features.notna().all(axis=1) & targets.notna().all(axis=1)
        features = features.loc[valid_mask]
        targets = targets.loc[valid_mask]

        return features, targets
