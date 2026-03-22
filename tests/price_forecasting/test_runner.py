"""Integration tests for BacktestRunner and LiveRunner using StubModel."""

import pytest
import json
from pathlib import Path

import pandas as pd

from price_forecasting.backtesting.runner import BacktestRunner
from price_forecasting.live_runner import LiveRunner
from price_forecasting.configs.experiment import ExperimentConfig

from tests.price_forecasting.conftest import (
    StubModel,
    make_synthetic_features_and_targets,
)


class TestBacktestRunner:
    """Integration tests for BacktestRunner — patches data loading, uses StubModel."""

    def _make_config(self, tmp_path: Path) -> ExperimentConfig:
        return ExperimentConfig(
            experiment_name="integration_test",
            results_dir=str(tmp_path / "results"),
            area="DE",
            target_column="price",
            train_ratio=0.5,
            validation_ratio=0.0,
            test_ratio=0.5,
            calibration_windows=[7],
            refit_interval_days=1,
            model_type="LEAR",
            model_params={},
        )

    def _patch_runner(self, runner: BacktestRunner):
        """Patch internal methods to avoid real data loading and model creation."""
        features, targets = make_synthetic_features_and_targets()
        runner._load_and_preprocess_data = lambda dataframe=None: (features, targets)
        runner._get_model_factory = lambda: (lambda: StubModel(prediction_value=50.0))

    def test_execute_produces_output_files(self, tmp_path):
        config = self._make_config(tmp_path)
        runner = BacktestRunner(config)
        self._patch_runner(runner)

        outputs = runner.execute()

        assert "forecasts" in outputs
        assert "actuals" in outputs
        # With 59 days and 0.5 test ratio, test set should have ~29-30 days
        assert outputs["forecasts"].shape[0] > 0
        assert outputs["actuals"].shape[0] > 0

        results_dir = tmp_path / "results"
        assert (results_dir / "integration_test_forecasts.csv").exists()
        assert (results_dir / "integration_test_actuals.csv").exists()
        assert (results_dir / "integration_test_metrics.json").exists()
        assert (results_dir / "integration_test_metrics_per_hour.csv").exists()

    def test_metrics_json_has_expected_keys(self, tmp_path):
        config = self._make_config(tmp_path)
        runner = BacktestRunner(config)
        self._patch_runner(runner)
        runner.execute()

        metrics_path = tmp_path / "results" / "integration_test_metrics.json"
        metrics = json.loads(metrics_path.read_text())
        assert "mae" in metrics
        assert "rmse" in metrics
        assert "smape" in metrics

    def test_metrics_per_hour_has_24_rows(self, tmp_path):
        config = self._make_config(tmp_path)
        runner = BacktestRunner(config)
        self._patch_runner(runner)
        runner.execute()

        per_hour_path = tmp_path / "results" / "integration_test_metrics_per_hour.csv"
        df = pd.read_csv(per_hour_path)
        assert len(df) == 24

    def test_no_test_dates_raises(self, tmp_path):
        # Use train_ratio=1.0 so test set is empty
        config = ExperimentConfig(
            experiment_name="empty_test",
            results_dir=str(tmp_path / "results"),
            area="DE",
            train_ratio=1.0,
            validation_ratio=0.0,
            test_ratio=0.0,
            calibration_windows=[7],
        )
        runner = BacktestRunner(config)
        features, targets = make_synthetic_features_and_targets()
        runner._load_and_preprocess_data = lambda dataframe=None: (features, targets)
        runner._get_model_factory = lambda: (lambda: StubModel())

        with pytest.raises(ValueError, match="No test dates"):
            runner.execute()


class TestLiveRunner:
    """Integration tests for LiveRunner."""

    def test_run_live_returns_24_hour_series(self, tmp_path):
        config = ExperimentConfig(
            experiment_name="live_test",
            results_dir=str(tmp_path),
            area="DE",
            calibration_windows=[7],
        )
        runner = LiveRunner(config)

        features, targets = make_synthetic_features_and_targets()
        runner._load_and_preprocess_data = lambda dataframe=None: (features, targets)
        runner._get_model_factory = lambda: (lambda: StubModel(prediction_value=55.0))

        result = runner.run_live("2019-02-01")
        assert isinstance(result, pd.Series)
        assert len(result) == 24

    def test_run_live_raises_for_missing_date(self, tmp_path):
        config = ExperimentConfig(
            experiment_name="live_test",
            results_dir=str(tmp_path),
            area="DE",
            calibration_windows=[7],
        )
        runner = LiveRunner(config)
        features, targets = make_synthetic_features_and_targets()
        runner._load_and_preprocess_data = lambda dataframe=None: (features, targets)
        runner._get_model_factory = lambda: (lambda: StubModel())

        with pytest.raises(ValueError, match="Target date not found"):
            runner.run_live("2099-12-31")
