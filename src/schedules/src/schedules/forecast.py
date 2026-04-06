"""Daily forecast flow.

Runs LiveRunner for a given config and stores predictions in ClickHouse.
Uses the same shared service layer pattern as ingestion: forecast_cli
handles config loading and tracking, price_forecasting handles prediction.
"""

from datetime import datetime, timedelta, timezone

from prefect import flow, task

from forecast_cli.config_loader import load_config
from forecast_cli.tracking import track_prediction
from price_forecasting import LiveRunner
from price_forecasting.configs import ExperimentConfig


@task(log_prints=True)
def load_config_task(config_name: str) -> ExperimentConfig:
    config = load_config(config_name)
    print(f"Loaded config: {config.experiment_name} (area={config.area}, model={config.model_type})")
    return config


@task(retries=2, retry_delay_seconds=60, log_prints=True)
def predict_task(config: ExperimentConfig, target_date: str):
    runner = LiveRunner(config)
    prediction = runner.run_live(target_date)
    print(f"Prediction for {target_date}: {len(prediction)} periods")
    return prediction


@task(log_prints=True)
def track_prediction_task(config: ExperimentConfig, target_date: str, prediction) -> str:
    run_id = track_prediction(config, target_date, prediction)
    print(f"Tracked prediction {run_id} in ClickHouse")
    return run_id


@flow(name="daily-forecast", log_prints=True)
def daily_forecast_flow(config_name: str = "dk1_lear", target_date: str | None = None):
    if target_date is None:
        target_date = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

    print(f"Running forecast: config={config_name}, target_date={target_date}")

    config = load_config_task(config_name)
    prediction = predict_task(config, target_date)
    run_id = track_prediction_task(config, target_date, prediction)

    return {
        "config_name": config_name,
        "area": config.area,
        "target_date": target_date,
        "run_id": run_id,
        "n_periods": len(prediction),
    }
