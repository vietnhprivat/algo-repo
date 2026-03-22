"""Tests for the shared backfill service layer."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from data_cli.entsoe.services import (
    BackfillResult,
    backfill_energy_prices,
    backfill_generation_forecast,
    backfill_total_load,
    backfill_wind_solar,
)
from domain.areas import DK1


def _make_mock_observation(rows: int = 5):
    mock = MagicMock()
    mock.data_frame = MagicMock()
    mock.data_frame.height = rows
    return mock


def _make_mock_forecast(rows: int = 5):
    mock = MagicMock()
    mock.data_frame = MagicMock()
    mock.data_frame.height = rows
    return mock


START = datetime(2026, 3, 20, tzinfo=timezone.utc)
END = datetime(2026, 3, 22, tzinfo=timezone.utc)


class TestBackfillEnergyPrices:
    @patch("data_cli.entsoe.services.insert_observations_batch")
    @patch("data_cli.entsoe.services.create_client")
    @patch("data_cli.entsoe.services.create_entsoe_client")
    def test_happy_path(self, mock_entsoe_factory, mock_ch_factory, mock_insert):
        obs = [_make_mock_observation(48), _make_mock_observation(48)]
        mock_entsoe = MagicMock()
        mock_entsoe.fetch_energy_prices.return_value = obs
        mock_entsoe_factory.return_value.__enter__ = MagicMock(return_value=mock_entsoe)
        mock_entsoe_factory.return_value.__exit__ = MagicMock(return_value=False)

        mock_ch = MagicMock()
        mock_ch_factory.return_value = mock_ch

        result = backfill_energy_prices(DK1, START, END)

        assert isinstance(result, BackfillResult)
        assert result.data_type == "energy_prices"
        assert result.area == "DK1"
        assert result.sets_fetched == 2
        assert result.rows_fetched == 96
        mock_insert.assert_called_once_with(mock_ch, obs)

    @patch("data_cli.entsoe.services.create_client")
    @patch("data_cli.entsoe.services.create_entsoe_client")
    def test_empty_result(self, mock_entsoe_factory, mock_ch_factory):
        mock_entsoe = MagicMock()
        mock_entsoe.fetch_energy_prices.return_value = []
        mock_entsoe_factory.return_value.__enter__ = MagicMock(return_value=mock_entsoe)
        mock_entsoe_factory.return_value.__exit__ = MagicMock(return_value=False)

        result = backfill_energy_prices(DK1, START, END)

        assert result.rows_fetched == 0
        assert result.sets_fetched == 0
        mock_ch_factory.assert_not_called()

    @patch("data_cli.entsoe.services.insert_observations_batch")
    @patch("data_cli.entsoe.services.create_client")
    @patch("data_cli.entsoe.services.create_entsoe_client")
    def test_clickhouse_client_closed(self, mock_entsoe_factory, mock_ch_factory, mock_insert):
        obs = [_make_mock_observation(10)]
        mock_entsoe = MagicMock()
        mock_entsoe.fetch_energy_prices.return_value = obs
        mock_entsoe_factory.return_value.__enter__ = MagicMock(return_value=mock_entsoe)
        mock_entsoe_factory.return_value.__exit__ = MagicMock(return_value=False)

        mock_ch = MagicMock()
        mock_ch_factory.return_value = mock_ch

        backfill_energy_prices(DK1, START, END)
        mock_ch.close.assert_called_once()


class TestBackfillTotalLoad:
    @patch("data_cli.entsoe.services.insert_forecasts_batch")
    @patch("data_cli.entsoe.services.create_client")
    @patch("data_cli.entsoe.services.create_entsoe_client")
    def test_process_type_forwarded(self, mock_entsoe_factory, mock_ch_factory, mock_insert):
        forecasts = [_make_mock_forecast(24)]
        mock_entsoe = MagicMock()
        mock_entsoe.fetch_total_load_forecasts.return_value = forecasts
        mock_entsoe_factory.return_value.__enter__ = MagicMock(return_value=mock_entsoe)
        mock_entsoe_factory.return_value.__exit__ = MagicMock(return_value=False)

        mock_ch = MagicMock()
        mock_ch_factory.return_value = mock_ch

        result = backfill_total_load(
            DK1, START, END, process_type="A16", process_type_name="Realised"
        )

        assert result.data_type == "total_load"
        assert result.sets_fetched == 1
        assert result.rows_fetched == 24
        mock_entsoe.fetch_total_load_forecasts.assert_called_once_with(
            area=DK1,
            start_date=START,
            end_date=END,
            process_type="A16",
            process_type_name="Realised",
        )

    @patch("data_cli.entsoe.services.create_client")
    @patch("data_cli.entsoe.services.create_entsoe_client")
    def test_empty_result(self, mock_entsoe_factory, mock_ch_factory):
        mock_entsoe = MagicMock()
        mock_entsoe.fetch_total_load_forecasts.return_value = []
        mock_entsoe_factory.return_value.__enter__ = MagicMock(return_value=mock_entsoe)
        mock_entsoe_factory.return_value.__exit__ = MagicMock(return_value=False)

        result = backfill_total_load(DK1, START, END)
        assert result.rows_fetched == 0
        assert result.sets_fetched == 0


class TestBackfillGenerationForecast:
    @patch("data_cli.entsoe.services.insert_forecasts_batch")
    @patch("data_cli.entsoe.services.create_client")
    @patch("data_cli.entsoe.services.create_entsoe_client")
    def test_happy_path(self, mock_entsoe_factory, mock_ch_factory, mock_insert):
        forecasts = [_make_mock_forecast(48)]
        mock_entsoe = MagicMock()
        mock_entsoe.fetch_generation_forecasts.return_value = forecasts
        mock_entsoe_factory.return_value.__enter__ = MagicMock(return_value=mock_entsoe)
        mock_entsoe_factory.return_value.__exit__ = MagicMock(return_value=False)

        mock_ch = MagicMock()
        mock_ch_factory.return_value = mock_ch

        result = backfill_generation_forecast(DK1, START, END)

        assert result.data_type == "generation_forecast"
        assert result.sets_fetched == 1
        assert result.rows_fetched == 48


class TestBackfillWindSolar:
    @patch("data_cli.entsoe.services.insert_forecasts_batch")
    @patch("data_cli.entsoe.services.create_client")
    @patch("data_cli.entsoe.services.create_entsoe_client")
    def test_psr_type_passed_through(self, mock_entsoe_factory, mock_ch_factory, mock_insert):
        forecasts = [_make_mock_forecast(24)]
        mock_entsoe = MagicMock()
        mock_entsoe.fetch_wind_solar_forecasts.return_value = forecasts
        mock_entsoe_factory.return_value.__enter__ = MagicMock(return_value=mock_entsoe)
        mock_entsoe_factory.return_value.__exit__ = MagicMock(return_value=False)

        mock_ch = MagicMock()
        mock_ch_factory.return_value = mock_ch

        result = backfill_wind_solar(DK1, START, END, psr_type="B16")

        assert result.data_type == "wind_solar"
        mock_entsoe.fetch_wind_solar_forecasts.assert_called_once_with(
            area=DK1,
            start_date=START,
            end_date=END,
            process_type="A01",
            process_type_name="Dayahead",
            psr_type="B16",
        )

    @patch("data_cli.entsoe.services.insert_forecasts_batch")
    @patch("data_cli.entsoe.services.create_client")
    @patch("data_cli.entsoe.services.create_entsoe_client")
    def test_no_psr_type(self, mock_entsoe_factory, mock_ch_factory, mock_insert):
        forecasts = [_make_mock_forecast(24)]
        mock_entsoe = MagicMock()
        mock_entsoe.fetch_wind_solar_forecasts.return_value = forecasts
        mock_entsoe_factory.return_value.__enter__ = MagicMock(return_value=mock_entsoe)
        mock_entsoe_factory.return_value.__exit__ = MagicMock(return_value=False)

        mock_ch = MagicMock()
        mock_ch_factory.return_value = mock_ch

        result = backfill_wind_solar(DK1, START, END)

        assert result.rows_fetched == 24
        call_kwargs = mock_entsoe.fetch_wind_solar_forecasts.call_args[1]
        assert call_kwargs["psr_type"] is None

    @patch("data_cli.entsoe.services.create_client")
    @patch("data_cli.entsoe.services.create_entsoe_client")
    def test_empty_result(self, mock_entsoe_factory, mock_ch_factory):
        mock_entsoe = MagicMock()
        mock_entsoe.fetch_wind_solar_forecasts.return_value = []
        mock_entsoe_factory.return_value.__enter__ = MagicMock(return_value=mock_entsoe)
        mock_entsoe_factory.return_value.__exit__ = MagicMock(return_value=False)

        result = backfill_wind_solar(DK1, START, END)
        assert result.rows_fetched == 0
        assert result.sets_fetched == 0
