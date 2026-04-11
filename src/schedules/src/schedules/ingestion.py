"""ENTSOE to ClickHouse ingestion flow.

Uses the shared service layer from data_cli.entsoe.services so that
both the CLI and Prefect flows share the same fetch + insert logic.
"""

from datetime import datetime, timedelta, timezone

from prefect import flow, task

from data_cli.entsoe.services import (
    backfill_energy_prices,
    backfill_generation_forecast,
    backfill_total_load,
    backfill_wind_solar,
)
from domain.areas import get_area_from_tag
from infrastructure_clickhouse.logging_setup import build_log_extra, get_logger

LOOKBACK_HOURS = 48
LOOKAHEAD_HOURS = 24
LOGGER = get_logger(__name__, service="prefect-ingestion")


@task(retries=2, retry_delay_seconds=60, log_prints=True)
def ingest_energy_prices_task(area_tag: str, start: datetime, end: datetime):
    area = get_area_from_tag(area_tag)
    result = backfill_energy_prices(area, start, end)
    LOGGER.info(
        "Energy price ingestion task completed",
        extra=build_log_extra(
            area=area_tag,
            chunk_start=start.isoformat(),
            chunk_end=end.isoformat(),
        ),
    )
    print(f"Energy prices: {result.sets_fetched} set(s), {result.rows_fetched} rows")
    return result


@task(retries=2, retry_delay_seconds=60, log_prints=True)
def ingest_total_load_task(area_tag: str, start: datetime, end: datetime):
    area = get_area_from_tag(area_tag)
    result = backfill_total_load(area, start, end)
    LOGGER.info(
        "Total load ingestion task completed",
        extra=build_log_extra(
            area=area_tag,
            chunk_start=start.isoformat(),
            chunk_end=end.isoformat(),
        ),
    )
    print(f"Total load: {result.sets_fetched} set(s), {result.rows_fetched} rows")
    return result


@task(retries=2, retry_delay_seconds=60, log_prints=True)
def ingest_generation_forecast_task(area_tag: str, start: datetime, end: datetime):
    area = get_area_from_tag(area_tag)
    result = backfill_generation_forecast(area, start, end)
    LOGGER.info(
        "Generation forecast ingestion task completed",
        extra=build_log_extra(
            area=area_tag,
            chunk_start=start.isoformat(),
            chunk_end=end.isoformat(),
        ),
    )
    print(f"Generation forecast: {result.sets_fetched} set(s), {result.rows_fetched} rows")
    return result


@task(retries=2, retry_delay_seconds=60, log_prints=True)
def ingest_wind_solar_task(area_tag: str, start: datetime, end: datetime):
    area = get_area_from_tag(area_tag)
    result = backfill_wind_solar(area, start, end)
    LOGGER.info(
        "Wind and solar ingestion task completed",
        extra=build_log_extra(
            area=area_tag,
            chunk_start=start.isoformat(),
            chunk_end=end.isoformat(),
        ),
    )
    print(f"Wind/solar: {result.sets_fetched} set(s), {result.rows_fetched} rows")
    return result


@flow(name="entsoe-backfill", log_prints=True)
def entsoe_backfill_flow(area: str = "DK1"):
    end = datetime.now(timezone.utc) + timedelta(hours=LOOKAHEAD_HOURS)
    start = end - timedelta(hours=LOOKBACK_HOURS)
    LOGGER.info(
        "Starting ENTSOE backfill flow",
        extra=build_log_extra(
            area=area,
            chunk_start=start.isoformat(),
            chunk_end=end.isoformat(),
        ),
    )

    prices = ingest_energy_prices_task(area, start, end)
    load = ingest_total_load_task(area, start, end)
    generation = ingest_generation_forecast_task(area, start, end)
    wind_solar = ingest_wind_solar_task(area, start, end)

    LOGGER.info(
        "Completed ENTSOE backfill flow",
        extra=build_log_extra(
            area=area,
            chunk_start=start.isoformat(),
            chunk_end=end.isoformat(),
        ),
    )

    return {
        "area": area,
        "time_window": {"start": start.isoformat(), "end": end.isoformat()},
        "results": [prices, load, generation, wind_solar],
    }
