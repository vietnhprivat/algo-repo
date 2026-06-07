"""Tests for ClickHouse data loader using a mock client."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pandas as pd
import pytest

from price_forecasting.data.clickhouse_loader import (
    load_price_series,
    load_exogenous_series,
    resample_hourly,
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


class TestLoadExogenousAggregates:
    def _two_member_client(self) -> MagicMock:
        t0 = datetime(2024, 1, 1, 0, tzinfo=timezone.utc)
        t1 = datetime(2024, 1, 1, 1, tzinfo=timezone.utc)
        onshore = [(t0, 100.0), (t1, 110.0)]
        offshore = [(t0, 40.0), (t1, 44.0)]
        client = MagicMock()
        client.query.side_effect = [
            _make_mock_query_result(onshore, ["timestamp_utc", "value"]),
            _make_mock_query_result(offshore, ["timestamp_utc", "value"]),
        ]
        return client

    def test_aggregate_column_is_sum_of_members(self) -> None:
        client = self._two_member_client()
        df = load_exogenous_series(
            client, "DK1", [], {"Wind": ["WindOnshore", "WindOffshore"]}
        )
        assert list(df.columns) == ["Wind"]
        assert df["Wind"].tolist() == [140.0, 154.0]

    def test_aggregate_queries_each_member_curve(self) -> None:
        client = self._two_member_client()
        load_exogenous_series(
            client, "DK1", [], {"Wind": ["WindOnshore", "WindOffshore"]}
        )
        calls = client.query.call_args_list
        curve_names = [
            c.kwargs.get("parameters", c[1].get("parameters", {})).get("curve_name")
            for c in calls
        ]
        assert "ENTSOE DK1 WindOnshore Dayahead" in curve_names
        assert "ENTSOE DK1 WindOffshore Dayahead" in curve_names

    def test_aggregate_drops_timestamps_missing_in_any_member(self) -> None:
        t0 = datetime(2024, 1, 1, 0, tzinfo=timezone.utc)
        t1 = datetime(2024, 1, 1, 1, tzinfo=timezone.utc)
        onshore = [(t0, 100.0), (t1, 110.0)]
        offshore = [(t0, 40.0)]  # t1 missing
        client = MagicMock()
        client.query.side_effect = [
            _make_mock_query_result(onshore, ["timestamp_utc", "value"]),
            _make_mock_query_result(offshore, ["timestamp_utc", "value"]),
        ]
        df = load_exogenous_series(
            client, "DK1", [], {"Wind": ["WindOnshore", "WindOffshore"]}
        )
        assert len(df) == 1
        assert df["Wind"].tolist() == [140.0]

    def test_plain_and_aggregate_columns_combine(self) -> None:
        t0 = datetime(2024, 1, 1, 0, tzinfo=timezone.utc)
        load_rows = [(t0, 45000.0)]
        onshore = [(t0, 100.0)]
        offshore = [(t0, 40.0)]
        client = MagicMock()
        client.query.side_effect = [
            _make_mock_query_result(load_rows, ["timestamp_utc", "value"]),
            _make_mock_query_result(onshore, ["timestamp_utc", "value"]),
            _make_mock_query_result(offshore, ["timestamp_utc", "value"]),
        ]
        df = load_exogenous_series(
            client, "DK1", ["TotalLoad"], {"Wind": ["WindOnshore", "WindOffshore"]}
        )
        assert list(df.columns) == ["TotalLoad", "Wind"]
        assert df["Wind"].tolist() == [140.0]
        assert df["TotalLoad"].tolist() == [45000.0]

    def test_aggregate_with_no_members_raises_clear_error(self) -> None:
        client = MagicMock()
        with pytest.raises(ValueError, match="'Wind'.*no member curves"):
            load_exogenous_series(client, "DK1", [], {"Wind": []})

    def test_mixed_resolution_exog_anchors_to_coarsest_grid(self) -> None:
        """A 15-min member series must not leak sub-hourly timestamps into
        the joined frame when another exogenous column is hourly."""
        h0 = datetime(2024, 1, 1, 0, tzinfo=timezone.utc)
        h1 = datetime(2024, 1, 1, 1, tzinfo=timezone.utc)
        q15 = datetime(2024, 1, 1, 0, 15, tzinfo=timezone.utc)
        load_rows = [(h0, 45000.0), (h1, 46000.0)]  # hourly
        onshore = [(h0, 100.0), (q15, 105.0), (h1, 110.0)]  # 15-min
        offshore = [(h0, 40.0), (q15, 42.0), (h1, 44.0)]  # 15-min
        client = MagicMock()
        client.query.side_effect = [
            _make_mock_query_result(load_rows, ["timestamp_utc", "value"]),
            _make_mock_query_result(onshore, ["timestamp_utc", "value"]),
            _make_mock_query_result(offshore, ["timestamp_utc", "value"]),
        ]
        df = load_exogenous_series(
            client, "DK1", ["TotalLoad"], {"Wind": ["WindOnshore", "WindOffshore"]}
        )
        assert list(df.index) == [h0, h1]  # q15 must NOT appear
        assert df["Wind"].tolist() == [140.0, 154.0]
        assert not df.isna().any().any()


class TestResampleHourly:
    def test_averages_four_quarters_into_one_hour(self) -> None:
        idx = pd.to_datetime([
            "2024-01-01T00:00", "2024-01-01T00:15",
            "2024-01-01T00:30", "2024-01-01T00:45",
            "2024-01-01T01:00",
        ], utc=True)
        df = pd.DataFrame(
            {"price": [10.0, 20.0, 30.0, 40.0, 100.0],
             "Wind": [1.0, 1.0, 1.0, 1.0, 5.0]},
            index=idx,
        )
        out = resample_hourly(df)
        assert list(out.index) == list(pd.to_datetime(
            ["2024-01-01T00:00", "2024-01-01T01:00"], utc=True))
        assert out.loc[pd.Timestamp("2024-01-01T00:00", tz="UTC"), "price"] == 25.0
        assert out.loc[pd.Timestamp("2024-01-01T01:00", tz="UTC"), "price"] == 100.0

    def test_already_hourly_is_unchanged(self) -> None:
        idx = pd.to_datetime(
            ["2024-01-01T00:00", "2024-01-01T01:00", "2024-01-01T02:00"], utc=True)
        df = pd.DataFrame({"price": [10.0, 20.0, 30.0]}, index=idx)
        out = resample_hourly(df)
        assert out["price"].tolist() == [10.0, 20.0, 30.0]
        assert len(out) == 3

    def test_empty_frame_returns_empty(self) -> None:
        out = resample_hourly(pd.DataFrame())
        assert out.empty
