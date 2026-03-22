import pandas as pd
from clickhouse_connect.driver.client import Client

from infrastructure_clickhouse.client_factory import create_client
from price_forecasting.configs import ExperimentConfig


def _price_curve_pattern(area: str) -> str:
    return f"ENTSOE {area} EnergyPrice %"



def load_price_series(client: Client, area: str) -> pd.DataFrame:
    """Query algo.timeseries for the price curve of the given area.

    Returns DataFrame with DatetimeIndex ('timestamp_utc') and 'price' column (hourly).
    """
    result = client.query(
        "SELECT timestamp_utc, value AS price "
        "FROM algo.timeseries "
        "WHERE area = {area:String} "
        "  AND curve_name LIKE {pattern:String} "
        "ORDER BY timestamp_utc",
        parameters={"area": area, "pattern": _price_curve_pattern(area)},
    )

    df = pd.DataFrame(result.result_rows, columns=["timestamp_utc", "price"])
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df = df.set_index("timestamp_utc").sort_index()
    return df


def load_exogenous_series(client: Client, area: str, curve_types: list[str]) -> pd.DataFrame:
    """Query algo.forecasts for each curve type.

    Returns DataFrame with DatetimeIndex and one column per curve type (hourly).
    Curve names follow: "ENTSOE {area} {curve_type} Dayahead"
    """
    frames = []
    for curve_type in curve_types:
        curve_name = f"ENTSOE {area} {curve_type} Dayahead"
        result = client.query(
            "SELECT timestamp_utc, value "
            "FROM algo.forecasts "
            "WHERE curve_name = {curve_name:String} "
            "ORDER BY timestamp_utc",
            parameters={"curve_name": curve_name},
        )

        df = pd.DataFrame(result.result_rows, columns=["timestamp_utc", curve_type])
        df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
        df = df.set_index("timestamp_utc").sort_index()
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    exogenous = frames[0]
    for df in frames[1:]:
        exogenous = exogenous.join(df, how="outer")

    return exogenous


def load_dataset(config: ExperimentConfig) -> pd.DataFrame:
    """Load price and exogenous data from ClickHouse for the configured area.

    Returns a single DataFrame with DatetimeIndex, 'price' column,
    and one column per exogenous curve type.
    """
    client = create_client()
    try:
        prices = load_price_series(client, config.area)

        if config.exogenous_curve_types:
            exogenous = load_exogenous_series(
                client, config.area, config.exogenous_curve_types
            )
            dataset = prices.join(exogenous, how="inner")
        else:
            dataset = prices

    finally:
        client.close()

    if dataset.empty:
        raise ValueError(
            f"No data found in ClickHouse for area '{config.area}'. "
            f"Check that data has been backfilled."
        )

    return dataset
