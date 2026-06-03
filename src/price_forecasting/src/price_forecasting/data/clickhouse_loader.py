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
    df = df.drop_duplicates(subset=["timestamp_utc"], keep="last")
    df = df.set_index("timestamp_utc").sort_index()
    return df


def _fetch_curve(client: Client, area: str, curve_type: str) -> pd.DataFrame:
    """Fetch one forecast curve as a single-column DataFrame indexed by timestamp."""
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
    df = df.drop_duplicates(subset=["timestamp_utc"], keep="last")
    df = df.set_index("timestamp_utc").sort_index()
    return df


def load_exogenous_series(
    client: Client,
    area: str,
    curve_types: list[str],
    aggregates: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """Query algo.forecasts for each curve type and each aggregate.

    Returns DataFrame with DatetimeIndex, one column per curve type, plus one
    column per aggregate (the sum of its member curves, inner-joined on
    timestamps so partial sums never occur).
    Curve names follow: "ENTSOE {area} {curve_type} Dayahead"

    All exogenous columns are inner-joined together on timestamps, so the
    coarsest series anchors the time grid.  Timestamps missing any exogenous
    value are dropped; with same-resolution inputs this is behaviour-identical
    to an outer join (no rows are lost).
    """
    frames = [_fetch_curve(client, area, curve_type) for curve_type in curve_types]

    for aggregate_name, members in (aggregates or {}).items():
        if not members:
            raise ValueError(
                f"exogenous_aggregates[{aggregate_name!r}] has no member curves"
            )
        member_frames = [_fetch_curve(client, area, member) for member in members]
        joined = member_frames[0]
        for member_frame in member_frames[1:]:
            joined = joined.join(member_frame, how="inner")
        # skipna=False: a NULL member value must surface as NaN (and be dropped
        # downstream), never silently understate the sum.
        frames.append(joined.sum(axis=1, skipna=False).to_frame(name=aggregate_name))

    if not frames:
        return pd.DataFrame()

    exogenous = frames[0]
    for df in frames[1:]:
        exogenous = exogenous.join(df, how="inner")

    return exogenous


def load_dataset(config: ExperimentConfig) -> pd.DataFrame:
    """Load price and exogenous data from ClickHouse for the configured area.

    Returns a single DataFrame with DatetimeIndex, 'price' column,
    and one column per exogenous curve type.
    """
    client = create_client()
    try:
        prices = load_price_series(client, config.area)

        if config.exogenous_curve_types or config.exogenous_aggregates:
            exogenous = load_exogenous_series(
                client,
                config.area,
                config.exogenous_curve_types,
                config.exogenous_aggregates,
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
