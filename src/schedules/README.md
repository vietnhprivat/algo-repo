# Schedules Module

This module contains Prefect flows and deployment scripts for scheduled data ingestion tasks.

## Structure

```
schedules/
├── scripts/           # Deployment and setup scripts
│   ├── setup_work_pool.py     # Create Prefect work pool (one-time)
│   └── deploy_ingestion.py    # Deploy/update ingestion flow
└── src/schedules/     # Flow definitions
    ├── ingestion.py   # ENTSOE energy price ingestion flow
    └── ...
```

## Usage

See the main [DEPLOYMENT.md](../../DEPLOYMENT.md) for complete setup instructions.

Quick reference (scripts auto-load `.env`):
```bash
# One-time: Create work pool
PREFECT_API_URL="http://localhost:4200/api" uv run python scripts/setup_work_pool.py

# Deploy flows
PREFECT_API_URL="http://localhost:4200/api" uv run python scripts/deploy_ingestion.py
```
