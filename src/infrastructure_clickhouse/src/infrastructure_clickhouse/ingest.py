from datetime import datetime, timezone

from clickhouse_connect.driver.client import Client
import polars as pl
from typing import List

from domain.curves import Forecast, Observations
from infrastructure_clickhouse.logging_setup import build_log_extra, get_logger

LOGGER = get_logger(__name__, service="clickhouse-ingest")


def insert_observations_batch(
    client: Client,
    observations: List[Observations],
) -> None:
    data_frames = pl.concat([obs.data_frame for obs in observations])
    insert_polars_dataframe(client, data_frames, "algo.timeseries")


def insert_forecasts_batch(
    client: Client,
    forecasts: List[Forecast],
) -> None:
    data_frames = pl.concat([f.data_frame for f in forecasts])
    insert_polars_dataframe(client, data_frames, "algo.forecasts")


def insert_experiment_run(
    client: Client,
    run_id: str,
    created_utc: datetime,
    experiment_name: str,
    area: str,
    model_type: str,
    config_json: str,
    metrics_json: str,
    *,
    training_duration_seconds: float | None = None,
    data_start_utc: datetime | None = None,
    data_end_utc: datetime | None = None,
    model_artifact_id: str | None = None,
) -> None:
    _epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)

    df = pl.DataFrame(
        {
            "run_id": [run_id],
            "created_utc": [created_utc],
            "experiment_name": [experiment_name],
            "area": [area],
            "model_type": [model_type],
            "config_json": [config_json],
            "metrics_json": [metrics_json],
            "training_duration_seconds": [training_duration_seconds if training_duration_seconds is not None else 0.0],
            "data_start_utc": [data_start_utc if data_start_utc is not None else _epoch],
            "data_end_utc": [data_end_utc if data_end_utc is not None else _epoch],
            "model_artifact_id": [model_artifact_id if model_artifact_id is not None else ""],
        },
        schema={
            "run_id": pl.String,
            "created_utc": pl.Datetime("us", "UTC"),
            "experiment_name": pl.String,
            "area": pl.String,
            "model_type": pl.String,
            "config_json": pl.String,
            "metrics_json": pl.String,
            "training_duration_seconds": pl.Float32,
            "data_start_utc": pl.Datetime("us", "UTC"),
            "data_end_utc": pl.Datetime("us", "UTC"),
            "model_artifact_id": pl.String,
        },
    )
    insert_polars_dataframe(client, df, "algo.experiment_runs")


def insert_model_artifact(
    client: Client,
    artifact_id: str,
    created_utc: datetime,
    run_id: str,
    area: str,
    model_type: str,
    config_name: str,
    artifact_blob: str,
    artifact_size_bytes: int,
) -> None:
    df = pl.DataFrame(
        {
            "artifact_id": [artifact_id],
            "created_utc": [created_utc],
            "run_id": [run_id],
            "area": [area],
            "model_type": [model_type],
            "config_name": [config_name],
            "artifact_blob": [artifact_blob],
            "artifact_size_bytes": [artifact_size_bytes],
        },
        schema={
            "artifact_id": pl.String,
            "created_utc": pl.Datetime("us", "UTC"),
            "run_id": pl.String,
            "area": pl.String,
            "model_type": pl.String,
            "config_name": pl.String,
            "artifact_blob": pl.String,
            "artifact_size_bytes": pl.UInt32,
        },
    )
    insert_polars_dataframe(client, df, "algo.model_artifacts")


def insert_experiment_predictions(
    client: Client,
    predictions: pl.DataFrame,
) -> None:
    """Insert experiment predictions into algo.experiment_predictions.

    Expected schema: run_id (String), timestamp_utc (Datetime), actual (Float32), predicted (Float32)
    """
    insert_polars_dataframe(client, predictions, "algo.experiment_predictions")


def insert_drift_report(
    client: Client,
    *,
    report_id: str,
    created_utc: datetime,
    area: str,
    curve_name: str,
    reference_start_utc: datetime,
    reference_end_utc: datetime,
    current_start_utc: datetime,
    current_end_utc: datetime,
    stat_test: str,
    drift_score: float,
    drift_threshold: float,
    drift_detected: bool,
    reference_n: int,
    current_n: int,
) -> None:
    df = pl.DataFrame(
        {
            "report_id": [report_id],
            "created_utc": [created_utc],
            "area": [area],
            "curve_name": [curve_name],
            "reference_start_utc": [reference_start_utc],
            "reference_end_utc": [reference_end_utc],
            "current_start_utc": [current_start_utc],
            "current_end_utc": [current_end_utc],
            "stat_test": [stat_test],
            "drift_score": [drift_score],
            "drift_threshold": [drift_threshold],
            "drift_detected": [1 if drift_detected else 0],
            "reference_n": [reference_n],
            "current_n": [current_n],
        },
        schema={
            "report_id": pl.String,
            "created_utc": pl.Datetime("us", "UTC"),
            "area": pl.String,
            "curve_name": pl.String,
            "reference_start_utc": pl.Datetime("us", "UTC"),
            "reference_end_utc": pl.Datetime("us", "UTC"),
            "current_start_utc": pl.Datetime("us", "UTC"),
            "current_end_utc": pl.Datetime("us", "UTC"),
            "stat_test": pl.String,
            "drift_score": pl.Float64,
            "drift_threshold": pl.Float64,
            "drift_detected": pl.UInt8,
            "reference_n": pl.UInt32,
            "current_n": pl.UInt32,
        },
    )
    insert_polars_dataframe(client, df, "algo.drift_reports")


def insert_hyperparam_trial(
    client: Client,
    *,
    study_name: str,
    trial_number: int,
    created_utc: datetime,
    area: str,
    model_type: str,
    config_name: str,
    state: str,
    value: float | None,
    params_json: str,
    val_start_utc: datetime | None,
    val_end_utc: datetime | None,
    duration_seconds: float | None,
) -> None:
    df = pl.DataFrame(
        {
            "study_name": [study_name],
            "trial_number": [trial_number],
            "created_utc": [created_utc],
            "area": [area],
            "model_type": [model_type],
            "config_name": [config_name],
            "state": [state],
            "value": [value],
            "params_json": [params_json],
            "val_start_utc": [val_start_utc],
            "val_end_utc": [val_end_utc],
            "duration_seconds": [duration_seconds],
        },
        schema={
            "study_name": pl.String,
            "trial_number": pl.UInt32,
            "created_utc": pl.Datetime("ms", "UTC"),
            "area": pl.String,
            "model_type": pl.String,
            "config_name": pl.String,
            "state": pl.String,
            "value": pl.Float64,
            "params_json": pl.String,
            "val_start_utc": pl.Datetime("ms", "UTC"),
            "val_end_utc": pl.Datetime("ms", "UTC"),
            "duration_seconds": pl.Float64,
        },
    )
    insert_polars_dataframe(client, df, "algo.hyperparam_trials")


def insert_polars_dataframe(
    client: Client, dataframe: pl.DataFrame, table_name: str, batch_size: int = 10_000
) -> None:
    """Insert a Polars DataFrame into ClickHouse in batches using insert_arrow.

    Args:
        client: clickhouse-connect client instance.
        df: Polars DataFrame to insert.
        table_name: Target ClickHouse table name.
        batch_size: Number of rows per batch.
    """
    batch_count = (dataframe.height + batch_size - 1) // batch_size if dataframe.height else 0
    LOGGER.info(
        "Starting ClickHouse insert",
        extra=build_log_extra(
            table_name=table_name,
            batch_size=batch_size,
            row_count=dataframe.height,
            batch_count=batch_count,
        ),
    )
    for offset in range(0, dataframe.height, batch_size):
        batch = dataframe.slice(offset, batch_size)
        try:
            client.insert_arrow(table_name, batch.to_arrow())
        except Exception:
            LOGGER.exception(
                "ClickHouse insert failed",
                extra=build_log_extra(
                    table_name=table_name,
                    batch_size=batch_size,
                    offset=offset,
                ),
            )
            raise
