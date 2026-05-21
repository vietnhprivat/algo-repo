"""Integration tests for ClickHouse queries module (DDL logic only, no real DB)."""


from tests.infrastructure_clickhouse.conftest import FakeClickHouseClient


class TestCreateForecastsTable:
    """Test DDL for the algo.forecasts table."""

    def test_create_table_command_contains_expected_sql(self, monkeypatch):
        fake_client = FakeClickHouseClient()

        monkeypatch.setattr(
            "infrastructure_clickhouse.queries.create_client",
            lambda: fake_client,
        )

        from infrastructure_clickhouse.queries import create_forecasts_table

        create_forecasts_table()

        assert len(fake_client.commands) == 1
        sql = fake_client.commands[0]
        assert "CREATE TABLE IF NOT EXISTS" in sql
        assert "algo.forecasts" in sql
        assert "ReplacingMergeTree" in sql
        assert "model" in sql
        assert "issued_utc" in sql
        assert "Float32" in sql
        assert fake_client.closed is True


class TestCreateObservationsTable:
    """Test DDL for the algo.timeseries observations table."""

    def test_create_table_command_contains_expected_sql(self, monkeypatch):
        fake_client = FakeClickHouseClient()

        monkeypatch.setattr(
            "infrastructure_clickhouse.queries.create_client",
            lambda: fake_client,
        )

        from infrastructure_clickhouse.queries import create_observations_table

        create_observations_table()

        assert len(fake_client.commands) == 1
        sql = fake_client.commands[0]
        assert "CREATE TABLE IF NOT EXISTS" in sql
        assert "algo.timeseries" in sql
        assert "ReplacingMergeTree" in sql
        assert "curve_name" in sql
        assert "timestamp_utc" in sql
        assert "Float32" in sql
        assert fake_client.closed is True
