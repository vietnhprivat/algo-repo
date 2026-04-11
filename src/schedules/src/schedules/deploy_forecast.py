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

from schedules.forecast import daily_forecast_flow
from schedules.reconciliation import reconcile_predictions_flow

load_dotenv()

CONFIGS_DIR = Path.cwd().resolve() / "configs"


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
                },
            },
            tags=["forecast", "production"],
            description="Runs daily price forecast for the configured experiment config",
        )


FORECAST_CONFIGS = ["dk1_lear"]

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
