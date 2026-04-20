"""Tests for the drift detection Prefect flow."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import numpy as np

from schedules.drift import (
    CURRENT_DAYS,
    MIN_SAMPLE_SIZE,
    REFERENCE_DAYS,
    _compute_drift,
    _compute_windows,
    detect_drift_for_area_task,
    drift_detection_flow,
)

NOW = datetime(2026, 4, 20, 19, 0, 0, tzinfo=timezone.utc)


def _price_rows(prices: list[float], start: datetime) -> list[dict]:
    return [
        {"timestamp_utc": start + timedelta(hours=i), "price": p}
        for i, p in enumerate(prices)
    ]


class TestComputeWindows:
    def test_current_window_is_seven_days_ending_today(self):
        windows = _compute_windows(NOW)
        today = datetime(2026, 4, 20, tzinfo=timezone.utc)
        assert windows.current_end == today
        assert windows.current_start == today - timedelta(days=CURRENT_DAYS)

    def test_reference_window_is_ninety_days_before_current(self):
        windows = _compute_windows(NOW)
        assert windows.reference_end == windows.current_start
        assert (
            windows.reference_start
            == windows.current_start - timedelta(days=REFERENCE_DAYS)
        )

    def test_windows_do_not_overlap(self):
        windows = _compute_windows(NOW)
        assert windows.reference_end <= windows.current_start


class TestComputeDrift:
    def test_no_drift_when_distributions_identical(self):
        rng = np.random.default_rng(42)
        samples = rng.normal(50, 10, 500).tolist()
        _, _, stat_test, detected = _compute_drift(samples, samples)
        assert detected is False
        assert stat_test  # some non-empty label

    def test_drift_detected_when_distributions_shifted(self):
        rng = np.random.default_rng(42)
        reference = rng.normal(50, 10, 500).tolist()
        current = rng.normal(80, 10, 500).tolist()
        _, _, _, detected = _compute_drift(reference, current)
        assert detected is True


class TestDetectDriftForAreaTask:
    @patch("schedules.drift.insert_drift_report")
    @patch("schedules.drift.get_actual_prices_for_period")
    @patch("schedules.drift.create_client")
    def test_skips_when_reference_is_too_small(
        self, mock_create_client, mock_get_prices, mock_insert
    ):
        mock_create_client.return_value = MagicMock()
        small = _price_rows([50.0] * 5, NOW - timedelta(days=90))
        full = _price_rows([50.0] * 168, NOW - timedelta(days=7))
        mock_get_prices.side_effect = [small, full]

        result = detect_drift_for_area_task.fn("DK1")

        assert result["status"] == "skipped_insufficient_samples"
        assert result["reference_n"] == 5
        mock_insert.assert_not_called()

    @patch("schedules.drift.insert_drift_report")
    @patch("schedules.drift.get_actual_prices_for_period")
    @patch("schedules.drift.create_client")
    def test_skips_when_current_is_too_small(
        self, mock_create_client, mock_get_prices, mock_insert
    ):
        mock_create_client.return_value = MagicMock()
        full = _price_rows([50.0] * (REFERENCE_DAYS * 24), NOW - timedelta(days=90))
        small = _price_rows([50.0] * (MIN_SAMPLE_SIZE - 1), NOW - timedelta(days=7))
        mock_get_prices.side_effect = [full, small]

        result = detect_drift_for_area_task.fn("DK1")

        assert result["status"] == "skipped_insufficient_samples"
        mock_insert.assert_not_called()

    @patch("schedules.drift.insert_drift_report")
    @patch("schedules.drift.get_actual_prices_for_period")
    @patch("schedules.drift.create_client")
    def test_inserts_report_and_returns_result(
        self, mock_create_client, mock_get_prices, mock_insert
    ):
        mock_create_client.return_value = MagicMock()
        rng = np.random.default_rng(7)
        reference = rng.normal(50, 10, 500).tolist()
        current = rng.normal(50, 10, 168).tolist()
        mock_get_prices.side_effect = [
            _price_rows(reference, NOW - timedelta(days=90)),
            _price_rows(current, NOW - timedelta(days=7)),
        ]

        result = detect_drift_for_area_task.fn("DK1")

        mock_insert.assert_called_once()
        kwargs = mock_insert.call_args.kwargs
        assert kwargs["area"] == "DK1"
        assert kwargs["curve_name"] == "ENTSOE DK1 EnergyPrice"
        assert kwargs["reference_n"] == len(reference)
        assert kwargs["current_n"] == len(current)
        assert kwargs["drift_threshold"] > 0
        assert kwargs["drift_detected"] is False
        assert result["status"] == "ok"

    @patch("schedules.drift.insert_drift_report")
    @patch("schedules.drift.get_actual_prices_for_period")
    @patch("schedules.drift.create_client")
    def test_flags_drift_and_logs_warning_when_distributions_shift(
        self, mock_create_client, mock_get_prices, mock_insert, caplog
    ):
        mock_create_client.return_value = MagicMock()
        rng = np.random.default_rng(7)
        reference = rng.normal(50, 10, 500).tolist()
        current = rng.normal(150, 10, 168).tolist()
        mock_get_prices.side_effect = [
            _price_rows(reference, NOW - timedelta(days=90)),
            _price_rows(current, NOW - timedelta(days=7)),
        ]

        with caplog.at_level("WARNING"):
            result = detect_drift_for_area_task.fn("DK1")

        mock_insert.assert_called_once()
        assert mock_insert.call_args.kwargs["drift_detected"] is True
        assert result["status"] == "detected"
        assert any("Drift detected" in msg for msg in caplog.messages)

    @patch("schedules.drift.insert_drift_report")
    @patch("schedules.drift.get_actual_prices_for_period")
    @patch("schedules.drift.create_client")
    def test_closes_client_on_success(
        self, mock_create_client, mock_get_prices, mock_insert
    ):
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        reference = [50.0 + i * 0.01 for i in range(500)]
        current = [50.0 + i * 0.01 for i in range(168)]
        mock_get_prices.side_effect = [
            _price_rows(reference, NOW - timedelta(days=90)),
            _price_rows(current, NOW - timedelta(days=7)),
        ]

        detect_drift_for_area_task.fn("DK1")

        mock_client.close.assert_called_once()


class TestDriftDetectionFlow:
    @patch("schedules.drift.detect_drift_for_area_task")
    def test_flow_delegates_to_task(self, mock_task):
        mock_task.return_value = {"area": "DK1", "status": "ok"}

        result = drift_detection_flow.fn("DK1")

        mock_task.assert_called_once_with("DK1")
        assert result == {"area": "DK1", "status": "ok"}
