"""Register smoke-only Prefect deployments for `daily-forecast-smoke` and
`reconcile-predictions`.

Mirrors `src/schedules/src/schedules/deploy_forecast.py` but targets the
`configs/smoke.py` config and skips production cron schedules.
"""
import os
from pathlib import Path

from schedules.forecast import daily_forecast_flow
from schedules.reconciliation import reconcile_predictions_flow

CONFIGS_DIR = Path.cwd().resolve() / "configs"

_COMMON_ENV = {
    "PREFECT_API_URL": "http://server:4200/api",
    "CLICKHOUSE_HOST": "clickhouse",
    "CLICKHOUSE_PORT": "8123",
    "CLICKHOUSE_USER": os.getenv("CLICKHOUSE_USER", "default"),
    "CLICKHOUSE_PASSWORD": os.getenv("CLICKHOUSE_PASSWORD", "password"),
    "CLICKHOUSE_DATABASE": "algo",
    "LOKI_URL": "",
    "SLACK_WEBHOOK_URL": "",
}


def main() -> None:
    daily_forecast_flow.deploy(
        name="daily-forecast-smoke",
        work_pool_name="docker-pool",
        image="algo-repo:latest",
        build=False,
        push=False,
        parameters={"config_name": "smoke"},
        job_variables={
            "image_pull_policy": "Never",
            "network_mode": "algo-repo_default",
            "auto_remove": True,
            "volumes": [f"{CONFIGS_DIR}:/app/configs"],
            "env": _COMMON_ENV,
        },
        tags=["smoke"],
    )

    reconcile_predictions_flow.deploy(
        name="reconcile-predictions",
        work_pool_name="docker-pool",
        image="algo-repo:latest",
        build=False,
        push=False,
        job_variables={
            "image_pull_policy": "Never",
            "network_mode": "algo-repo_default",
            "auto_remove": True,
            "env": _COMMON_ENV,
        },
        tags=["smoke"],
    )


if __name__ == "__main__":
    main()
