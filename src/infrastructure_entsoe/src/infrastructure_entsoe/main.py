from infrastructure_entsoe.client_factory import create_entsoe_client
from datetime import datetime, timedelta
from assets.areas import DK1


client = create_entsoe_client()

start = datetime(2026, 1, 28)
end = start + timedelta(days=1)

prices = client.fetch_energy_prices(
    area=DK1, 
    start_date=start, 
    end_date=end
)
