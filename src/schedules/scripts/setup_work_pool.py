#!/usr/bin/env python
"""Create Docker work pool for Prefect."""
from prefect.client.orchestration import get_client
from prefect.client.schemas.actions import WorkPoolCreate
from prefect.exceptions import ObjectNotFound
import asyncio

async def create_work_pool():
    async with get_client() as client:
        try:
            # Check if pool exists
            existing_pool = await client.read_work_pool("docker-pool")
            print("Deleting existing work pool 'docker-pool' to recreate with correct config...")
            await client.delete_work_pool("docker-pool")
        except ObjectNotFound:
            pass
        
        # Create the work pool with proper Docker base job template
        base_job_template = {
            "job_configuration": {
                "image": "{{ image }}",
                "network_mode": "{{ network_mode }}",
                "auto_remove": "{{ auto_remove }}",
                "command": "{{ command }}",
                "env": "{{ env }}",
                "labels": "{{ labels }}",
                "name": "{{ name }}",
            },
            "variables": {
                "type": "object",
                "properties": {
                    "image": {
                        "type": "string",
                        "title": "Image",
                        "description": "Docker image to use",
                    },
                    "image_pull_policy": {
                        "type": "string",
                        "title": "Image Pull Policy",
                        "description": "Policy for pulling the image",
                        "default": "IfNotPresent",
                        "enum": ["Always", "IfNotPresent", "Never"],
                    },
                    "network_mode": {
                        "type": "string",
                        "title": "Network Mode",
                        "description": "Network mode for the container",
                    },
                    "auto_remove": {
                        "type": "boolean",
                        "title": "Auto Remove",
                        "description": "Remove container after completion",
                        "default": True,
                    },
                },
                "required": ["image"],
            },
        }
        
        work_pool = WorkPoolCreate(
            name="docker-pool",
            type="docker",
            description="Docker work pool for on-demand flow execution",
            base_job_template=base_job_template,
        )
        await client.create_work_pool(work_pool=work_pool)
        print("Work pool 'docker-pool' created successfully with Docker template")

if __name__ == "__main__":
    asyncio.run(create_work_pool())
