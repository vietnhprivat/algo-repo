#!/usr/bin/env python
"""Deploy ingestion flow to Prefect Docker worker pool.

Reads credentials from the host .env file and bakes them into the deployment
so that spawned containers receive all necessary environment variables.
"""
import os

from dotenv import load_dotenv
from prefect import Flow

from schedules.ingestion import batch_ingest_energy_prices_flow

load_dotenv()

class EntsoeIngestionFlowDeployment:
    def __init__(self, name: str, work_pool_name: str, image: str, cron: str, flow: Flow):
        self.name = name
        self.work_pool_name = work_pool_name
        self.image = image
        self.cron = cron
        self.flow = flow

    def deploy(self):
        self.flow.deploy(
            name=self.name,
            work_pool_name=self.work_pool_name,
            image=self.image,
            build=False,  
            push=False,  
            cron=self.cron,
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
            description="Fetches ENTSOE energy prices for DK1 every hour (last 24h)",
        )

if __name__ == "__main__":
    deployment = EntsoeIngestionFlowDeployment(
        name="ingestion-hourly-now",
        work_pool_name="docker-pool",
        image="algo-repo:latest",
        cron="0 * * * *",
        flow=batch_ingest_energy_prices_flow
    )
    deployment.deploy()