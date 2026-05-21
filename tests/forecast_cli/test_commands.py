"""Tests for forecast_cli backtest and predict commands."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
from typer.testing import CliRunner

from forecast_cli.main import app
from price_forecasting import ExperimentConfig
from price_forecasting.live_runner import LiveResult

runner = CliRunner()


def _make_test_config() -> ExperimentConfig:
    return ExperimentConfig(
        experiment_name="test_run",
        results_dir="/tmp/test_results",
        area="DK1",
        model_type="lear",
        calibration_windows=[7],
        exogenous_curve_types=["TotalLoad"],
    )


def _make_backtest_outputs(n_periods: int = 24) -> dict[str, pd.DataFrame]:
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    columns = [f"h{i}" for i in range(n_periods)]
    rng = np.random.default_rng(42)
    forecasts = pd.DataFrame(
        rng.standard_normal((10, n_periods)) * 10 + 50, index=dates, columns=columns
    )
    actuals = pd.DataFrame(
        rng.standard_normal((10, n_periods)) * 10 + 50, index=dates, columns=columns
    )
    return {"forecasts": forecasts, "actuals": actuals}


def _make_prediction_series(n_periods: int = 24) -> pd.Series:
    return pd.Series(
        np.arange(n_periods, dtype=float) + 30.0,
        index=[f"p{i}" for i in range(n_periods)],
        name="2024-06-15",
    )


def _make_live_result(n_periods: int = 24, duration: float = 1.25) -> LiveResult:
    return LiveResult(
        prediction=_make_prediction_series(n_periods),
        data_start_utc=datetime(2024, 1, 1, tzinfo=timezone.utc),
        data_end_utc=datetime(2024, 6, 14, tzinfo=timezone.utc),
        training_duration_seconds=duration,
        trained_models={},
    )


class TestBacktestCommand:

    @patch("forecast_cli.main.BacktestRunner")
    @patch("forecast_cli.main.load_config")
    def test_backtest_runs_and_prints_metrics(self, mock_load, mock_runner_cls):
        config = _make_test_config()
        mock_load.return_value = config

        outputs = _make_backtest_outputs()
        mock_runner_instance = MagicMock()
        mock_runner_instance.execute.return_value = outputs
        mock_runner_cls.return_value = mock_runner_instance

        result = runner.invoke(app, ["backtest", "dk1_lear"])

        assert result.exit_code == 0
        assert "Running backtest: test_run" in result.output
        assert "DK1" in result.output
        assert "MAE:" in result.output
        assert "RMSE:" in result.output
        mock_runner_instance.execute.assert_called_once()

    @patch("forecast_cli.main.BacktestRunner")
    @patch("forecast_cli.main.track_backtest_run")
    @patch("forecast_cli.main.load_config")
    def test_backtest_with_track_calls_tracking(
        self, mock_load, mock_track, mock_runner_cls
    ):
        config = _make_test_config()
        mock_load.return_value = config

        outputs = _make_backtest_outputs()
        outputs["training_duration_seconds"] = 12.5
        mock_runner_instance = MagicMock()
        mock_runner_instance.execute.return_value = outputs
        mock_runner_cls.return_value = mock_runner_instance
        mock_track.return_value = "fake-uuid-1234"

        result = runner.invoke(app, ["backtest", "dk1_lear", "--track"])

        assert result.exit_code == 0
        assert "Tracked run fake-uuid-1234" in result.output
        mock_track.assert_called_once()
        _, kwargs = mock_track.call_args
        assert kwargs["training_duration_seconds"] == 12.5

    @patch("forecast_cli.main.load_config")
    def test_backtest_missing_config_exits(self, mock_load):
        mock_load.side_effect = SystemExit(1)
        result = runner.invoke(app, ["backtest", "nonexistent"])
        assert result.exit_code != 0


class TestPredictCommand:

    @patch("forecast_cli.main.LiveRunner")
    @patch("forecast_cli.main.load_config")
    def test_predict_prints_periods(self, mock_load, mock_runner_cls):
        config = _make_test_config()
        mock_load.return_value = config

        live_result = _make_live_result()
        mock_runner_instance = MagicMock()
        mock_runner_instance.run_live_with_metadata.return_value = live_result
        mock_runner_cls.return_value = mock_runner_instance

        result = runner.invoke(app, ["predict", "dk1_lear", "-d", "2024-06-15"])

        assert result.exit_code == 0
        assert "Prediction for DK1 on 2024-06-15" in result.output
        assert "Period" in result.output
        assert "Time" in result.output
        assert "Price" in result.output
        mock_runner_instance.run_live_with_metadata.assert_called_once_with(
            "2024-06-15"
        )

    @patch("forecast_cli.main.LiveRunner")
    @patch("forecast_cli.main.track_prediction")
    @patch("forecast_cli.main.load_config")
    def test_predict_with_track_calls_tracking(
        self, mock_load, mock_track, mock_runner_cls
    ):
        config = _make_test_config()
        mock_load.return_value = config

        live_result = _make_live_result(duration=2.5)
        mock_runner_instance = MagicMock()
        mock_runner_instance.run_live_with_metadata.return_value = live_result
        mock_runner_cls.return_value = mock_runner_instance
        mock_track.return_value = "fake-uuid-5678"

        result = runner.invoke(
            app, ["predict", "dk1_lear", "-d", "2024-06-15", "--track"]
        )

        assert result.exit_code == 0
        assert "Tracked prediction fake-uuid-5678" in result.output
        mock_track.assert_called_once()
        _, kwargs = mock_track.call_args
        assert kwargs["training_duration_seconds"] == 2.5
        assert kwargs["data_start_utc"] == live_result.data_start_utc
        assert kwargs["data_end_utc"] == live_result.data_end_utc

    def test_predict_missing_date_exits(self):
        result = runner.invoke(app, ["predict", "dk1_lear"])
        assert result.exit_code != 0
