"""Tests for feature transformers and the refactored DataPreprocessor pipeline."""

import numpy as np
import pandas as pd
import pytest

from price_forecasting.data.preprocessor import pivot_to_daily
from price_forecasting.data.transformers import (
    CalendarDummyTransformer,
    CyclicalTimeTransformer,
    DayAheadExogTransformer,
    ExogenousLagTransformer,
    MeanWeeklyForecastTransformer,
    PastPriceSequenceTransformer,
    PriceLagTransformer,
    default_transformers_for_model,
)

from tests.price_forecasting.conftest import make_hourly_dataframe


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

N_PERIODS = 24


def _build_daily_prices(hourly_df: pd.DataFrame) -> pd.DataFrame:
    return pivot_to_daily(hourly_df, "price")


# ---------------------------------------------------------------------------
# PriceLagTransformer
# ---------------------------------------------------------------------------


class TestPriceLagTransformer:
    def test_default_lags_produce_correct_column_count(self):
        hourly = make_hourly_dataframe()
        daily = _build_daily_prices(hourly)
        t = PriceLagTransformer()

        result = t.transform(hourly, daily)
        assert result.shape[1] == 4 * N_PERIODS

    def test_custom_lags(self):
        hourly = make_hourly_dataframe()
        daily = _build_daily_prices(hourly)
        t = PriceLagTransformer(lags=[1, 14])

        result = t.transform(hourly, daily)
        assert result.shape[1] == 2 * N_PERIODS

    def test_column_names_follow_convention(self):
        hourly = make_hourly_dataframe()
        daily = _build_daily_prices(hourly)
        t = PriceLagTransformer(lags=[1])

        result = t.transform(hourly, daily)
        expected = [f"p_lag1_price_p{p}" for p in range(N_PERIODS)]
        assert result.columns.tolist() == expected

    def test_first_lag_rows_are_nan(self):
        hourly = make_hourly_dataframe()
        daily = _build_daily_prices(hourly)
        t = PriceLagTransformer()

        result = t.transform(hourly, daily)
        # First 7 rows should have NaN in lag-7 columns
        lag7_cols = [c for c in result.columns if c.startswith("p_lag7_")]
        assert result[lag7_cols].iloc[:7].isna().all().all()
        # Row 7 (index 7) should have values
        assert result[lag7_cols].iloc[7].notna().all()


# ---------------------------------------------------------------------------
# ExogenousLagTransformer
# ---------------------------------------------------------------------------


class TestExogenousLagTransformer:
    def test_single_exogenous_column_count(self):
        hourly = make_hourly_dataframe(exogenous_columns=["TotalLoad"])
        daily = _build_daily_prices(hourly)
        t = ExogenousLagTransformer(exogenous_columns=["TotalLoad"])

        result = t.transform(hourly, daily)
        assert result.shape[1] == 3 * N_PERIODS

    def test_multiple_exogenous_columns(self):
        hourly = make_hourly_dataframe(exogenous_columns=["TotalLoad", "Wind"])
        daily = _build_daily_prices(hourly)
        t = ExogenousLagTransformer(exogenous_columns=["TotalLoad", "Wind"])

        result = t.transform(hourly, daily)
        assert result.shape[1] == 2 * 3 * N_PERIODS

    def test_empty_exogenous_returns_empty(self):
        hourly = make_hourly_dataframe()
        daily = _build_daily_prices(hourly)
        t = ExogenousLagTransformer(exogenous_columns=[])

        result = t.transform(hourly, daily)
        assert result.empty

    def test_missing_column_is_skipped(self):
        hourly = make_hourly_dataframe(exogenous_columns=["TotalLoad"])
        daily = _build_daily_prices(hourly)
        t = ExogenousLagTransformer(
            exogenous_columns=["TotalLoad", "NonExistent"]
        )

        result = t.transform(hourly, daily)
        # Only TotalLoad contributes
        assert result.shape[1] == 3 * N_PERIODS

    def test_column_naming_matches_convention(self):
        hourly = make_hourly_dataframe(exogenous_columns=["TotalLoad"])
        daily = _build_daily_prices(hourly)
        t = ExogenousLagTransformer(exogenous_columns=["TotalLoad"])

        result = t.transform(hourly, daily)
        # d0 columns come first, then d1, then d7
        assert result.columns[0] == "TotalLoad_d0_TotalLoad_p0"
        assert result.columns[N_PERIODS] == "TotalLoad_d1_TotalLoad_p0"
        assert result.columns[2 * N_PERIODS] == "TotalLoad_d7_TotalLoad_p0"


# ---------------------------------------------------------------------------
# CalendarDummyTransformer
# ---------------------------------------------------------------------------


class TestCalendarDummyTransformer:
    def test_produces_7_columns(self):
        hourly = make_hourly_dataframe()
        daily = _build_daily_prices(hourly)
        t = CalendarDummyTransformer()

        result = t.transform(hourly, daily)
        assert result.shape[1] == 7

    def test_column_names(self):
        hourly = make_hourly_dataframe()
        daily = _build_daily_prices(hourly)
        t = CalendarDummyTransformer()

        result = t.transform(hourly, daily)
        expected = [f"day_{i}" for i in range(7)]
        assert sorted(result.columns.tolist()) == expected

    def test_values_are_binary(self):
        hourly = make_hourly_dataframe()
        daily = _build_daily_prices(hourly)
        t = CalendarDummyTransformer()

        result = t.transform(hourly, daily)
        unique_values = set(result.values.flatten())
        assert unique_values <= {True, False} or unique_values <= {0, 1}

    def test_exactly_one_hot_per_row(self):
        hourly = make_hourly_dataframe()
        daily = _build_daily_prices(hourly)
        t = CalendarDummyTransformer()

        result = t.transform(hourly, daily)
        assert (result.sum(axis=1) == 1).all()


# ---------------------------------------------------------------------------
# CyclicalTimeTransformer
# ---------------------------------------------------------------------------


class TestCyclicalTimeTransformer:
    def test_values_in_range(self):
        hourly = make_hourly_dataframe()
        daily = _build_daily_prices(hourly)
        t = CyclicalTimeTransformer()

        result = t.transform(hourly, daily)
        assert (result >= -1.0).all().all()
        assert (result <= 1.0).all().all()

    def test_january_1_and_december_31_are_close(self):
        hourly = make_hourly_dataframe(
            start_date="2019-01-01", end_date="2020-01-02"
        )
        daily = _build_daily_prices(hourly)
        t = CyclicalTimeTransformer()

        result = t.transform(hourly, daily)
        jan1 = result.iloc[0].values
        dec31 = result.iloc[-1].values
        distance = np.linalg.norm(jan1 - dec31)
        # Adjacent days on the cycle should be very close
        assert distance < 0.05

    def test_july_is_opposite_january(self):
        hourly = make_hourly_dataframe(
            start_date="2019-01-01", end_date="2020-01-01"
        )
        daily = _build_daily_prices(hourly)
        t = CyclicalTimeTransformer()

        result = t.transform(hourly, daily)
        jan1 = result.iloc[0].values  # day 1
        jul1 = result.iloc[181].values  # ~day 182
        distance = np.linalg.norm(jan1 - jul1)
        # Opposite sides of the cycle
        assert distance > 1.5

    def test_week_of_year_disabled_by_default(self):
        hourly = make_hourly_dataframe()
        daily = _build_daily_prices(hourly)
        t = CyclicalTimeTransformer()

        result = t.transform(hourly, daily)
        assert "woy_sin" not in result.columns


# ---------------------------------------------------------------------------
# MeanWeeklyForecastTransformer
# ---------------------------------------------------------------------------


class TestMeanWeeklyForecastTransformer:
    def test_single_column_produces_1_feature(self):
        hourly = make_hourly_dataframe(exogenous_columns=["TotalLoad"])
        daily = _build_daily_prices(hourly)
        t = MeanWeeklyForecastTransformer(exogenous_columns=["TotalLoad"])

        result = t.transform(hourly, daily)
        assert result.shape[1] == 1
        assert result.columns[0] == "TotalLoad_week_mean"

    def test_multiple_columns(self):
        hourly = make_hourly_dataframe(exogenous_columns=["TotalLoad", "Wind"])
        daily = _build_daily_prices(hourly)
        t = MeanWeeklyForecastTransformer(
            exogenous_columns=["TotalLoad", "Wind"]
        )

        result = t.transform(hourly, daily)
        assert result.shape[1] == 2

    def test_empty_columns_returns_empty(self):
        hourly = make_hourly_dataframe()
        daily = _build_daily_prices(hourly)
        t = MeanWeeklyForecastTransformer(exogenous_columns=[])

        result = t.transform(hourly, daily)
        assert result.empty

    def test_no_nan_in_output(self):
        hourly = make_hourly_dataframe(exogenous_columns=["TotalLoad"])
        daily = _build_daily_prices(hourly)
        t = MeanWeeklyForecastTransformer(exogenous_columns=["TotalLoad"])

        result = t.transform(hourly, daily)
        # min_periods=1 means no NaN even for the first row
        assert result.notna().all().all()


# ---------------------------------------------------------------------------
# default_transformers_for_model
# ---------------------------------------------------------------------------


class TestDefaultTransformersForModel:
    def test_returns_three_transformers(self):
        transformers = default_transformers_for_model([])
        assert len(transformers) == 3
        assert isinstance(transformers[0], PriceLagTransformer)
        assert isinstance(transformers[1], ExogenousLagTransformer)
        assert isinstance(transformers[2], CalendarDummyTransformer)

    def test_exogenous_columns_passed_to_exogenous_transformer(self):
        transformers = default_transformers_for_model(["TotalLoad", "Wind"])
        exog = transformers[1]
        assert isinstance(exog, ExogenousLagTransformer)
        assert exog.exogenous_columns == ["TotalLoad", "Wind"]

    def test_empty_exogenous_columns(self):
        transformers = default_transformers_for_model([])
        exog = transformers[1]
        assert exog.exogenous_columns == []


# ---------------------------------------------------------------------------
# Regression: refactored preprocessor produces identical output to old code
# ---------------------------------------------------------------------------


class TestPreprocessorRegressionIdentity:
    """Verify that the transformer-based preprocessor produces the exact same
    feature matrix as the old monolithic DataPreprocessor.

    We inline the old logic here to compare against.
    """

    def _old_build_price_lags(self, daily_prices: pd.DataFrame) -> pd.DataFrame:
        lags = [1, 2, 3, 7]
        blocks = []
        for lag in lags:
            block = daily_prices.shift(lag).add_prefix(f"p_lag{lag}_")
            blocks.append(block)
        return pd.concat(blocks, axis=1)

    def _old_build_exogenous_features(
        self, hourly_df: pd.DataFrame, exogenous_columns: list[str]
    ) -> pd.DataFrame:
        if not exogenous_columns:
            return pd.DataFrame()
        all_blocks = []
        for column in exogenous_columns:
            if column not in hourly_df.columns:
                continue
            daily = pivot_to_daily(hourly_df, column)
            all_blocks.append(daily.copy().add_prefix(f"{column}_d0_"))
            all_blocks.append(daily.shift(1).add_prefix(f"{column}_d1_"))
            all_blocks.append(daily.shift(7).add_prefix(f"{column}_d7_"))
        return pd.concat(all_blocks, axis=1) if all_blocks else pd.DataFrame()

    def _old_add_calendar_dummies(self, index: pd.Index) -> pd.DataFrame:
        dates = pd.to_datetime(index)
        dummies = pd.get_dummies(dates.dayofweek, prefix="day")
        dummies.index = index
        return dummies

    def _old_generate_features(
        self,
        hourly_df: pd.DataFrame,
        target_column: str,
        exogenous_columns: list[str],
    ) -> pd.DataFrame:
        daily_prices = pivot_to_daily(hourly_df, target_column)
        price_lags = self._old_build_price_lags(daily_prices)
        exogenous = self._old_build_exogenous_features(hourly_df, exogenous_columns)
        calendar = self._old_add_calendar_dummies(daily_prices.index)
        parts = [price_lags, calendar] if exogenous.empty else [price_lags, exogenous, calendar]
        return pd.concat(parts, axis=1)

    def test_identical_no_exogenous(self):
        hourly = make_hourly_dataframe(seed=99)

        old = self._old_generate_features(hourly, "price", [])

        from price_forecasting.configs import ExperimentConfig
        from price_forecasting.data.preprocessor import DataPreprocessor

        config = ExperimentConfig(
            experiment_name="test",
            results_dir="/tmp/test",
            area="DE",
            exogenous_curve_types=[],
        )
        preprocessor = DataPreprocessor(config)
        new = preprocessor.generate_full_feature_matrix(hourly)

        pd.testing.assert_frame_equal(old, new)

    def test_identical_with_exogenous(self):
        hourly = make_hourly_dataframe(
            exogenous_columns=["TotalLoad"], seed=99
        )

        old = self._old_generate_features(hourly, "price", ["TotalLoad"])

        from price_forecasting.configs import ExperimentConfig
        from price_forecasting.data.preprocessor import DataPreprocessor

        config = ExperimentConfig(
            experiment_name="test",
            results_dir="/tmp/test",
            area="DE",
            exogenous_curve_types=["TotalLoad"],
        )
        preprocessor = DataPreprocessor(config)
        new = preprocessor.generate_full_feature_matrix(hourly)

        pd.testing.assert_frame_equal(old, new)

    def test_feature_column_count_formula(self):
        """Verify: no exogenous = 103, 1 exogenous = 175, 2 = 247."""
        hourly_0 = make_hourly_dataframe(exogenous_columns=[])
        hourly_1 = make_hourly_dataframe(exogenous_columns=["A"])
        hourly_2 = make_hourly_dataframe(exogenous_columns=["A", "B"])

        from price_forecasting.configs import ExperimentConfig
        from price_forecasting.data.preprocessor import DataPreprocessor

        for hourly, exog, expected in [
            (hourly_0, [], 103),
            (hourly_1, ["A"], 175),
            (hourly_2, ["A", "B"], 247),
        ]:
            config = ExperimentConfig(
                experiment_name="test",
                results_dir="/tmp/test",
                area="DE",
                exogenous_curve_types=exog,
            )
            preprocessor = DataPreprocessor(config)
            features = preprocessor.generate_full_feature_matrix(hourly)
            assert features.shape[1] == expected, (
                f"Expected {expected} columns for {len(exog)} exogenous, "
                f"got {features.shape[1]}"
            )


# ---------------------------------------------------------------------------
# PastPriceSequenceTransformer
# ---------------------------------------------------------------------------


class TestPastPriceSequenceTransformer:
    def test_outputs_m_days_of_n_periods_in_oldest_first_order(self):
        # 10 days of hourly price data (start inclusive, end exclusive via freq="h")
        hourly = make_hourly_dataframe(start_date="2019-01-01", end_date="2019-01-11")
        daily_prices = pivot_to_daily(hourly, "price")

        m = 3
        transformer = PastPriceSequenceTransformer(sequence_length_days=m)
        out = transformer.transform(hourly, daily_prices)

        # Column count = m * n_periods
        assert out.shape[1] == m * N_PERIODS

        # Column ordering: oldest day (d{m}) first, yesterday (d1) last.
        expected_cols = (
            [f"seq_d{k}_p{p}" for k in range(m, 0, -1) for p in range(N_PERIODS)]
        )
        assert list(out.columns) == expected_cols

        # The "d1" block on row i equals daily_prices on row i-1 (yesterday).
        # The "d{m}" block on row i equals daily_prices on row i-m.
        # Skip rows where shift produces NaN.
        first_valid = m
        d1_block = out.iloc[first_valid][[f"seq_d1_p{p}" for p in range(N_PERIODS)]].values
        np.testing.assert_array_equal(d1_block, daily_prices.iloc[first_valid - 1].values)

        dm_block = out.iloc[first_valid][[f"seq_d{m}_p{p}" for p in range(N_PERIODS)]].values
        np.testing.assert_array_equal(dm_block, daily_prices.iloc[first_valid - m].values)

    def test_rejects_non_positive_sequence_length(self):
        with pytest.raises(ValueError):
            PastPriceSequenceTransformer(sequence_length_days=0)


# ---------------------------------------------------------------------------
# DayAheadExogTransformer
# ---------------------------------------------------------------------------


class TestDayAheadExogTransformer:
    def test_outputs_one_block_per_exog_column(self):
        hourly = make_hourly_dataframe(
            start_date="2019-01-01",
            end_date="2019-01-06",
            exogenous_columns=["load_forecast", "gen_forecast"],
        )
        daily_prices = pivot_to_daily(hourly, "price")

        transformer = DayAheadExogTransformer(
            exogenous_columns=["load_forecast", "gen_forecast"]
        )
        out = transformer.transform(hourly, daily_prices)

        assert out.shape[1] == 2 * N_PERIODS
        expected_cols = (
            [f"exog_load_forecast_p{p}" for p in range(N_PERIODS)]
            + [f"exog_gen_forecast_p{p}" for p in range(N_PERIODS)]
        )
        assert list(out.columns) == expected_cols

        # The exog block equals the day-of pivot (lag 0) — the D+1 forecast
        # that is known at prediction time.
        load_daily = pivot_to_daily(hourly, "load_forecast")
        np.testing.assert_allclose(
            out[[f"exog_load_forecast_p{p}" for p in range(N_PERIODS)]].values,
            load_daily.values,
        )

    def test_rejects_empty_exogenous_columns(self):
        with pytest.raises(ValueError):
            DayAheadExogTransformer(exogenous_columns=[])
