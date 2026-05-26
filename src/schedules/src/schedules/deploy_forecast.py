#!/usr/bin/env python
"""Deploy forecast flow to Prefect Docker worker pool.

Reads credentials from the host .env file and bakes them into the deployment
so that spawned containers receive all necessary environment variables.
Configs are mounted from the host via Docker volume (no image rebuild needed).
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from prefect import Flow

from schedules.drift import drift_detection_flow
from schedules.forecast import daily_forecast_flow
from schedules.reconciliation import reconcile_predictions_flow

load_dotenv()

CONFIGS_DIR = Path.cwd().resolve() / "configs"

# W&B environment variables for observability_wandb
WANDB_API_KEY = os.environ.get("WANDB_API_KEY", "")
WANDB_ENTITY = os.environ.get("WANDB_ENTITY", "")
WANDB_PROJECT = os.environ.get("WANDB_PROJECT", "algo-research")
WANDB_MODE = os.environ.get("WANDB_MODE", "" if WANDB_API_KEY else "disabled")


class ForecastFlowDeployment:
    def __init__(
        self,
        name: str,
        work_pool_name: str,
        image: str,
        cron: str,
        flow: Flow,
        parameters: dict | None = None,
    ):
        self.name = name
        self.work_pool_name = work_pool_name
        self.image = image
        self.cron = cron
        self.flow = flow
        self.parameters = parameters or {}

    def deploy(self):
        self.flow.deploy(
            name=self.name,
            work_pool_name=self.work_pool_name,
            image=self.image,
            build=False,
            push=False,
            cron=self.cron,
            parameters=self.parameters,
            job_variables={
                "image_pull_policy": "Never",
                "network_mode": "algo-repo_default",
                "auto_remove": True,
                "volumes": [f"{CONFIGS_DIR}:/app/configs"],
                "env": {
                    "PREFECT_API_URL": "http://server:4200/api",
                    "CLICKHOUSE_HOST": "clickhouse",
                    "CLICKHOUSE_PORT": "8123",
                    "CLICKHOUSE_USER": os.getenv("CLICKHOUSE_USER", "default"),
                    "CLICKHOUSE_PASSWORD": os.getenv("CLICKHOUSE_PASSWORD", "password"),
                    "CLICKHOUSE_DATABASE": "algo",
                    "LOKI_URL": os.getenv("LOKI_URL", "http://loki:3100/loki/api/v1/push"),
                    "SLACK_WEBHOOK_URL": os.getenv("SLACK_WEBHOOK_URL", ""),
                    "WANDB_API_KEY": WANDB_API_KEY,
                    "WANDB_ENTITY": WANDB_ENTITY,
                    "WANDB_PROJECT": WANDB_PROJECT,
                    "WANDB_MODE": WANDB_MODE,
                },
            },
            tags=["forecast", "production"],
            description="Runs daily price forecast for the configured experiment config",
        )


FORECAST_CONFIGS = [
    "dk1_lear",
    "de_lear",
    "dk1_dnn",
    "de_dnn",
    "dk1_transformer",
    "de_transformer",
]
DRIFT_AREAS = ["DK1", "DE"]

if __name__ == "__main__":
    for config_name in FORECAST_CONFIGS:
        ForecastFlowDeployment(
            name=f"daily-forecast-{config_name}",
            work_pool_name="docker-pool",
            image="algo-repo:latest",
            cron="0 6 * * *",
            flow=daily_forecast_flow,
            parameters={"config_name": config_name},
        ).deploy()

    # Reconciliation runs once daily at 18:00 UTC — 4h after ENTSO-E day-ahead
    # prices are published (~14:00 UTC), giving a comfortable buffer.
    ForecastFlowDeployment(
        name="reconcile-predictions",
        work_pool_name="docker-pool",
        image="algo-repo:latest",
        cron="0 18 * * *",
        flow=reconcile_predictions_flow,
        parameters={},
    ).deploy()

    # Drift detection runs at 19:00 UTC, one hour after reconciliation so the
    # latest day's actuals are in place before we compute distributions.
    for area in DRIFT_AREAS:
        ForecastFlowDeployment(
            name=f"drift-detection-{area.lower()}",
            work_pool_name="docker-pool",
            image="algo-repo:latest",
            cron="0 19 * * *",
            flow=drift_detection_flow,
            parameters={"area": area},
        ).deploy()
