import numpy as np
import pandas as pd
from typing import List


from sklearn.preprocessing import StandardScaler
from typing import Tuple

from price_forecasting.configs import ExperimentConfig
from price_forecasting.data.clickhouse_loader import load_dataset


def detect_n_periods(index: pd.DatetimeIndex) -> int:
    """Detect number of periods per day from the data frequency."""
    delta = index.to_series().diff().median()
    if delta <= pd.Timedelta(minutes=15):
        return 96
    return 24


def pivot_to_daily(dataframe: pd.DataFrame, column: str) -> pd.DataFrame:
    """Pivot an hourly (or 15-min) column into a daily wide matrix.

    Returns a DataFrame indexed by date with columns {column}_p0..pN.
    """
    df: pd.DataFrame = dataframe[[column]].copy()
    index: pd.DatetimeIndex = df.index
    n_periods = detect_n_periods(index)

    df["date"] = index.date
    df["period"] = (index.hour * 60 + index.minute) // (1440 // n_periods)

    pivoted: pd.DataFrame = df.pivot(
        index="date", columns="period", values=column
    )
    pivoted.columns = [f"{column}_p{p}" for p in range(n_periods)]
    return pivoted


class DataPreprocessor:
    def __init__(self, experiment_config: ExperimentConfig):
        self.experiment_config = experiment_config
        self.feature_scaler = StandardScaler()
        self.target_scaler = self._build_target_scaler(experiment_config.target_scaler)

        if experiment_config.feature_transformers is not None:
            self.transformers = experiment_config.feature_transformers
        else:
            from price_forecasting.data.transformers import default_transformers_for_model
            self.transformers = default_transformers_for_model(experiment_config.exogenous_columns)

    @staticmethod
    def _build_target_scaler(name: str):
        if name == "asinh":
            from price_forecasting.data.asinh_scaler import AsinhScaler
            return AsinhScaler()
        if name == "standard":
            return StandardScaler()
        raise ValueError(f"Unknown target_scaler: {name!r}")

    def generate_full_feature_matrix(
        self, dataframe: pd.DataFrame | None = None
    ) -> pd.DataFrame:
        if dataframe is None:
            dataframe = load_dataset(self.experiment_config)
        hourly_dataframe = dataframe.copy()
        daily_prices = pivot_to_daily(hourly_dataframe, self.experiment_config.target_column)

        blocks : List[pd.DataFrame] = []
        for transformer in self.transformers:
            block = transformer.transform(hourly_dataframe, daily_prices)
            if not block.empty:
                blocks.append(block)

        full_feature_matrix = pd.concat(blocks, axis=1)
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

    def build_dataset(
        self, dataframe: pd.DataFrame | None = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Return (features, targets) aligned on common valid dates.

        If dataframe is None, loads from ClickHouse via the experiment config.
        Pass a DataFrame directly to skip the DB call (e.g. in tests).
        """
        if dataframe is None:
            dataframe = load_dataset(self.experiment_config)

        features = self.generate_full_feature_matrix(dataframe)
        targets = pivot_to_daily(dataframe, self.experiment_config.target_column)

        features.index = pd.to_datetime(features.index)
        targets.index = pd.to_datetime(targets.index)

        common_index = features.index.intersection(targets.index)
        features = features.loc[common_index].sort_index()
        targets = targets.loc[common_index].sort_index()

        valid_mask = features.notna().all(axis=1) & targets.notna().all(axis=1)
        features = features.loc[valid_mask]
        targets = targets.loc[valid_mask]

        return features, targets

    def build_dataset_for_prediction(
        self, target_date, dataframe: pd.DataFrame | None = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Return (features, targets) for a live forecast of ``target_date``.

        Identical to :meth:`build_dataset` except the target-date row is kept
        even when its target (actual price) is missing or NaN: the validity
        filter is applied to the training rows only. The target row's feature
        vector is built from past price lags and ahead-published exogenous
        forecasts, so it exists before the actual clears. The engine trains on
        ``features.index < target_date`` and predicts from this feature row, so
        the missing target is never read (see ``BacktestEngine._slice_data``).
        """
        if dataframe is None:
            dataframe = load_dataset(self.experiment_config)

        features = self.generate_full_feature_matrix(dataframe)
        targets = pivot_to_daily(dataframe, self.experiment_config.target_column)

        features.index = pd.to_datetime(features.index)
        targets.index = pd.to_datetime(targets.index)
        target_ts = pd.to_datetime(target_date)

        # Align targets to the feature index; the target row may be absent from
        # targets (actual not yet published) and becomes NaN after reindex.
        targets = targets.reindex(features.index)

        feature_ok = features.notna().all(axis=1)
        target_ok = targets.notna().all(axis=1)
        is_target = features.index == target_ts
        valid_mask = feature_ok & (target_ok | is_target)

        features = features.loc[valid_mask].sort_index()
        targets = targets.loc[valid_mask].sort_index()

        return features, targets

    def latest_complete_target(self, dataframe: pd.DataFrame | None = None):
        """Return the most recent date whose feature row is fully available.

        This is the latest day a live forecast can be produced for: its inputs
        (price lags from past days, ahead-published exogenous forecasts) are all
        present. Used when no explicit target date is given, so the scheduled
        forecast always targets the freshest *complete* day rather than a
        partially-available leading-edge day (e.g. tomorrow, whose last UTC
        hours are not yet published).
        """
        if dataframe is None:
            dataframe = load_dataset(self.experiment_config)

        features = self.generate_full_feature_matrix(dataframe)
        features.index = pd.to_datetime(features.index)
        complete = features.notna().all(axis=1)
        if not complete.any():
            raise ValueError(
                "No complete feature row available; cannot pick a forecast target."
            )
        return features.index[complete].max()
