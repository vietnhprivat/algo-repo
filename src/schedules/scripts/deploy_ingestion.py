#!/usr/bin/env python
"""Deploy ingestion flow to Prefect Docker worker pool.

Reads credentials from the host .env file and bakes them into the deployment
so that spawned containers receive all necessary environment variables.
"""
import os

from dotenv import load_dotenv

from schedules.ingestion import entsoe_ingestion_flow

load_dotenv()

if __name__ == "__main__":
    entsoe_ingestion_flow.deploy(
        name="ingestion-hourly",
        work_pool_name="docker-pool",
        image="algo-repo:latest",  # Pre-built local image
        build=False,  # Don't build — use existing image
        push=False,  # Don't push — it's local only
        cron="0 * * * *",  # Every hour at minute 0
        job_variables={
            "image_pull_policy": "Never",  # Use local image, don't pull
            "network_mode": "algo-repo_default",  # Connect to compose network
            "auto_remove": True,  # Clean up container after run
            "env": {
                # Prefect API — so the container can report flow run status
                "PREFECT_API_URL": "http://server:4200/api",
                # ClickHouse — use Docker service name, not localhost
                "CLICKHOUSE_HOST": "clickhouse",
                "CLICKHOUSE_PORT": "8123",
                "CLICKHOUSE_USER": os.getenv("CLICKHOUSE_USER", "default"),
                "CLICKHOUSE_PASSWORD": os.getenv("CLICKHOUSE_PASSWORD", "password"),
                "CLICKHOUSE_DATABASE": "algo",
                # ENTSOE API key
                "ENTSOE_API_KEY": os.getenv("ENTSOE_API_KEY", ""),
            },
        },
        tags=["entsoe", "ingestion", "production"],
        description="Fetches ENTSOE energy prices for DK1 every hour (last 24h)",
    )

    print("Deployment 'ingestion-hourly' created successfully!")
    print("The worker will execute this flow every hour at minute 0.")
    print("View deployments at: http://localhost:4200/deployments")
