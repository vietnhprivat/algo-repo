#!/usr/bin/env python
"""Deploy ingestion flow to Prefect worker."""
from schedules.ingestion import entsoe_ingestion_flow

if __name__ == "__main__":
    # Deploy the ingestion flow to docker worker pool
    entsoe_ingestion_flow.deploy(
        name="ingestion-hourly",
        work_pool_name="docker-pool",
        image="algo-repo:latest",  # Use our pre-built local image
        build=False,  # Don't build - use existing image
        push=False,  # Don't push - it's local only
        cron="0 * * * *",  # Every hour at minute 0
        job_variables={
            "image_pull_policy": "Never",  # Use local image, don't pull
            "network_mode": "algo-repo_default",  # Connect to compose network
            "auto_remove": True,  # Clean up container after run
        },
        tags=["entsoe", "ingestion", "production"],
        description="Fetches ENTSOE energy prices for DK1 every hour (last 24h)"
    )
    
    print("Deployment created successfully!")
    print("The worker will now execute this flow every hour at minute 0.")
    print("View deployments at: http://localhost:4200/deployments")
