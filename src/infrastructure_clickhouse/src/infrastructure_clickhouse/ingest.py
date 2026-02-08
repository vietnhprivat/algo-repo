import polars as pl
from typing import List
from assets.data_objects import EnergyPriceObservation


def insert_energy_prices_batch(
    client,
    energy_prices: List[EnergyPriceObservation],
) -> None:
    data_frames = pl.concat([price.data_frame for price in energy_prices])
    insert_polars_dataframe(client, data_frames, "algo.energy_prices")



def insert_polars_dataframe(
        client, 
        dataframe: pl.DataFrame, 
        table_name: str, 
        batch_size: int = 10_000
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
