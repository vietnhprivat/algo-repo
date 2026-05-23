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


@dataclass
class DayAheadExogTransformer(FeatureTransformer):
    """Day-ahead exogenous forecast for D+1, one block of `n_periods` columns per variable.

    Output columns, in order:
        exog_{col_1}_p0..exog_{col_1}_p{N-1},
        exog_{col_2}_p0..,
        ...

    For TransformerModel consumption: a row of length `n_exog * N` that the
    model reshapes to `(n_exog, N)`.
    """

    exogenous_columns: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.exogenous_columns:
            raise ValueError("exogenous_columns must contain at least one entry")

    def transform(
        self,
        hourly_dataframe: pd.DataFrame,
        daily_prices: pd.DataFrame,
    ) -> pd.DataFrame:
        blocks: list[pd.DataFrame] = []
        for column in self.exogenous_columns:
            if column not in hourly_dataframe.columns:
                raise KeyError(f"Exogenous column {column!r} not found in input data")
            daily_col = pivot_to_daily(hourly_dataframe, column)
            n_periods = daily_col.shape[1]
            daily_col.columns = [f"exog_{column}_p{p}" for p in range(n_periods)]
            blocks.append(daily_col)
        return pd.concat(blocks, axis=1)


@dataclass
class PastPriceSequenceTransformer(FeatureTransformer):
    """Past `m` days of hourly prices, arranged oldest-day-first.

    Output columns, in order:
        seq_d{m}_p0..seq_d{m}_p{N-1},  # m days back, oldest
        seq_d{m-1}_p0..,
        ...
        seq_d1_p0..seq_d1_p{N-1}       # yesterday

    For TransformerModel consumption: a row of length `m * N` that the model
    reshapes to `(m, N)` with row 0 = oldest day.
    """

    sequence_length_days: int = 14

    def __post_init__(self) -> None:
        if self.sequence_length_days < 1:
            raise ValueError("sequence_length_days must be >= 1")

    def transform(
        self,
        hourly_dataframe: pd.DataFrame,
        daily_prices: pd.DataFrame,
    ) -> pd.DataFrame:
        n_periods = daily_prices.shape[1]
        blocks: list[pd.DataFrame] = []
        for k in range(self.sequence_length_days, 0, -1):
            shifted = daily_prices.shift(k)
            shifted.columns = [f"seq_d{k}_p{p}" for p in range(n_periods)]
            blocks.append(shifted)
        return pd.concat(blocks, axis=1)


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
