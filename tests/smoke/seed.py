"""Seed ClickHouse with synthetic data for the PR smoke test."""
from infrastructure_clickhouse.client_factory import create_client
from infrastructure_clickhouse.ingest import (
    insert_forecasts_batch,
    insert_observations_batch,
)

from tests.smoke.fixtures import build_load_forecasts, build_price_observations


def main() -> None:
    client = create_client()
    try:
        insert_observations_batch(client, [build_price_observations()])
        insert_forecasts_batch(client, [build_load_forecasts()])
        print("Smoke fixtures seeded into algo.timeseries and algo.forecasts")
    finally:
        client.close()


if __name__ == "__main__":
    main()
