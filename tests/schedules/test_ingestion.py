"""Tests for the ENTSOE ingestion Prefect flow and tasks."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from data_cli.entsoe.services import BackfillResult
from schedules.ingestion import (
    entsoe_backfill_flow,
    ingest_energy_prices_task,
    ingest_generation_forecast_task,
    ingest_total_load_task,
    ingest_wind_solar_task,
)


def _make_result(data_type: str, rows: int = 24) -> BackfillResult:
    return BackfillResult(data_type=data_type, area="DK1", sets_fetched=1, rows_fetched=rows)


class TestIngestEnergyPricesTask:
    @patch("schedules.ingestion.backfill_energy_prices")
    @patch("schedules.ingestion.get_area_from_tag")
    def test_calls_backfill_with_resolved_area(self, mock_get_area, mock_backfill):
        area = MagicMock()
        mock_get_area.return_value = area
        expected = _make_result("energy_prices")
        mock_backfill.return_value = expected

        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 2, tzinfo=timezone.utc)
        result = ingest_energy_prices_task.fn("DK1", start, end)

        mock_get_area.assert_called_once_with("DK1")
        mock_backfill.assert_called_once_with(area, start, end)
        assert result is expected

    @patch("schedules.ingestion.backfill_energy_prices")
    @patch("schedules.ingestion.get_area_from_tag")
    def test_returns_backfill_result(self, mock_get_area, mock_backfill):
        mock_get_area.return_value = MagicMock()
        result_obj = _make_result("energy_prices", rows=48)
        mock_backfill.return_value = result_obj

        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 2, tzinfo=timezone.utc)
        result = ingest_energy_prices_task.fn("DK1", start, end)

        assert result.data_type == "energy_prices"
        assert result.rows_fetched == 48


class TestIngestTotalLoadTask:
    @patch("schedules.ingestion.backfill_total_load")
    @patch("schedules.ingestion.get_area_from_tag")
    def test_calls_backfill_with_resolved_area(self, mock_get_area, mock_backfill):
        area = MagicMock()
        mock_get_area.return_value = area
        expected = _make_result("total_load")
        mock_backfill.return_value = expected

        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 2, tzinfo=timezone.utc)
        result = ingest_total_load_task.fn("DK1", start, end)

        mock_get_area.assert_called_once_with("DK1")
        mock_backfill.assert_called_once_with(area, start, end)
        assert result is expected


class TestIngestGenerationForecastTask:
    @patch("schedules.ingestion.backfill_generation_forecast")
    @patch("schedules.ingestion.get_area_from_tag")
    def test_calls_backfill_with_resolved_area(self, mock_get_area, mock_backfill):
        area = MagicMock()
        mock_get_area.return_value = area
        expected = _make_result("generation_forecast")
        mock_backfill.return_value = expected

        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 2, tzinfo=timezone.utc)
        result = ingest_generation_forecast_task.fn("DK1", start, end)

        mock_get_area.assert_called_once_with("DK1")
        mock_backfill.assert_called_once_with(area, start, end)
        assert result is expected


class TestIngestWindSolarTask:
    @patch("schedules.ingestion.backfill_wind_solar")
    @patch("schedules.ingestion.get_area_from_tag")
    def test_calls_backfill_with_resolved_area(self, mock_get_area, mock_backfill):
        area = MagicMock()
        mock_get_area.return_value = area
        expected = _make_result("wind_solar")
        mock_backfill.return_value = expected

        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end = datetime(2026, 1, 2, tzinfo=timezone.utc)
        result = ingest_wind_solar_task.fn("DK1", start, end)

        mock_get_area.assert_called_once_with("DK1")
        mock_backfill.assert_called_once_with(area, start, end)
        assert result is expected


class TestEntsoeBackfillFlow:
    @patch("schedules.ingestion.ingest_wind_solar_task")
    @patch("schedules.ingestion.ingest_generation_forecast_task")
    @patch("schedules.ingestion.ingest_total_load_task")
    @patch("schedules.ingestion.ingest_energy_prices_task")
    def test_flow_calls_all_four_tasks(
        self,
        mock_prices,
        mock_load,
        mock_gen,
        mock_wind,
    ):
        mock_prices.return_value = _make_result("energy_prices")
        mock_load.return_value = _make_result("total_load")
        mock_gen.return_value = _make_result("generation_forecast")
        mock_wind.return_value = _make_result("wind_solar")

        result = entsoe_backfill_flow.fn(area="DK1")

        mock_prices.assert_called_once()
        mock_load.assert_called_once()
        mock_gen.assert_called_once()
        mock_wind.assert_called_once()
        assert result["area"] == "DK1"

    @patch("schedules.ingestion.ingest_wind_solar_task")
    @patch("schedules.ingestion.ingest_generation_forecast_task")
    @patch("schedules.ingestion.ingest_total_load_task")
    @patch("schedules.ingestion.ingest_energy_prices_task")
    def test_flow_returns_time_window_and_results(
        self,
        mock_prices,
        mock_load,
        mock_gen,
        mock_wind,
    ):
        r_prices = _make_result("energy_prices")
        r_load = _make_result("total_load")
        r_gen = _make_result("generation_forecast")
        r_wind = _make_result("wind_solar")
        mock_prices.return_value = r_prices
        mock_load.return_value = r_load
        mock_gen.return_value = r_gen
        mock_wind.return_value = r_wind

        result = entsoe_backfill_flow.fn(area="DK1")

        assert "time_window" in result
        assert "start" in result["time_window"]
        assert "end" in result["time_window"]
        assert result["results"] == [r_prices, r_load, r_gen, r_wind]

    @patch("schedules.ingestion.ingest_wind_solar_task")
    @patch("schedules.ingestion.ingest_generation_forecast_task")
    @patch("schedules.ingestion.ingest_total_load_task")
    @patch("schedules.ingestion.ingest_energy_prices_task")
    def test_flow_passes_area_to_all_tasks(
        self,
        mock_prices,
        mock_load,
        mock_gen,
        mock_wind,
    ):
        for mock in [mock_prices, mock_load, mock_gen, mock_wind]:
            mock.return_value = _make_result("any")

        entsoe_backfill_flow.fn(area="NL")

        for mock in [mock_prices, mock_load, mock_gen, mock_wind]:
            args, _ = mock.call_args
            assert args[0] == "NL"

    @patch("schedules.ingestion.ingest_wind_solar_task")
    @patch("schedules.ingestion.ingest_generation_forecast_task")
    @patch("schedules.ingestion.ingest_total_load_task")
    @patch("schedules.ingestion.ingest_energy_prices_task")
    def test_flow_default_area_is_dk1(
        self,
        mock_prices,
        mock_load,
        mock_gen,
        mock_wind,
    ):
        for mock in [mock_prices, mock_load, mock_gen, mock_wind]:
            mock.return_value = _make_result("any")

        result = entsoe_backfill_flow.fn()

        assert result["area"] == "DK1"
