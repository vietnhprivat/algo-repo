"""ENTSOE to ClickHouse ingestion flow."""
from datetime import datetime, timedelta, timezone

from prefect import flow, task

from domain.areas import get_area_from_tag
from infrastructure_clickhouse.client_factory import create_client
from infrastructure_clickhouse.ingest import insert_energy_prices_batch
from infrastructure_entsoe.client_factory import create_entsoe_client


@task(retries=2, retry_delay_seconds=60, log_prints=True)
def ingest_area_task(area_tag: str, start_time: datetime, end_time: datetime):
    """Fetch energy prices from ENTSOE and insert into ClickHouse."""
    area = get_area_from_tag(area_tag)
    
    print(f"Ingesting {area_tag} from {start_time} to {end_time}")
    
    clickhouse_client = create_client()
    
    with create_entsoe_client() as entsoe_client:
        all_energy_prices = entsoe_client.fetch_energy_prices(
            area=area,
            start_date=start_time,
            end_date=end_time
        )
        
        if not all_energy_prices:
            print(f"WARNING: No data received for {area_tag}")
            return {"area": area_tag, "records": 0, "status": "no_data"}
        
        insert_energy_prices_batch(clickhouse_client, all_energy_prices)

        total_records = sum(len(energy_price.data_frame) for energy_price in all_energy_prices)
        print(f"Successfully ingested {total_records} records for {area_tag}")
        
        return {
            "area": area_tag,
            "records": total_records,
            "status": "success"
        }


@flow(name="entsoe-ingestion", log_prints=True)
def entsoe_ingestion_flow():
    """
    Ingest energy prices from ENTSOE API.
    Runs every hour, fetches last 24 hours of data for DK1.
    """
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=24)
    
    print("Starting ENTSOE ingestion flow")
    print(f"Time window: {start_time} to {end_time}")
    
    areas = ["DK1"]
    
    results = []
    for area in areas:
        result = ingest_area_task(area, start_time, end_time)
        results.append(result)
    
    total_records = sum(r["records"] for r in results)
    print(f"Flow completed. Total records ingested: {total_records}")
    
    return {
        "status": "completed",
        "total_records": total_records,
        "areas": results,
        "time_window": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat()
        }
    }


if __name__ == "__main__":
    # Run the flow locally for testing
    entsoe_ingestion_flow()