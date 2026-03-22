#!/usr/bin/env python
"""Deploy ingestion flow to Prefect Docker worker pool.

Reads credentials from the host .env file and bakes them into the deployment
so that spawned containers receive all necessary environment variables.
"""
import os

from dotenv import load_dotenv
from prefect import Flow

from schedules.ingestion import entsoe_backfill_flow

load_dotenv()

class EntsoeIngestionFlowDeployment:
    def __init__(self, name: str, work_pool_name: str, image: str, cron: str, flow: Flow, parameters: dict | None = None):
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
                "env": {
                    "PREFECT_API_URL": "http://server:4200/api",
                    "CLICKHOUSE_HOST": "clickhouse",
                    "CLICKHOUSE_PORT": "8123",
                    "CLICKHOUSE_USER": os.getenv("CLICKHOUSE_USER", "default"),
                    "CLICKHOUSE_PASSWORD": os.getenv("CLICKHOUSE_PASSWORD", "password"),
                    "CLICKHOUSE_DATABASE": "algo",
                    "ENTSOE_API_KEY": os.getenv("ENTSOE_API_KEY", ""),
                },
            },
            tags=["entsoe", "ingestion", "production"],
            description="Fetches all ENTSOE data types for the configured area (last 48h)",
        )

AREAS = ["DK1", "DK2", "NL", "BE", "DE", "FR", "PL"]

if __name__ == "__main__":
    for area in AREAS:
        EntsoeIngestionFlowDeployment(
            name=f"entsoe-backfill-{area.lower()}",
            work_pool_name="docker-pool",
            image="algo-repo:latest",
            cron="0 * * * *",
            flow=entsoe_backfill_flow,
            parameters={"area": area},
        ).deploy()
