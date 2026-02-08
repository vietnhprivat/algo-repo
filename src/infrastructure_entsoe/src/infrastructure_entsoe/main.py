from datetime import datetime, timezone

from assets.areas import get_area_from_tag
from infrastructure_clickhouse.client_factory import create_client
from infrastructure_entsoe.client_factory import create_entsoe_client
from infrastructure_clickhouse.ingest import insert_energy_prices_batch

def main(input_area: str, start_date: datetime, end_date: datetime):
    clickhouse_client = create_client()
    area = get_area_from_tag(input_area)
    with create_entsoe_client() as client:
        energy_prices = client.fetch_energy_prices(area=area, start_date=start_date, end_date=end_date)
        insert_energy_prices_batch(clickhouse_client, energy_prices)


if __name__ == "__main__":
    area = "DK1"
    start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)
    main(input_area=area, start_date=start_date, end_date=end_date)
