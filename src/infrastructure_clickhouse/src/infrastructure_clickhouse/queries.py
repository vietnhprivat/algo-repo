from infrastructure_clickhouse.client_factory import create_client


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
