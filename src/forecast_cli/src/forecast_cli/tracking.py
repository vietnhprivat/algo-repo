"""ClickHouse experiment tracking — write runs and predictions."""

import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone

import pandas as pd
import polars as pl

from infrastructure_clickhouse.client_factory import create_client
from infrastructure_clickhouse.ingest import (
    insert_experiment_predictions,
    insert_experiment_run,
)
from price_forecasting.configs import ExperimentConfig


def _generate_run_id() -> str:
    return str(uuid.uuid4())


def _period_timedelta(period_idx: int, n_periods: int) -> pd.Timedelta:
    """Convert a period index to a timedelta offset from midnight."""
    minutes_per_period = 1440 // n_periods
    return pd.Timedelta(minutes=period_idx * minutes_per_period)


def _reshape_wide_to_long(
    run_id: str,
    forecasts: pd.DataFrame,
    actuals: pd.DataFrame,
) -> pl.DataFrame:
    """Reshape wide DataFrames (days x h0..hN) to long format for ClickHouse."""
    n_periods = forecasts.shape[1]
    rows = []
    for date in forecasts.index:
        for p in range(n_periods):
            col = f"h{p}"
            timestamp = pd.Timestamp(date) + _period_timedelta(p, n_periods)
            rows.append(
                {
                    "run_id": run_id,
                    "timestamp_utc": timestamp.to_pydatetime().replace(
                        tzinfo=timezone.utc
                    ),
                    "actual": float(actuals.loc[date, col]),
                    "predicted": float(forecasts.loc[date, col]),
                }
            )

    return pl.DataFrame(
        rows,
        schema={
            "run_id": pl.String,
            "timestamp_utc": pl.Datetime("us", "UTC"),
            "actual": pl.Float32,
            "predicted": pl.Float32,
        },
    )


def _prediction_series_to_long(
    run_id: str,
    target_date: str,
    predictions: pd.Series,
) -> pl.DataFrame:
    """Convert a prediction Series to long format for ClickHouse."""
    n_periods = len(predictions)
    base_date = pd.Timestamp(target_date)
    rows = []
    for p in range(n_periods):
        timestamp = base_date + _period_timedelta(p, n_periods)
        rows.append(
            {
                "run_id": run_id,
                "timestamp_utc": timestamp.to_pydatetime().replace(
                    tzinfo=timezone.utc
                ),
                "actual": 0.0,
                "predicted": float(predictions.iloc[p]),
            }
        )

    return pl.DataFrame(
        rows,
        schema={
            "run_id": pl.String,
            "timestamp_utc": pl.Datetime("us", "UTC"),
            "actual": pl.Float32,
            "predicted": pl.Float32,
        },
    )


def track_backtest_run(
    config: ExperimentConfig,
    forecasts: pd.DataFrame,
    actuals: pd.DataFrame,
    metrics: dict,
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
        )
        insert_experiment_predictions(client, predictions_df)
    finally:
        client.close()

    return run_id


def track_prediction(
    config: ExperimentConfig,
    target_date: str,
    predictions: pd.Series,
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
        insert_experiment_run(
            client,
            run_id=run_id,
            created_utc=now,
            experiment_name=config.experiment_name,
            area=config.area,
            model_type=config.model_type,
            config_json=config_json,
            metrics_json="{}",
        )
        insert_experiment_predictions(client, predictions_df)
    finally:
        client.close()

    return run_id
