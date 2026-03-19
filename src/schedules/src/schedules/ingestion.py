"""ENTSOE to ClickHouse ingestion flow."""
from datetime import datetime, timedelta, timezone

from prefect import flow, task

from domain.areas import get_area_from_tag
from infrastructure_clickhouse.client_factory import create_client
from infrastructure_clickhouse.ingest import insert_observations_batch
from infrastructure_entsoe.client_factory import create_entsoe_client


@task(retries=2, retry_delay_seconds=60, log_prints=True)
def batch_ingest_energy_prices_task(area_tag: str, start_time: datetime, end_time: datetime):
    area = get_area_from_tag(area_tag)    
    clickhouse_client = create_client()
    
    with create_entsoe_client() as entsoe_client:
        all_energy_prices = entsoe_client.fetch_energy_prices(
            area=area,
            start_date=start_time,
            end_date=end_time
        )
        
        if not all_energy_prices:
            return None
        
        insert_observations_batch(clickhouse_client, all_energy_prices)

@flow(name="entsoe-ingestion", log_prints=True)
def batch_ingest_energy_prices_flow():
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=24)
    areas = ["DK1"]
    
    results = []
    for area in areas:
        result = batch_ingest_energy_prices_task(area, start_time, end_time)
        results.append(result)


    return {
        "status": "completed",
        "areas": results,
        "time_window": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat()
        }
    }

