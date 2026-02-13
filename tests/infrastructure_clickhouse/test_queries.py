"""Integration tests for ClickHouse queries module (DDL logic only, no real DB)."""


from tests.infrastructure_clickhouse.conftest import FakeClickHouseClient


class TestCreateEnergyPricesTable:
    """Test the DDL command generation by monkey-patching create_client."""

    def test_create_table_command_contains_expected_sql(self, monkeypatch):
        fake_client = FakeClickHouseClient()

        # Patch create_client so queries.py uses our fake
        monkeypatch.setattr(
            "infrastructure_clickhouse.queries.create_client",
            lambda: fake_client,
        )

        from infrastructure_clickhouse.queries import create_energy_prices_table

        create_energy_prices_table()

        assert len(fake_client.commands) == 1
        sql = fake_client.commands[0]
        assert "CREATE TABLE IF NOT EXISTS" in sql
        assert "algo.energy_prices" in sql
        assert "ReplacingMergeTree" in sql
        assert "start_utc" in sql
        assert "price Float64" in sql
        assert fake_client.closed is True
