from datetime import datetime

from clickhouse_connect.driver.client import Client

from infrastructure_clickhouse.client_factory import create_client


def get_unreconciled_runs(client: Client) -> list[dict]:
    """Find live prediction runs that haven't been reconciled yet (metrics_json='{}').

    Returns all 11 columns so the caller can re-insert the row with updated metrics.
    """
    result = client.query(
        "SELECT run_id, created_utc, experiment_name, area, model_type, "
        "       config_json, metrics_json, training_duration_seconds, "
        "       data_start_utc, data_end_utc, model_artifact_id "
        "FROM algo.experiment_runs FINAL "
        "WHERE metrics_json = '{}' "
        "ORDER BY created_utc"
    )
    columns = [
        "run_id",
        "created_utc",
        "experiment_name",
        "area",
        "model_type",
        "config_json",
        "metrics_json",
        "training_duration_seconds",
        "data_start_utc",
        "data_end_utc",
        "model_artifact_id",
    ]
    return [dict(zip(columns, row)) for row in result.result_rows]


def get_predictions_for_runs(client: Client, run_ids: list[str]) -> list[dict]:
    """Fetch all predictions for the given run_ids."""
    if not run_ids:
        return []
    result = client.query(
        "SELECT run_id, timestamp_utc, actual, predicted "
        "FROM algo.experiment_predictions FINAL "
        "WHERE run_id IN {run_ids:Array(String)} "
        "ORDER BY run_id, timestamp_utc",
        parameters={"run_ids": run_ids},
    )
    return [
        {
            "run_id": row[0],
            "timestamp_utc": row[1],
            "actual": row[2],
            "predicted": row[3],
        }
        for row in result.result_rows
    ]


def get_actual_prices_for_period(
    client: Client, area: str, start_utc: datetime, end_utc: datetime
) -> list[dict]:
    """Fetch actual prices from algo.timeseries for a given area and time range.

    Matches ENTSOE energy price curves for the area (e.g. ``ENTSOE DK1 EnergyPrice ...``).
    """
    pattern = f"ENTSOE {area} EnergyPrice %"
    result = client.query(
        "SELECT timestamp_utc, value AS price "
        "FROM algo.timeseries FINAL "
        "WHERE area = {area:String} "
        "  AND curve_name LIKE {pattern:String} "
        "  AND timestamp_utc >= {start_utc:DateTime64} "
        "  AND timestamp_utc < {end_utc:DateTime64} "
        "ORDER BY timestamp_utc",
        parameters={
            "area": area,
            "pattern": pattern,
            "start_utc": start_utc,
            "end_utc": end_utc,
        },
    )
    return [{"timestamp_utc": row[0], "price": row[1]} for row in result.result_rows]


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
