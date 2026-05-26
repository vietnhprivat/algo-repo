"""Integration tests for BacktestEngine using StubModel (no real training)."""

import pytest
import pandas as pd

from price_forecasting.backtesting.engine import BacktestEngine
from price_forecasting.configs.experiment import ExperimentConfig

from tests.price_forecasting.conftest import (
    StubModel,
    make_test_config,
    make_synthetic_features_and_targets,
)


class TestBacktestEngineSliceData:
    def setup_method(self, tmp_path=None):
        self.config = ExperimentConfig(
            experiment_name="slice_test",
            results_dir="/tmp/slice_test_results",
            area="DE",
            target_column="price",
            calibration_windows=[7],
            refit_interval_days=1,
        )
        self.engine = BacktestEngine(self.config)
        self.features, self.targets = make_synthetic_features_and_targets()

    def test_slice_data_returns_correct_shapes(self):
        target_date = pd.Timestamp("2019-02-01")
        window_size = 7
        feat_train, tgt_train, feat_test = self.engine._slice_data(
            self.features, self.targets, target_date, window_size
        )
        assert feat_train.shape[0] == window_size
        assert tgt_train.shape[0] == window_size
        assert tgt_train.shape[1] == self.targets.shape[1]
        assert feat_test.shape[0] == 1

    def test_slice_data_raises_for_missing_date(self):
        target_date = pd.Timestamp("2099-01-01")
        with pytest.raises(ValueError, match="not found in feature index"):
            self.engine._slice_data(self.features, self.targets, target_date, 7)

    def test_slice_data_raises_for_insufficient_data(self):
        target_date = pd.Timestamp("2019-01-03")  # Only 2 days before
        with pytest.raises(ValueError, match="Not enough training data"):
            self.engine._slice_data(self.features, self.targets, target_date, 30)

    def test_slice_data_skips_calendar_gaps(self):
        """When some calendar days are missing, slice returns the last window_size
        available rows regardless of the calendar span they cover."""
        # Construct a feature frame with a 5-day gap in the middle:
        # 2024-01-01 .. 2024-01-10 (10 days), 2024-01-16 .. 2024-01-25 (10 days),
        # 2024-01-26 = target. Total available pre-target rows: 20.
        dates = pd.date_range("2024-01-01", "2024-01-10", freq="D").union(
            pd.date_range("2024-01-16", "2024-01-26", freq="D")
        )
        features = pd.DataFrame(
            {"f1": range(len(dates))}, index=dates
        )
        targets = pd.DataFrame(
            {"t1": range(len(dates))}, index=dates
        )
        target_date = pd.Timestamp("2024-01-26")
        engine = BacktestEngine(self.config)

        # window_size = 15: 15 most recent available rows before 2024-01-26
        feat_train, tgt_train, feat_test = engine._slice_data(
            features, targets, target_date, window_size=15
        )
        assert feat_train.shape[0] == 15
        assert tgt_train.shape[0] == 15
        assert feat_test.shape[0] == 1
        # The 15 rows should be the 15 most recent — i.e. all 10 rows from the
        # second contiguous block (2024-01-16..2024-01-25) plus the last 5 rows
        # of the first block (2024-01-06..2024-01-10). Verify by checking the
        # first row of the slice corresponds to 2024-01-06's `f1` value.
        # 2024-01-06 is index 5 in the original dates (0..9 = first 10 days).
        assert feat_train[0, 0] == 5  # f1 value at 2024-01-06


class TestBacktestEngineRun:
    def test_run_returns_forecasts_and_actuals(self, tmp_path):
        config = make_test_config(tmp_path, windows=[7])
        engine = BacktestEngine(config)
        features, targets = make_synthetic_features_and_targets()

        test_dates = pd.DatetimeIndex(
            [pd.Timestamp("2019-02-01"), pd.Timestamp("2019-02-02")]
        )

        def factory():
            return StubModel(prediction_value=42.0)

        forecasts, actuals = engine.run(factory, features, targets, test_dates)

        assert isinstance(forecasts, pd.DataFrame)
        assert isinstance(actuals, pd.DataFrame)
        n_periods = targets.shape[1]
        assert forecasts.shape == (2, n_periods)
        assert actuals.shape == (2, n_periods)

    def test_forecasts_use_stub_prediction(self, tmp_path):
        config = make_test_config(tmp_path, windows=[7])
        engine = BacktestEngine(config)
        features, targets = make_synthetic_features_and_targets()
        test_dates = pd.DatetimeIndex([pd.Timestamp("2019-02-01")])

        def factory():
            return StubModel(prediction_value=99.0)

        forecasts, _ = engine.run(factory, features, targets, test_dates)

        # StubModel returns 99.0 but goes through scaler -> inverse_transform
        # so actual values won't be exactly 99.0, but the pipeline completes
        assert forecasts.shape == (1, targets.shape[1])
        assert not forecasts.isna().any().any()

    def test_multiple_windows_produce_ensemble(self, tmp_path):
        config = make_test_config(tmp_path, windows=[7, 14])
        engine = BacktestEngine(config)
        features, targets = make_synthetic_features_and_targets()
        test_dates = pd.DatetimeIndex([pd.Timestamp("2019-02-15")])

        def factory():
            return StubModel(prediction_value=50.0)

        forecasts, actuals = engine.run(factory, features, targets, test_dates)

        n_periods = targets.shape[1]
        assert forecasts.shape == (1, n_periods)
        assert actuals.shape == (1, n_periods)


class TestBacktestEngineRefit:
    def test_refit_interval_skips_training(self, tmp_path):
        """With refit_interval_days=7, the model should only be fitted once for
        consecutive days within that window."""
        config = make_test_config(
            tmp_path,
            windows=[14],
            refit_interval_days=7,
        )
        engine = BacktestEngine(config)
        features, targets = make_synthetic_features_and_targets()
        test_dates = pd.DatetimeIndex(
            pd.date_range("2019-02-15", "2019-02-18", freq="D")
        )

        models_created = []

        def factory():
            model = StubModel(prediction_value=42.0)
            models_created.append(model)
            return model

        forecasts, _ = engine.run(factory, features, targets, test_dates)
        assert forecasts.shape[0] == 4

        # With refit_interval_days=7 and 4 consecutive days,
        # only 1 model should be created (fitted on first day, reused for rest)
        fitted_models = [m for m in models_created if m.fit_called]
        assert len(fitted_models) == 1
