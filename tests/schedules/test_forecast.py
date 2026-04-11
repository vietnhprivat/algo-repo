"""Tests for the daily forecast Prefect flow and tasks."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from price_forecasting import ExperimentConfig
from price_forecasting.live_runner import LiveResult
from schedules.forecast import (
    daily_forecast_flow,
    load_config_task,
    predict_task,
    track_prediction_task,
)


def _make_config() -> ExperimentConfig:
    return ExperimentConfig(
        experiment_name="dk1_lear",
        results_dir="/tmp/test",
        area="DK1",
        model_type="lear",
        calibration_windows=[7],
        exogenous_curve_types=["TotalLoad"],
    )


def _make_live_result(n_periods: int = 24) -> LiveResult:
    prediction = pd.Series(
        np.arange(n_periods, dtype=float) + 30.0,
        index=[f"p{i}" for i in range(n_periods)],
        name="2026-04-11",
    )
    return LiveResult(
        prediction=prediction,
        data_start_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
        data_end_utc=datetime(2026, 4, 10, tzinfo=timezone.utc),
        training_duration_seconds=5.0,
        trained_models={},
    )


class TestLoadConfigTask:
    @patch("schedules.forecast.load_config")
    def test_returns_config(self, mock_load_config):
        config = _make_config()
        mock_load_config.return_value = config

        result = load_config_task.fn("dk1_lear")

        mock_load_config.assert_called_once_with("dk1_lear")
        assert result is config

    @patch("schedules.forecast.load_config")
    def test_config_name_forwarded(self, mock_load_config):
        mock_load_config.return_value = _make_config()

        load_config_task.fn("custom_config")

        mock_load_config.assert_called_once_with("custom_config")


class TestPredictTask:
    @patch("schedules.forecast.LiveRunner")
    def test_calls_runner_with_target_date(self, mock_runner_cls):
        config = _make_config()
        live_result = _make_live_result()
        mock_runner = MagicMock()
        mock_runner.run_live_with_metadata.return_value = live_result
        mock_runner_cls.return_value = mock_runner

        result = predict_task.fn(config, "2026-04-11")

        mock_runner_cls.assert_called_once_with(config)
        mock_runner.run_live_with_metadata.assert_called_once_with("2026-04-11")
        assert result is live_result

    @patch("schedules.forecast.LiveRunner")
    def test_returns_live_result(self, mock_runner_cls):
        config = _make_config()
        live_result = _make_live_result(n_periods=24)
        mock_runner = MagicMock()
        mock_runner.run_live_with_metadata.return_value = live_result
        mock_runner_cls.return_value = mock_runner

        result = predict_task.fn(config, "2026-04-11")

        assert len(result.prediction) == 24
        assert result.training_duration_seconds == 5.0


class TestTrackPredictionTask:
    @patch("schedules.forecast.track_prediction")
    def test_calls_track_prediction_and_returns_run_id(self, mock_track):
        config = _make_config()
        live_result = _make_live_result()
        mock_track.return_value = "fake-run-id"

        run_id = track_prediction_task.fn(config, "2026-04-11", live_result, "dk1_lear")

        mock_track.assert_called_once_with(
            config,
            "2026-04-11",
            live_result.prediction,
            training_duration_seconds=live_result.training_duration_seconds,
            data_start_utc=live_result.data_start_utc,
            data_end_utc=live_result.data_end_utc,
            trained_models=live_result.trained_models,
            config_name="dk1_lear",
        )
        assert run_id == "fake-run-id"


class TestDailyForecastFlow:
    @patch("schedules.forecast.track_prediction_task")
    @patch("schedules.forecast.predict_task")
    @patch("schedules.forecast.load_config_task")
    def test_flow_uses_provided_target_date(
        self, mock_load, mock_predict, mock_track
    ):
        config = _make_config()
        live_result = _make_live_result()
        mock_load.return_value = config
        mock_predict.return_value = live_result
        mock_track.return_value = "run-123"

        result = daily_forecast_flow.fn(config_name="dk1_lear", target_date="2026-04-11")

        mock_predict.assert_called_once_with(config, "2026-04-11")
        assert result["target_date"] == "2026-04-11"

    @patch("schedules.forecast.track_prediction_task")
    @patch("schedules.forecast.predict_task")
    @patch("schedules.forecast.load_config_task")
    def test_flow_defaults_to_tomorrow_when_no_date(
        self, mock_load, mock_predict, mock_track
    ):
        config = _make_config()
        live_result = _make_live_result()
        mock_load.return_value = config
        mock_predict.return_value = live_result
        mock_track.return_value = "run-456"

        result = daily_forecast_flow.fn(config_name="dk1_lear")

        _, predict_call_args, _ = mock_predict.mock_calls[0]
        target_date = predict_call_args[1]
        # Should be a valid date string in YYYY-MM-DD format
        datetime.strptime(target_date, "%Y-%m-%d")
        assert result["target_date"] == target_date

    @patch("schedules.forecast.track_prediction_task")
    @patch("schedules.forecast.predict_task")
    @patch("schedules.forecast.load_config_task")
    def test_flow_returns_expected_keys(self, mock_load, mock_predict, mock_track):
        config = _make_config()
        live_result = _make_live_result()
        mock_load.return_value = config
        mock_predict.return_value = live_result
        mock_track.return_value = "run-789"

        result = daily_forecast_flow.fn(config_name="dk1_lear", target_date="2026-04-11")

        assert result["config_name"] == "dk1_lear"
        assert result["area"] == "DK1"
        assert result["run_id"] == "run-789"
        assert result["n_periods"] == len(live_result.prediction)
        assert result["training_duration_seconds"] == live_result.training_duration_seconds

    @patch("schedules.forecast.track_prediction_task")
    @patch("schedules.forecast.predict_task")
    @patch("schedules.forecast.load_config_task")
    def test_flow_passes_config_name_to_track(self, mock_load, mock_predict, mock_track):
        config = _make_config()
        live_result = _make_live_result()
        mock_load.return_value = config
        mock_predict.return_value = live_result
        mock_track.return_value = "run-abc"

        daily_forecast_flow.fn(config_name="dk1_lear", target_date="2026-04-11")

        _, track_args, _ = mock_track.mock_calls[0]
        assert track_args[3] == "dk1_lear"
