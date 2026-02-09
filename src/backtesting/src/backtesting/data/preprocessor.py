import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from typing import Tuple

from backtesting.configs.experiment import ExperimentConfig


class DataPreprocessor:
    def __init__(self, experiment_config: ExperimentConfig):
        self.experiment_config = experiment_config
        self.exogenous_columns = experiment_config.exogenous_features
        self.feature_scaler = StandardScaler()
        self.target_scaler = StandardScaler()

    def generate_full_feature_matrix(
        self, dataframe: pd.DataFrame | None = None
    ) -> pd.DataFrame:
        if dataframe is None:
            dataframe = self._load_data()
        hourly_dataframe = dataframe.copy()
        daily_prices = self._pivot_hourly_to_daily(
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

    def _pivot_hourly_to_daily(
        self, dataframe_copy: pd.DataFrame, column: str
    ) -> pd.DataFrame:
        dataframe_copy: pd.DataFrame = dataframe_copy[[column]].copy()

        index: pd.DatetimeIndex = dataframe_copy.index
        dates: np.ndarray = index.date
        hours: pd.Index = index.hour

        dataframe_copy["date"] = dates
        dataframe_copy["hour"] = hours

        pivoted: pd.DataFrame = dataframe_copy.pivot(
            index="date", columns="hour", values=column
        )
        pivoted.columns = [f"{column}_hour{hour}" for hour in range(24)]

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
        For each exogenous column: 3 blocks x 24 hours = 72 features per column.
        """
        if not self.exogenous_columns:
            return pd.DataFrame()

        all_blocks = []
        for column in self.exogenous_columns:
            daily = self._pivot_hourly_to_daily(hourly_dataframe, column)
            all_blocks.append(daily.copy().add_prefix(f"{column}_d0_"))
            all_blocks.append(daily.shift(1).add_prefix(f"{column}_d1_"))
            all_blocks.append(daily.shift(7).add_prefix(f"{column}_d7_"))
        return pd.concat(all_blocks, axis=1)

    def _add_calendar_dummies(self, index: pd.Index) -> pd.DataFrame:
        """Creates 7 binary columns for day-of-week seasonality"""
        dates = pd.to_datetime(index)
        dummies = pd.get_dummies(dates.dayofweek, prefix="day")
        dummies.index = index
        return dummies

    def _load_data(self) -> pd.DataFrame:
        dataframe = pd.read_csv(
            self.experiment_config.data_path,
            parse_dates=["timestamp"],
            index_col="timestamp",
        )
        return dataframe

    def build_dataset(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        dataframe = self._load_data()
        features = self.generate_full_feature_matrix(dataframe)
        targets = self._pivot_hourly_to_daily(
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


if __name__ == "__main__":
    test_config = ExperimentConfig(
        experiment_name="test_experiment",
        results_dir="/tmp/test_results",
        data_path="src/backtesting/src/backtesting/data/DE_data.csv",
        target_column="price",
        model_type="LEAR",
        exogenous_features=["exogenous_1", "exogenous_2"],
        model_params={"alpha": 0.1},
    )

    data_preprocessor = DataPreprocessor(test_config)
    feature_matrix = data_preprocessor.build_dataset()
    print(feature_matrix)
