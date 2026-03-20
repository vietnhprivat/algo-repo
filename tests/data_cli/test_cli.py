"""Tests for the data_cli backfill tool."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from typer import Exit
from typer.testing import CliRunner

from data_cli.main import app
from data_cli.utils import parse_flexible_datetime, resolve_area
from domain.areas import DK1, DE


runner = CliRunner()


class TestParseFlexibleDatetime:
    def test_iso_date(self):
        result = parse_flexible_datetime("2022-12-24")
        assert result == datetime(2022, 12, 24, tzinfo=timezone.utc)

    def test_human_readable_short_month(self):
        result = parse_flexible_datetime("1 jan 2022")
        assert result == datetime(2022, 1, 1, tzinfo=timezone.utc)

    def test_human_readable_full_month(self):
        result = parse_flexible_datetime("1 January 2022")
        assert result == datetime(2022, 1, 1, tzinfo=timezone.utc)

    def test_compact_format(self):
        result = parse_flexible_datetime("202412240001")
        assert result == datetime(2024, 12, 24, 0, 1, tzinfo=timezone.utc)

    def test_compact_format_midnight(self):
        result = parse_flexible_datetime("202501010000")
        assert result == datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)

    def test_date_with_hour_hyphen(self):
        result = parse_flexible_datetime("2022-12-24-00:00")
        assert result == datetime(2022, 12, 24, 0, 0, tzinfo=timezone.utc)

    def test_date_with_nonzero_hour(self):
        result = parse_flexible_datetime("2022-12-24-14:30")
        assert result == datetime(2022, 12, 24, 14, 30, tzinfo=timezone.utc)

    def test_naive_datetime_gets_utc(self):
        result = parse_flexible_datetime("2022-06-15")
        assert result.tzinfo == timezone.utc

    def test_invalid_string_exits(self):
        with pytest.raises((SystemExit, Exit)):
            parse_flexible_datetime("not-a-date")

    def test_whitespace_is_stripped(self):
        result = parse_flexible_datetime("  2022-12-24  ")
        assert result == datetime(2022, 12, 24, tzinfo=timezone.utc)


class TestResolveArea:
    def test_uppercase_input(self):
        assert resolve_area("DK1") == DK1

    def test_lowercase_input(self):
        assert resolve_area("dk1") == DK1

    def test_mixed_case(self):
        assert resolve_area("Dk1") == DK1

    def test_different_area(self):
        assert resolve_area("de") == DE

    def test_invalid_area_exits(self):
        with pytest.raises((SystemExit, Exit)):
            resolve_area("XYZ123")

    def test_whitespace_is_stripped(self):
        assert resolve_area("  dk1  ") == DK1


class TestBackfillEntsoePriceDocument:
    @patch("data_cli.entsoe.backfill.create_client")
    @patch("data_cli.entsoe.backfill.create_entsoe_client")
    @patch("data_cli.entsoe.backfill.insert_observations_batch")
    def test_successful_backfill(self, mock_insert, mock_entsoe_factory, mock_ch_factory):
        mock_obs = MagicMock()
        mock_obs.data_frame.height = 24

        mock_entsoe = MagicMock()
        mock_entsoe.fetch_energy_prices.return_value = [mock_obs]
        mock_entsoe.__enter__ = MagicMock(return_value=mock_entsoe)
        mock_entsoe.__exit__ = MagicMock(return_value=False)
        mock_entsoe_factory.return_value = mock_entsoe

        mock_ch = MagicMock()
        mock_ch_factory.return_value = mock_ch

        result = runner.invoke(
            app,
            ["entsoe", "backfill", "price-document", "--area", "dk1", "--start", "2024-01-01", "--end", "2024-01-02"],
        )

        assert result.exit_code == 0
        assert "Backfilling ENTSOE price document for DK1" in result.output
        assert "Successfully inserted into algo.timeseries" in result.output
        mock_insert.assert_called_once_with(mock_ch, [mock_obs])

    def test_invalid_area(self):
        result = runner.invoke(
            app,
            ["entsoe", "backfill", "price-document", "--area", "INVALID", "--start", "2024-01-01", "--end", "2024-01-02"],
        )
        assert result.exit_code == 1
        assert "Unknown area tag" in result.output

    def test_invalid_date(self):
        result = runner.invoke(
            app,
            ["entsoe", "backfill", "price-document", "--area", "dk1", "--start", "not-a-date", "--end", "2024-01-02"],
        )
        assert result.exit_code == 1
        assert "Cannot parse datetime" in result.output

    def test_start_after_end(self):
        result = runner.invoke(
            app,
            ["entsoe", "backfill", "price-document", "--area", "dk1", "--start", "2024-02-01", "--end", "2024-01-01"],
        )
        assert result.exit_code == 1
        assert "must be before end" in result.output

    @patch("data_cli.entsoe.backfill.create_entsoe_client")
    def test_no_data_returned(self, mock_entsoe_factory):
        mock_entsoe = MagicMock()
        mock_entsoe.fetch_energy_prices.return_value = []
        mock_entsoe.__enter__ = MagicMock(return_value=mock_entsoe)
        mock_entsoe.__exit__ = MagicMock(return_value=False)
        mock_entsoe_factory.return_value = mock_entsoe

        result = runner.invoke(
            app,
            ["entsoe", "backfill", "price-document", "--area", "dk1", "--start", "2024-01-01", "--end", "2024-01-02"],
        )

        assert result.exit_code == 0
        assert "No data returned" in result.output

    def test_short_flags(self):
        result = runner.invoke(
            app,
            ["entsoe", "backfill", "price-document", "-a", "INVALID", "-s", "2024-01-01", "-e", "2024-01-02"],
        )
        assert result.exit_code == 1
        assert "Unknown area tag" in result.output
