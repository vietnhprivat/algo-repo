"""Composable feature transformers for the price forecasting pipeline.

Each transformer implements the FeatureTransformer interface and produces
a date-indexed pd.DataFrame of feature columns. The DataPreprocessor
concatenates outputs from a list of transformers to build the full
feature matrix.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from price_forecasting.data.preprocessor import pivot_to_daily


class FeatureTransformer(ABC):
    """Interface for feature engineering components.

    Each transformer receives raw hourly data and daily-pivoted prices,
    and returns a pd.DataFrame indexed by date (daily rows).
    """

    @abstractmethod
    def transform(
        self,
        hourly_dataframe: pd.DataFrame,
        daily_prices: pd.DataFrame,
    ) -> pd.DataFrame:
        """Produce feature columns.

        Parameters
        ----------
        hourly_dataframe:
            Original hourly data with DatetimeIndex. Contains the target
            column (e.g. "price") and any exogenous columns.
        daily_prices:
            Already-pivoted price matrix (date index, columns price_p0..pN).

        Returns
        -------
        pd.DataFrame with date index. May be empty if no features apply.
        """


# ---------------------------------------------------------------------------
# LEAR-paper feature transformers (reproduce the current default pipeline)
# ---------------------------------------------------------------------------


@dataclass
class PriceLagTransformer(FeatureTransformer):
    """LEAR-style price lag features.

    Shifts the daily-pivoted price matrix by each lag day.
    Default lags [1, 2, 3, 7] follow the LEAR paper.

    Produces len(lags) * n_periods columns.
    """

    lags: list[int] = field(default_factory=lambda: [1, 2, 3, 7])

    def transform(
        self,
        hourly_dataframe: pd.DataFrame,
        daily_prices: pd.DataFrame,
    ) -> pd.DataFrame:
        blocks = []
        for lag in self.lags:
            block = daily_prices.shift(lag).add_prefix(f"p_lag{lag}_")
            blocks.append(block)
        return pd.concat(blocks, axis=1)


@dataclass
class ExogenousLagTransformer(FeatureTransformer):
    """LEAR-style exogenous forecast features.

    For each exogenous column, pivots to daily wide format then shifts
    by each configured lag. Default lags (d0, d-1, d-7) follow the
    LEAR paper.

    Produces len(exogenous_columns) * len(lags) * n_periods columns.
    """

    exogenous_columns: list[str] = field(default_factory=list)
    lags: list[tuple[str, int]] = field(
        default_factory=lambda: [("d0", 0), ("d1", 1), ("d7", 7)]
    )

    def transform(
        self,
        hourly_dataframe: pd.DataFrame,
        daily_prices: pd.DataFrame,
    ) -> pd.DataFrame:
        if not self.exogenous_columns:
            return pd.DataFrame()

        all_blocks = []
        for column in self.exogenous_columns:
            if column not in hourly_dataframe.columns:
                continue
            daily = pivot_to_daily(hourly_dataframe, column)
            for label, shift in self.lags:
                block = daily.shift(shift).add_prefix(f"{column}_{label}_")
                all_blocks.append(block)
        return pd.concat(all_blocks, axis=1) if all_blocks else pd.DataFrame()


@dataclass
class CalendarDummyTransformer(FeatureTransformer):
    """One-hot day-of-week encoding. Produces 7 binary columns: day_0..day_6."""

    def transform(
        self,
        hourly_dataframe: pd.DataFrame,
        daily_prices: pd.DataFrame,
    ) -> pd.DataFrame:
        dates = pd.to_datetime(daily_prices.index)
        dummies = pd.get_dummies(dates.dayofweek, prefix="day")
        dummies.index = daily_prices.index
        return dummies


# ---------------------------------------------------------------------------
# New feature transformers
# ---------------------------------------------------------------------------


@dataclass
class CyclicalTimeTransformer(FeatureTransformer):
    """Sin/cos encoding of calendar cycles.

    Encodes day-of-year (annual seasonality) and optionally week-of-year.
    Captures periodicity in 2-4 columns instead of one-hot encoding.
    """
    def transform(
        self,
        hourly_dataframe: pd.DataFrame,
        daily_prices: pd.DataFrame,
    ) -> pd.DataFrame:
        dates = pd.to_datetime(daily_prices.index)
        parts: list[pd.DataFrame] = []

        day_of_year = dates.dayofyear.astype(float)
        parts.append(
            pd.DataFrame(
                {
                    "doy_sin": np.sin(2 * np.pi * day_of_year / 365.25),
                    "doy_cos": np.cos(2 * np.pi * day_of_year / 365.25),
                },
                index=daily_prices.index,
            )
        )

        if not parts:
            return pd.DataFrame(index=daily_prices.index)
        return pd.concat(parts, axis=1)


@dataclass
class MeanWeeklyForecastTransformer(FeatureTransformer):
    """Rolling weekly mean of exogenous forecasts.

    For each exogenous column, computes the daily mean across all periods,
    then takes a 7-day rolling average. Produces 1 column per curve —
    a compressed alternative to the full wide pivot + lag.

    Example: with ["TotalLoad", "WindOnshore"], produces 2 columns:
        TotalLoad_week_mean, WindOnshore_week_mean
    """

    exogenous_columns: list[str] = field(default_factory=list)
    window_days: int = 7

    def transform(
        self,
        hourly_dataframe: pd.DataFrame,
        daily_prices: pd.DataFrame,
    ) -> pd.DataFrame:
        if not self.exogenous_columns:
            return pd.DataFrame()

        parts: list[pd.DataFrame] = []
        for column in self.exogenous_columns:
            if column not in hourly_dataframe.columns:
                continue
            daily = pivot_to_daily(hourly_dataframe, column)
            # Mean across all periods of the day, then rolling weekly average
            daily_mean = daily.mean(axis=1)
            rolling_mean = daily_mean.rolling(
                window=self.window_days, min_periods=1
            ).mean()
            parts.append(
                pd.DataFrame(
                    {f"{column}_week_mean": rolling_mean},
                    index=daily.index,
                )
            )

        if not parts:
            return pd.DataFrame()
        return pd.concat(parts, axis=1)


class AggregatedLagTransformer(FeatureTransformer):
    """Compressed lag features using summary statistics per lag day.

    Instead of pivoting each lag day into n_periods columns, computes
    summary statistics per lag day. This compresses n_periods columns
    into a fixed number of columns per lag:

        {column}_lag{d}_mean
        {column}_lag{d}_min
        {column}_lag{d}_max
        {column}_lag{d}_std
        {column}_lag{d}_range   (max - min, peak-to-trough spread)

    Example: for price with lags [1, 2, 3, 7], produces 4 * 5 = 20 columns
    instead of 4 * 24 = 96 columns (hourly) or 4 * 96 = 384 columns (15-min).

    Use case: models with small calibration windows where the feature-to-sample
    ratio with full pivoted lags is too high. DNN models or experiments with
    many exogenous curves benefit most.

    Configuration:
        columns: list[str] — which columns to aggregate (e.g. ["price", "TotalLoad"])
        lags: list[int] — which day-lags to compute (e.g. [1, 2, 3, 7])
        stats: list[str] — which stats (default: ["mean", "min", "max", "std", "range"])

    NOT YET IMPLEMENTED.
    """

    def transform(
        self,
        hourly_dataframe: pd.DataFrame,
        daily_prices: pd.DataFrame,
    ) -> pd.DataFrame:
        raise NotImplementedError(
            "AggregatedLagTransformer is designed but not yet implemented."
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def default_transformers_for_model(
    exogenous_columns: list[str],
) -> list[FeatureTransformer]:
    """Build the standard transformer list for a model type.

    LEAR defaults reproduce the exact feature set from the research paper.
    """
    return [
        PriceLagTransformer(lags=[1, 2, 3, 7]),
        ExogenousLagTransformer(exogenous_columns=exogenous_columns),
        CalendarDummyTransformer(),
    ]
