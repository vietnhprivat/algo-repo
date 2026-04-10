from clickhouse_connect.driver.client import Client

from infrastructure_clickhouse.client_factory import create_client


def load_latest_artifact(
    client: Client, area: str, model_type: str, config_name: str
) -> dict | None:
    """Load the most recent model artifact for a given area, model type, and config.

    Returns a dict with artifact metadata and blob, or None if not found.
    """
    result = client.query(
        "SELECT artifact_id, created_utc, run_id, artifact_blob, artifact_size_bytes "
        "FROM algo.model_artifacts "
        "WHERE area = {area:String} "
        "  AND model_type = {model_type:String} "
        "  AND config_name = {config_name:String} "
        "ORDER BY created_utc DESC "
        "LIMIT 1",
        parameters={"area": area, "model_type": model_type, "config_name": config_name},
    )
    rows = result.result_rows
    if not rows:
        return None
    row = rows[0]
    return {
        "artifact_id": row[0],
        "created_utc": row[1],
        "run_id": row[2],
        "artifact_blob": row[3],
        "artifact_size_bytes": row[4],
    }


def create_observations_table():
    command = """
        CREATE TABLE IF NOT EXISTS algo.timeseries
        (
            source        LowCardinality(String),
            curve_name    String,
            area          LowCardinality(String),
            timezone      LowCardinality(String),
            timestamp_utc DateTime('UTC'),
            value         Float32,
            ingested_utc  DateTime('UTC')
        )
        ENGINE = ReplacingMergeTree(ingested_utc)
        ORDER BY (curve_name, timestamp_utc)
        PARTITION BY toStartOfQuarter(timestamp_utc)
        """

    client = create_client()
    try:
        client.command(command)
    finally:
        client.close()


def create_forecasts_table():
    command = """
        CREATE TABLE IF NOT EXISTS algo.forecasts
        (
            source               LowCardinality(String),
            curve_name           String,
            area                 LowCardinality(String),
            area_timezone        LowCardinality(String),
            model                LowCardinality(String),
            issued_utc           DateTime('UTC'),
            issued_timezone      LowCardinality(String),
            timestamp_utc        DateTime('UTC'),
            value                Float32,
            ingested_utc         DateTime('UTC')
        )
        ENGINE = ReplacingMergeTree(ingested_utc)
        ORDER BY (curve_name, model, issued_utc, timestamp_utc)
        PARTITION BY toStartOfQuarter(timestamp_utc)
        """

    client = create_client()
    try:
        client.command(command)
    finally:
        client.close()


def create_energy_prices_table():
    engine = "ReplacingMergeTree"
    command = f"""
        CREATE TABLE IF NOT EXISTS algo.energy_prices
        (
            source LowCardinality(String),
            area LowCardinality(String),
            area_timezone LowCardinality(String),
            start_utc DateTime('UTC'),
            end_utc DateTime('UTC'),
            auction_type LowCardinality(String),
            business_type LowCardinality(String),
            contract_type LowCardinality(String),
            price Float64,
            currency LowCardinality(String),
            ingestion_timestamp DateTime('UTC')
        )
        ENGINE = {engine}
        ORDER BY (source, area, contract_type, start_utc)
        PARTITION BY toStartOfQuarter(start_utc)
        """

    client = create_client()

    try:
        client.command(command)
    finally:
        client.close()
