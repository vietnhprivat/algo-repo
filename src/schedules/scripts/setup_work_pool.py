#!/usr/bin/env python
"""Create Docker work pool for Prefect (optional — the worker auto-creates it).

Run this only if you need the pool to exist before the worker starts,
e.g. to register deployments while the worker is still offline.
"""
import asyncio

from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.exceptions import ObjectNotFound


async def setup():
    async with get_client() as client:
        try:
            pool = await client.read_work_pool("docker-pool")
            print(f"Work pool 'docker-pool' already exists (type={pool.type})")
            return
        except ObjectNotFound:
            pass

        work_pool = WorkPoolCreate(
            name="docker-pool",
            type="docker",
            description="Docker work pool for on-demand flow execution",
        )
        await client.create_work_pool(work_pool=work_pool)
        print("Work pool 'docker-pool' created successfully!")


if __name__ == "__main__":
    asyncio.run(setup())
