"""Integration tests for ClickHouse ingest using a fake client."""

import pytest
import pyarrow as pa

from infrastructure_clickhouse.ingest import (
    insert_energy_prices_batch,
    insert_polars_dataframe,
)

from tests.infrastructure_clickhouse.conftest import (
    FakeClickHouseClient,
    make_sample_energy_price_observation,
)


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
