"""Fake ClickHouse client for integration tests."""

from datetime import datetime, timezone

import polars as pl
import pyarrow as pa

from domain.curves import EnergyPriceObservation


class FakeClickHouseClient:
    """In-memory fake that records insert_arrow calls instead of hitting a real DB."""

    def __init__(self):
        self.inserted: list[tuple[str, pa.Table]] = []
        self.commands: list[str] = []
        self.closed = False

    def insert_arrow(self, table_name: str, arrow_table) -> None:
        self.inserted.append((table_name, arrow_table))

    def command(self, sql: str) -> None:
        self.commands.append(sql)

    def close(self) -> None:
        self.closed = True


def make_sample_energy_price_observation(n_rows: int = 24) -> EnergyPriceObservation:
    """Create a sample EnergyPriceObservation matching the expected schema."""
    now = datetime.now(timezone.utc)
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

    rows = []
    for i in range(n_rows):
        rows.append(
            {
                "source": "ENTSOE",
                "area": "DE",
                "area_timezone": "Europe/Berlin",
                "start_utc": base_time.replace(hour=i % 24),
                "end_utc": base_time.replace(hour=(i + 1) % 24 if i < 23 else 0),
                "auction_type": "Implicit",
                "business_type": "Production",
                "contract_type": "Daily",
                "price": 50.0 + i,
                "currency": "EUR",
                "ingestion_timestamp": now,
            }
        )

    df = pl.DataFrame(
        rows,
        schema={
            "source": pl.Utf8,
            "area": pl.Utf8,
            "area_timezone": pl.Utf8,
            "start_utc": pl.Datetime(time_zone=str(timezone.utc)),
            "end_utc": pl.Datetime(time_zone=str(timezone.utc)),
            "auction_type": pl.Utf8,
            "business_type": pl.Utf8,
            "contract_type": pl.Utf8,
            "price": pl.Float64,
            "currency": pl.Utf8,
            "ingestion_timestamp": pl.Datetime(time_zone=str(timezone.utc)),
        },
    )
    return EnergyPriceObservation(df)
