"""Tests for ClickHouse data loader using a mock client."""

import pytest
import pandas as pd
from datetime import datetime, timezone
from unittest.mock import MagicMock

from price_forecasting.data.clickhouse_loader import (
    load_price_series,
    load_exogenous_series,
)


def _make_mock_query_result(rows, columns):
    """Create a mock ClickHouse query result."""
    result = MagicMock()
    result.result_rows = rows
    return result


class TestLoadPriceSeries:

    def test_returns_dataframe_with_price_column(self):
        rows = [
            (datetime(2024, 1, 1, 0, tzinfo=timezone.utc), 50.0),
            (datetime(2024, 1, 1, 1, tzinfo=timezone.utc), 51.0),
            (datetime(2024, 1, 1, 2, tzinfo=timezone.utc), 52.0),
        ]
        client = MagicMock()
        client.query.return_value = _make_mock_query_result(rows, ["timestamp_utc", "price"])

        df = load_price_series(client, "DE")

        assert "price" in df.columns
        assert len(df) == 3
        assert df.index.name == "timestamp_utc"

    def test_queries_with_correct_area_and_pattern(self):
        client = MagicMock()
        client.query.return_value = _make_mock_query_result([], [])

        load_price_series(client, "DK1")

        call_args = client.query.call_args
        params = call_args.kwargs.get("parameters") or call_args[1].get("parameters")
        assert params["area"] == "DK1"
        assert "ENTSOE DK1 EnergyPrice" in params["pattern"]

    def test_empty_result_returns_empty_dataframe(self):
        client = MagicMock()
        client.query.return_value = _make_mock_query_result([], [])

        df = load_price_series(client, "DE")
        assert len(df) == 0


class TestLoadExogenousSeries:

    def test_returns_columns_per_curve_type(self):
        rows = [
            (datetime(2024, 1, 1, 0, tzinfo=timezone.utc), 45000.0),
            (datetime(2024, 1, 1, 1, tzinfo=timezone.utc), 46000.0),
        ]
        client = MagicMock()
        client.query.return_value = _make_mock_query_result(rows, ["timestamp_utc", "value"])

        df = load_exogenous_series(client, "DE", ["TotalLoad", "Generation"])

        assert "TotalLoad" in df.columns
        assert "Generation" in df.columns

    def test_queries_correct_curve_names(self):
        client = MagicMock()
        client.query.return_value = _make_mock_query_result([], [])

        load_exogenous_series(client, "DK1", ["TotalLoad", "Solar"])

        assert client.query.call_count == 2
        calls = client.query.call_args_list
        curve_names = [
            c.kwargs.get("parameters", c[1].get("parameters", {})).get("curve_name")
            for c in calls
        ]
        assert "ENTSOE DK1 TotalLoad Dayahead" in curve_names
        assert "ENTSOE DK1 Solar Dayahead" in curve_names

    def test_empty_curve_types_returns_empty_dataframe(self):
        client = MagicMock()
        df = load_exogenous_series(client, "DE", [])
        assert df.empty
