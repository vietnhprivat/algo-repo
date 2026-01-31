import polars as pl

class EnergyPrice:
    SCHEMA = {
        "source": pl.Utf8,
        "area": pl.Utf8,
        "area_timezone": pl.Utf8,
        "start_utc": pl.Datetime,
        "end_utc": pl.Datetime,
        "auction_type": pl.Utf8,
        "business_type": pl.Utf8,
        "contract_type": pl.Utf8,
        "price": pl.Float64,
    }