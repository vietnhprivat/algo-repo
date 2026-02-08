from infrastructure_clickhouse.client_factory import create_client

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

