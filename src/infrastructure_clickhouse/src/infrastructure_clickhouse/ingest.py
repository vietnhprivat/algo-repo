from datetime import datetime

from clickhouse_connect.driver.client import Client
import polars as pl
from typing import List

from domain.curves import EnergyPriceObservation, Forecast, Observations


def insert_observations_batch(
    client: Client,
    observations: List[Observations],
) -> None:
    data_frames = pl.concat([obs.data_frame for obs in observations])
    insert_polars_dataframe(client, data_frames, "algo.timeseries")


def insert_energy_prices_batch(
    client: Client,
    energy_prices: List[EnergyPriceObservation],
) -> None:
    data_frames = pl.concat([price.data_frame for price in energy_prices])
    insert_polars_dataframe(client, data_frames, "algo.energy_prices")


def insert_forecasts_batch(
    client: Client,
    forecasts: List[Forecast],
) -> None:
    data_frames = pl.concat([f.data_frame for f in forecasts])
    insert_polars_dataframe(client, data_frames, "algo.forecasts")


def insert_experiment_run(
    client: Client,
    run_id: str,
    created_utc: datetime,
    experiment_name: str,
    area: str,
    model_type: str,
    config_json: str,
    metrics_json: str,
) -> None:
    df = pl.DataFrame(
        {
            "run_id": [run_id],
            "created_utc": [created_utc],
            "experiment_name": [experiment_name],
            "area": [area],
            "model_type": [model_type],
            "config_json": [config_json],
            "metrics_json": [metrics_json],
        },
        schema={
            "run_id": pl.String,
            "created_utc": pl.Datetime("us", "UTC"),
            "experiment_name": pl.String,
            "area": pl.String,
            "model_type": pl.String,
            "config_json": pl.String,
            "metrics_json": pl.String,
        },
    )
    insert_polars_dataframe(client, df, "algo.experiment_runs")


def insert_experiment_predictions(
    client: Client,
    predictions: pl.DataFrame,
) -> None:
    """Insert experiment predictions into algo.experiment_predictions.

    Expected schema: run_id (String), timestamp_utc (Datetime), actual (Float32), predicted (Float32)
    """
    insert_polars_dataframe(client, predictions, "algo.experiment_predictions")


def insert_polars_dataframe(
    client: Client, dataframe: pl.DataFrame, table_name: str, batch_size: int = 10_000
) -> None:
    """Insert a Polars DataFrame into ClickHouse in batches using insert_arrow.

    Args:
        client: clickhouse-connect client instance.
        df: Polars DataFrame to insert.
        table_name: Target ClickHouse table name.
        batch_size: Number of rows per batch.
    """
    for offset in range(0, dataframe.height, batch_size):
        batch = dataframe.slice(offset, batch_size)
        client.insert_arrow(table_name, batch.to_arrow())
