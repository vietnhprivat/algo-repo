"""Integration tests for price forecasting evaluation and metrics."""

import pytest
import numpy as np
import pandas as pd

from price_forecasting.evaluation.metrics import (
    calculate_mae,
    calculate_rmse,
    calculate_smape,
    calculate_rmae,
)
from price_forecasting.evaluation.summary import (
    build_weekly_naive,
    compute_metrics_summary,
    compute_metrics_per_hour,
)


class TestMetrics:
    """Test metric calculations with known values."""

    def test_mae_perfect_forecast(self):
        y = np.array([1.0, 2.0, 3.0])
        assert calculate_mae(y, y) == 0.0

    def test_mae_known_value(self):
        y_true = np.array([10.0, 20.0, 30.0])
        y_pred = np.array([12.0, 18.0, 33.0])
        # |2| + |2| + |3| = 7, mean = 7/3
        assert pytest.approx(calculate_mae(y_true, y_pred), abs=1e-6) == 7 / 3

    def test_rmse_perfect_forecast(self):
        y = np.array([1.0, 2.0, 3.0])
        assert calculate_rmse(y, y) == 0.0

    def test_rmse_known_value(self):
        y_true = np.array([10.0, 20.0])
        y_pred = np.array([13.0, 16.0])
        # (9 + 16) / 2 = 12.5, sqrt = 3.5355...
        assert pytest.approx(calculate_rmse(y_true, y_pred), abs=1e-4) == np.sqrt(12.5)

    def test_smape_perfect_forecast(self):
        y = np.array([10.0, 20.0, 30.0])
        assert calculate_smape(y, y) == 0.0

    def test_rmae_returns_nan_when_naive_is_perfect(self):
        y_true = np.array([1.0, 2.0, 3.0])
        y_pred = np.array([1.5, 2.5, 3.5])
        y_naive = np.array([1.0, 2.0, 3.0])  # naive == true -> denom = 0
        assert np.isnan(calculate_rmae(y_true, y_pred, y_naive))

    def test_rmae_known_value(self):
        y_true = np.array([10.0, 20.0, 30.0])
        y_pred = np.array([12.0, 18.0, 33.0])
        y_naive = np.array([8.0, 22.0, 28.0])
        # MAE(pred) = (2+2+3)/3 = 7/3, MAE(naive) = (2+2+2)/3 = 2 -> rMAE = 7/6
        expected = calculate_mae(y_true, y_pred) / calculate_mae(y_true, y_naive)
        assert pytest.approx(calculate_rmae(y_true, y_pred, y_naive), abs=1e-6) == expected


class TestEvaluation:

    N_PERIODS = 24

    def _make_sample_data(self):
        """Create aligned forecasts/actuals DataFrames."""
        dates = pd.date_range("2019-02-01", periods=14, freq="D")
        n = self.N_PERIODS
        columns = [f"h{i}" for i in range(n)]
        rng = np.random.default_rng(42)
        actuals = pd.DataFrame(
            rng.standard_normal((14, n)) * 20 + 50, index=dates, columns=columns
        )
        forecasts = actuals + rng.standard_normal((14, n)) * 5
        return forecasts, actuals

    def test_build_weekly_naive(self):
        _, actuals = self._make_sample_data()
        naive = build_weekly_naive(actuals)
        # First 7 rows should be NaN (no data from 7 days before)
        assert naive.iloc[:7].isna().all().all()
        # Row 7 should equal row 0
        pd.testing.assert_series_equal(
            naive.iloc[7], actuals.iloc[0], check_names=False
        )

    def test_compute_metrics_summary_keys(self):
        forecasts, actuals = self._make_sample_data()
        naive = build_weekly_naive(actuals)
        summary = compute_metrics_summary(forecasts, actuals, naive)
        assert "mae" in summary
        assert "rmse" in summary
        assert "smape" in summary
        assert "rmae" in summary

    def test_compute_metrics_summary_without_naive(self):
        forecasts, actuals = self._make_sample_data()
        summary = compute_metrics_summary(forecasts, actuals)
        assert "mae" in summary
        assert "rmae" not in summary

    def test_compute_metrics_per_hour_has_24_rows(self):
        forecasts, actuals = self._make_sample_data()
        naive = build_weekly_naive(actuals)
        per_hour = compute_metrics_per_hour(forecasts, actuals, naive)
        assert len(per_hour) == self.N_PERIODS
        assert "hour" in per_hour.columns
        assert "mae" in per_hour.columns

    def test_metrics_are_non_negative(self):
        forecasts, actuals = self._make_sample_data()
        summary = compute_metrics_summary(forecasts, actuals)
        assert summary["mae"] >= 0
        assert summary["rmse"] >= 0
        assert summary["smape"] >= 0
