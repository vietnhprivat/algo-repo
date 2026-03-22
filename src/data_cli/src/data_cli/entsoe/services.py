"""Core backfill functions for ENTSOE data.

These functions contain the shared fetch + insert logic used by both the
data_cli commands and the Prefect scheduled flows. No typer dependency —
pure Python, returns a result dataclass.
"""

from dataclasses import dataclass
from datetime import datetime

from domain.areas import Area
from infrastructure_clickhouse.client_factory import create_client
from infrastructure_clickhouse.ingest import insert_forecasts_batch, insert_observations_batch
from infrastructure_entsoe.client_factory import create_entsoe_client


@dataclass
class BackfillResult:
    data_type: str
    area: str
    sets_fetched: int
    rows_fetched: int


def backfill_energy_prices(
    area: Area,
    start: datetime,
    end: datetime,
) -> BackfillResult:
    """Fetch ENTSOE energy prices and insert into algo.timeseries."""
    with create_entsoe_client() as entsoe_client:
        observations = entsoe_client.fetch_energy_prices(
            area=area, start_date=start, end_date=end
        )

    if not observations:
        return BackfillResult("energy_prices", area.tag, 0, 0)

    total_rows = sum(obs.data_frame.height for obs in observations)
    ch_client = create_client()
    try:
        insert_observations_batch(ch_client, observations)
    finally:
        ch_client.close()

    return BackfillResult("energy_prices", area.tag, len(observations), total_rows)


def backfill_total_load(
    area: Area,
    start: datetime,
    end: datetime,
    process_type: str = "A01",
    process_type_name: str = "Dayahead",
) -> BackfillResult:
    """Fetch ENTSOE total load forecasts and insert into algo.forecasts."""
    with create_entsoe_client() as entsoe_client:
        forecasts = entsoe_client.fetch_total_load_forecasts(
            area=area,
            start_date=start,
            end_date=end,
            process_type=process_type,
            process_type_name=process_type_name,
        )

    if not forecasts:
        return BackfillResult("total_load", area.tag, 0, 0)

    total_rows = sum(f.data_frame.height for f in forecasts)
    ch_client = create_client()
    try:
        insert_forecasts_batch(ch_client, forecasts)
    finally:
        ch_client.close()

    return BackfillResult("total_load", area.tag, len(forecasts), total_rows)


def backfill_generation_forecast(
    area: Area,
    start: datetime,
    end: datetime,
    process_type: str = "A01",
    process_type_name: str = "Dayahead",
) -> BackfillResult:
    """Fetch ENTSOE generation forecasts and insert into algo.forecasts."""
    with create_entsoe_client() as entsoe_client:
        forecasts = entsoe_client.fetch_generation_forecasts(
            area=area,
            start_date=start,
            end_date=end,
            process_type=process_type,
            process_type_name=process_type_name,
        )

    if not forecasts:
        return BackfillResult("generation_forecast", area.tag, 0, 0)

    total_rows = sum(f.data_frame.height for f in forecasts)
    ch_client = create_client()
    try:
        insert_forecasts_batch(ch_client, forecasts)
    finally:
        ch_client.close()

    return BackfillResult("generation_forecast", area.tag, len(forecasts), total_rows)


def backfill_wind_solar(
    area: Area,
    start: datetime,
    end: datetime,
    process_type: str = "A01",
    process_type_name: str = "Dayahead",
    psr_type: str | None = None,
) -> BackfillResult:
    """Fetch ENTSOE wind/solar forecasts and insert into algo.forecasts."""
    with create_entsoe_client() as entsoe_client:
        forecasts = entsoe_client.fetch_wind_solar_forecasts(
            area=area,
            start_date=start,
            end_date=end,
            process_type=process_type,
            process_type_name=process_type_name,
            psr_type=psr_type,
        )

    if not forecasts:
        return BackfillResult("wind_solar", area.tag, 0, 0)

    total_rows = sum(f.data_frame.height for f in forecasts)
    ch_client = create_client()
    try:
        insert_forecasts_batch(ch_client, forecasts)
    finally:
        ch_client.close()

    return BackfillResult("wind_solar", area.tag, len(forecasts), total_rows)
