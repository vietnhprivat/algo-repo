"""Daily forecast flow.

Runs LiveRunner for a given config and stores predictions in ClickHouse.
Uses the same shared service layer pattern as ingestion: forecast_cli
handles config loading and tracking, price_forecasting handles prediction.
"""

from datetime import datetime, timedelta, timezone

from prefect import flow, task

from forecast_cli.config_loader import load_config
from forecast_cli.tracking import track_prediction
from infrastructure_clickhouse.logging_setup import build_log_extra, get_logger
from price_forecasting import LiveRunner
from price_forecasting.configs import ExperimentConfig
from price_forecasting.live_runner import LiveResult

LOGGER = get_logger(__name__, service="prefect-forecast")


@task(log_prints=True)
def load_config_task(config_name: str) -> ExperimentConfig:
    config = load_config(config_name)
    LOGGER.info(
        "Loaded forecast config",
        extra=build_log_extra(
            area=config.area,
            config_name=config_name,
        ),
    )
    print(f"Loaded config: {config.experiment_name} (area={config.area}, model={config.model_type})")
    return config


@task(retries=2, retry_delay_seconds=60, log_prints=True)
def predict_task(config: ExperimentConfig, target_date: str) -> LiveResult:
    runner = LiveRunner(config)
    result = runner.run_live_with_metadata(target_date)
    LOGGER.info(
        "Forecast prediction completed",
        extra=build_log_extra(
            area=config.area,
            config_name=config.experiment_name,
            target_date=target_date,
        ),
    )
    print(
        f"Prediction for {target_date}: {len(result.prediction)} periods, "
        f"training took {result.training_duration_seconds:.2f}s"
    )
    return result


@task(log_prints=True)
def track_prediction_task(
    config: ExperimentConfig,
    target_date: str,
    result: LiveResult,
    config_name: str,
) -> str:
    run_id = track_prediction(
        config,
        target_date,
        result.prediction,
        training_duration_seconds=result.training_duration_seconds,
        data_start_utc=result.data_start_utc,
        data_end_utc=result.data_end_utc,
        trained_models=result.trained_models,
        config_name=config_name,
    )
    LOGGER.info(
        "Tracked forecast prediction",
        extra=build_log_extra(
            area=config.area,
            config_name=config_name,
            target_date=target_date,
            run_id=run_id,
        ),
    )
    print(f"Tracked prediction {run_id} in ClickHouse")
    return run_id


@flow(name="daily-forecast", log_prints=True)
def daily_forecast_flow(config_name: str = "dk1_lear", target_date: str | None = None):
    if target_date is None:
        target_date = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

    LOGGER.info(
        "Starting daily forecast flow",
        extra=build_log_extra(
            config_name=config_name,
            target_date=target_date,
        ),
    )
    print(f"Running forecast: config={config_name}, target_date={target_date}")

    config = load_config_task(config_name)
    result = predict_task(config, target_date)
    run_id = track_prediction_task(config, target_date, result, config_name)

    LOGGER.info(
        "Completed daily forecast flow",
        extra=build_log_extra(
            area=config.area,
            config_name=config_name,
            target_date=target_date,
            run_id=run_id,
        ),
    )

    return {
        "config_name": config_name,
        "area": config.area,
        "target_date": target_date,
        "run_id": run_id,
        "n_periods": len(result.prediction),
        "training_duration_seconds": result.training_duration_seconds,
    }
