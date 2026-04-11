"""Integration tests for ClickHouse ingest using a fake client."""

import logging
import pytest
import pyarrow as pa

from infrastructure_clickhouse.ingest import (
    insert_energy_prices_batch,
    insert_forecasts_batch,
    insert_observations_batch,
    insert_polars_dataframe,
)

from tests.infrastructure_clickhouse.conftest import (
    FakeClickHouseClient,
    make_sample_energy_price_observation,
    make_sample_forecast,
    make_sample_observations,
)


class FailingClickHouseClient(FakeClickHouseClient):
    def insert_arrow(self, table_name: str, arrow_table) -> None:
        raise RuntimeError("insert failed")


class TestInsertEnergyPricesBatch:
    """Test the batch insert pipeline with fake client."""

    def test_single_observation_inserts_one_batch(self):
        client = FakeClickHouseClient()
        obs = make_sample_energy_price_observation(24)
        insert_energy_prices_batch(client, [obs])

        assert len(client.inserted) == 1
        table_name, arrow_table = client.inserted[0]
        assert table_name == "algo.energy_prices"
        assert isinstance(arrow_table, pa.Table)
        assert arrow_table.num_rows == 24

    def test_multiple_observations_are_concatenated(self):
        client = FakeClickHouseClient()
        obs1 = make_sample_energy_price_observation(24)
        obs2 = make_sample_energy_price_observation(24)
        insert_energy_prices_batch(client, [obs1, obs2])

        # 48 rows total, may be split by batch_size but default 10_000 fits
        total_rows = sum(t.num_rows for _, t in client.inserted if isinstance(t, pa.Table))
        assert total_rows == 48

    def test_empty_list_raises(self):
        """Concatenating empty list of observations should raise."""
        client = FakeClickHouseClient()
        with pytest.raises(Exception):
            insert_energy_prices_batch(client, [])


class TestInsertForecastsBatch:
    """Test the forecast batch insert pipeline with fake client."""

    def test_single_forecast_inserts_one_batch(self):
        client = FakeClickHouseClient()
        forecast = make_sample_forecast(n_rows=24)
        insert_forecasts_batch(client, [forecast])

        assert len(client.inserted) == 1
        table_name, arrow_table = client.inserted[0]
        assert table_name == "algo.forecasts"
        assert isinstance(arrow_table, pa.Table)
        assert arrow_table.num_rows == 24

    def test_multiple_forecasts_are_concatenated(self):
        client = FakeClickHouseClient()
        f1 = make_sample_forecast("ENTSOE DE TotalLoad Dayahead", n_rows=24)
        f2 = make_sample_forecast("ENTSOE DK1 TotalLoad Dayahead", n_rows=24)
        insert_forecasts_batch(client, [f1, f2])

        total_rows = sum(t.num_rows for _, t in client.inserted if isinstance(t, pa.Table))
        assert total_rows == 48

    def test_empty_list_raises(self):
        client = FakeClickHouseClient()
        with pytest.raises(Exception):
            insert_forecasts_batch(client, [])


class TestInsertObservationsBatch:
    """Test the observations batch insert pipeline with fake client."""

    def test_single_observations_inserts_one_batch(self):
        client = FakeClickHouseClient()
        obs = make_sample_observations(n_rows=24)
        insert_observations_batch(client, [obs])

        assert len(client.inserted) == 1
        table_name, arrow_table = client.inserted[0]
        assert table_name == "algo.timeseries"
        assert isinstance(arrow_table, pa.Table)
        assert arrow_table.num_rows == 24

    def test_multiple_observations_are_concatenated(self):
        client = FakeClickHouseClient()
        obs1 = make_sample_observations("ENTSOE DE Daily EUR", n_rows=24)
        obs2 = make_sample_observations("ENTSOE DK1 Daily EUR", n_rows=24)
        insert_observations_batch(client, [obs1, obs2])

        total_rows = sum(t.num_rows for _, t in client.inserted if isinstance(t, pa.Table))
        assert total_rows == 48

    def test_empty_list_raises(self):
        client = FakeClickHouseClient()
        with pytest.raises(Exception):
            insert_observations_batch(client, [])


class TestInsertPolarsDataframe:
    """Test the low-level batch insert function."""

    def test_small_dataframe_single_batch(self):
        client = FakeClickHouseClient()
        obs = make_sample_energy_price_observation(10)
        insert_polars_dataframe(client, obs.data_frame, "test_table")

        assert len(client.inserted) == 1
        assert client.inserted[0][0] == "test_table"

    def test_batching_splits_large_data(self):
        client = FakeClickHouseClient()
        obs = make_sample_energy_price_observation(24)
        # Use a tiny batch_size to force multiple inserts
        insert_polars_dataframe(client, obs.data_frame, "test_table", batch_size=10)

        assert len(client.inserted) == 3  # 24 rows / 10 batch size = 3 batches
        total_rows = sum(t.num_rows for _, t in client.inserted if isinstance(t, pa.Table))
        assert total_rows == 24

    def test_arrow_conversion_preserves_columns(self):
        client = FakeClickHouseClient()
        obs = make_sample_energy_price_observation(5)
        insert_polars_dataframe(client, obs.data_frame, "test_table")

        _, arrow_table = client.inserted[0]
        assert isinstance(arrow_table, pa.Table)
        expected_columns = list(obs.data_frame.columns)
        assert arrow_table.column_names == expected_columns

    def test_insert_failure_is_logged(self, caplog):
        client = FailingClickHouseClient()
        obs = make_sample_energy_price_observation(5)

        with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError, match="insert failed"):
            insert_polars_dataframe(client, obs.data_frame, "test_table", batch_size=2)

        assert any(
            record.message == "ClickHouse insert failed"
            and getattr(record, "table_name", None) == "test_table"
            and getattr(record, "batch_size", None) == 2
            for record in caplog.records
        )
