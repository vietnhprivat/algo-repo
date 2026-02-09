"""Integration tests for BacktestEngine using StubModel (no real training)."""

import pytest
import numpy as np
import pandas as pd

from backtesting.engine import BacktestEngine
from backtesting.configs.experiment import ExperimentConfig

from tests.backtesting.conftest import (
    StubModel,
    make_test_config,
    make_synthetic_features_and_targets,
)


class TestBacktestEngineSliceData:
    def setup_method(self, tmp_path=None):
        self.config = ExperimentConfig(
            experiment_name="slice_test",
            results_dir="/tmp/slice_test_results",
            data_path="unused",
            target_column="price",
            test_start_date="2019-02-01",
            test_end_date="2019-02-03",
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
        assert tgt_train.shape[1] == 24
        assert feat_test.shape[0] == 1

    def test_slice_data_raises_for_missing_date(self):
        target_date = pd.Timestamp("2099-01-01")
        with pytest.raises(ValueError, match="not found in feature index"):
            self.engine._slice_data(self.features, self.targets, target_date, 7)

    def test_slice_data_raises_for_insufficient_data(self):
        target_date = pd.Timestamp("2019-01-03")  # Only 2 days before
        with pytest.raises(ValueError, match="Not enough training data"):
            self.engine._slice_data(self.features, self.targets, target_date, 30)


class TestBacktestEngineRun:
    def test_run_returns_forecasts_and_actuals(self, tmp_path):
        config = make_test_config(tmp_path, windows=[7])
        engine = BacktestEngine(config)
        features, targets = make_synthetic_features_and_targets()

        test_dates = pd.DatetimeIndex(
            [pd.Timestamp("2019-02-01"), pd.Timestamp("2019-02-02")]
        )
        factory = lambda: StubModel(prediction_value=42.0)

        forecasts, actuals = engine.run(factory, features, targets, test_dates)

        assert isinstance(forecasts, pd.DataFrame)
        assert isinstance(actuals, pd.DataFrame)
        assert forecasts.shape == (2, 24)
        assert actuals.shape == (2, 24)

    def test_forecasts_use_stub_prediction(self, tmp_path):
        config = make_test_config(tmp_path, windows=[7])
        engine = BacktestEngine(config)
        features, targets = make_synthetic_features_and_targets()
        test_dates = pd.DatetimeIndex([pd.Timestamp("2019-02-01")])

        factory = lambda: StubModel(prediction_value=99.0)
        forecasts, _ = engine.run(factory, features, targets, test_dates)

        # StubModel returns 99.0 but goes through scaler -> inverse_transform
        # so actual values won't be exactly 99.0, but the pipeline completes
        assert forecasts.shape == (1, 24)
        assert not forecasts.isna().any().any()

    def test_multiple_windows_produce_ensemble(self, tmp_path):
        config = make_test_config(tmp_path, windows=[7, 14])
        engine = BacktestEngine(config)
        features, targets = make_synthetic_features_and_targets()
        test_dates = pd.DatetimeIndex([pd.Timestamp("2019-02-15")])

        factory = lambda: StubModel(prediction_value=50.0)
        forecasts, actuals = engine.run(factory, features, targets, test_dates)

        assert forecasts.shape == (1, 24)
        assert actuals.shape == (1, 24)


class TestBacktestEngineRefit:
    def test_refit_interval_skips_training(self, tmp_path):
        """With refit_interval_days=7, the model should only be fitted once for
        consecutive days within that window."""
        config = make_test_config(
            tmp_path,
            windows=[14],
            test_start="2019-02-15",
            test_end="2019-02-18",
            refit_interval_days=7,
        )
        engine = BacktestEngine(config)
        features, targets = make_synthetic_features_and_targets()
        test_dates = pd.DatetimeIndex(
            pd.date_range("2019-02-15", "2019-02-18", freq="D")
        )

        models_created = []

        def counting_factory():
            model = StubModel(prediction_value=42.0)
            models_created.append(model)
            return model

        forecasts, _ = engine.run(counting_factory, features, targets, test_dates)
        assert forecasts.shape[0] == 4

        # With refit_interval_days=7 and 4 consecutive days,
        # only 1 model should be created (fitted on first day, reused for rest)
        fitted_models = [m for m in models_created if m.fit_called]
        assert len(fitted_models) == 1
