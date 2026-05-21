"""ClickHouse experiment tracking — write runs and predictions."""

import base64
import io
import json
import os
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

import joblib
import pandas as pd
import polars as pl

from infrastructure_clickhouse.client_factory import create_client
from infrastructure_clickhouse.ingest import (
    insert_experiment_predictions,
    insert_experiment_run,
    insert_model_artifact,
)
from price_forecasting.configs import ExperimentConfig


def _resolve_git_sha() -> str:
    """Return the build-time git SHA from env, or '' if unset.

    Env-driven on purpose: production sets GIT_SHA at image build time via
    cd_deploy.yml. Local runs leave it unset to avoid stamping dirty trees.
    """
    return os.environ.get("GIT_SHA", "")


def _generate_run_id() -> str:
    return str(uuid.uuid4())


def _serialize_model(model) -> tuple[str, int]:
    """Serialize a model to base64 string, returning (blob, size_bytes)."""
    buf = io.BytesIO()
    joblib.dump(model, buf)
    raw_bytes = buf.getvalue()
    size_bytes = len(raw_bytes)
    blob = base64.b64encode(raw_bytes).decode("ascii")
    return blob, size_bytes



def _reshape_wide_to_long(
    run_id: str,
    forecasts: pd.DataFrame,
    actuals: pd.DataFrame,
) -> pl.DataFrame:
    """Reshape wide DataFrames (days x h0..hN) to long format for ClickHouse."""
    n_periods = forecasts.shape[1]

    # 1440 = minutes in a day; divides evenly for hourly (60) and 15-min (15) resolutions
    minutes_per_period = 1440 // n_periods  

    forecasts_long = forecasts.reset_index(names="date").melt(id_vars="date", var_name="col", value_name="predicted")
    actuals_long = actuals.reset_index(names="date").melt(id_vars="date", var_name="col", value_name="actual")

    df = forecasts_long.merge(actuals_long, on=["date", "col"])
    df["period"] = df["col"].str[1:].astype(int)
    df["timestamp_utc"] = pd.to_datetime(df["date"]) + pd.to_timedelta(df["period"] * minutes_per_period, unit="m")
    df["timestamp_utc"] = df["timestamp_utc"].dt.tz_localize("UTC")
    df["run_id"] = run_id

    return pl.from_pandas(
        df[["run_id", "timestamp_utc", "actual", "predicted"]],
        schema_overrides={"actual": pl.Float32, "predicted": pl.Float32},
    )


def _prediction_series_to_long(
    run_id: str,
    target_date: str,
    predictions: pd.Series,
) -> pl.DataFrame:
    """Convert a prediction Series to long format for ClickHouse."""
    n_periods = len(predictions)

    # 1440 = minutes in a day; divides evenly for hourly (60) and 15-min (15) resolutions
    minutes_per_period = 1440 // n_periods  
    base_date = pd.Timestamp(target_date, tz="UTC")
    timestamps = base_date + pd.to_timedelta(range(n_periods), unit="m") * minutes_per_period

    return pl.from_pandas(
        pd.DataFrame(
            {
                "run_id": run_id,
                "timestamp_utc": timestamps,
                "actual": 0.0,
                "predicted": predictions.to_numpy(),
            }
        ),
        schema_overrides={"actual": pl.Float32, "predicted": pl.Float32},
    )


def track_backtest_run(
    config: ExperimentConfig,
    forecasts: pd.DataFrame,
    actuals: pd.DataFrame,
    metrics: dict,
    *,
    training_duration_seconds: float = 0.0,
) -> str:
    """Store a backtest run and its predictions in ClickHouse.

    Returns the generated run_id.
    """
    run_id = _generate_run_id()
    now = datetime.now(timezone.utc)
    config_json = json.dumps(asdict(config))
    metrics_json = json.dumps(metrics)

    predictions_df = _reshape_wide_to_long(run_id, forecasts, actuals)

    client = create_client()
    try:
        insert_experiment_run(
            client,
            run_id=run_id,
            created_utc=now,
            experiment_name=config.experiment_name,
            area=config.area,
            model_type=config.model_type,
            config_json=config_json,
            metrics_json=metrics_json,
            training_duration_seconds=training_duration_seconds,
            git_sha=_resolve_git_sha(),
        )
        insert_experiment_predictions(client, predictions_df)
    finally:
        client.close()

    return run_id


def track_prediction(
    config: ExperimentConfig,
    target_date: str,
    predictions: pd.Series,
    *,
    training_duration_seconds: float | None = None,
    data_start_utc: datetime | None = None,
    data_end_utc: datetime | None = None,
    trained_models: dict | None = None,
    config_name: str | None = None,
) -> str:
    """Store a live prediction in ClickHouse.

    Returns the generated run_id.
    """
    run_id = _generate_run_id()
    now = datetime.now(timezone.utc)
    config_json = json.dumps(asdict(config))

    predictions_df = _prediction_series_to_long(run_id, target_date, predictions)

    client = create_client()
    try:
        artifact_id = None
        if trained_models:
            artifact_id = str(uuid.uuid4())
            blob, size_bytes = _serialize_model(trained_models)
            insert_model_artifact(
                client,
                artifact_id=artifact_id,
                created_utc=now,
                run_id=run_id,
                area=config.area,
                model_type=config.model_type,
                config_name=config_name or config.experiment_name,
                artifact_blob=blob,
                artifact_size_bytes=size_bytes,
            )

        insert_experiment_run(
            client,
            run_id=run_id,
            created_utc=now,
            experiment_name=config.experiment_name,
            area=config.area,
            model_type=config.model_type,
            config_json=config_json,
            metrics_json="{}",
            training_duration_seconds=training_duration_seconds,
            data_start_utc=data_start_utc,
            data_end_utc=data_end_utc,
            model_artifact_id=artifact_id,
            git_sha=_resolve_git_sha(),
        )
        insert_experiment_predictions(client, predictions_df)
    finally:
        client.close()

    return run_id
