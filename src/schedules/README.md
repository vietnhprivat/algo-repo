# schedules

Prefect workflows for scheduled data ingestion and forecasting.

---

## Architecture

```
schedules/
├── src/schedules/
│   ├── ingestion.py        # ENTSOE backfill flow (4 data types, parameterized by area)
│   ├── deploy_ingestion.py # Deployment script — one deployment per area
│   └── forecast.py         # Forecast flow (placeholder)
└── scripts/
    └── setup_work_pool.py  # One-time: create the Docker work pool
```

### Key design principle

The flow itself contains **no fetch/insert logic**. It delegates to the shared service layer in `data_cli.entsoe.services`. This means both the CLI and Prefect flows use exactly the same code path:

```
data_cli.entsoe.services   ← shared: fetch + insert logic
       ↑                ↑
data_cli/backfill.py    schedules/ingestion.py
(Typer UX)              (Prefect task/flow wrappers)
```

---

## Flows

### `entsoe_backfill_flow(area: str = "DK1")`

Ingests all four ENTSOE data types for a given area over the last **48 hours**:

| Task | Data type | ClickHouse table |
|---|---|---|
| `ingest_energy_prices_task` | Day-ahead prices (A44) | `algo.timeseries` |
| `ingest_total_load_task` | Total load forecast (A65) | `algo.forecasts` |
| `ingest_generation_forecast_task` | Generation forecast (A71) | `algo.forecasts` |
| `ingest_wind_solar_task` | Wind/solar forecast (A69) | `algo.forecasts` |

Each task has `retries=2, retry_delay_seconds=60`. Tasks run sequentially to respect the ENTSOE rate limit (400 calls/60s shared across all calls). If one task fails after retries, the others still run.

The `LOOKBACK_HOURS = 48` constant in `ingestion.py` controls the window. Overlapping runs are safe — ClickHouse uses `ReplacingMergeTree` and deduplicates.

---

## Setup (one-time)

```bash
# 1. Create the Docker work pool in Prefect
PREFECT_API_URL="http://localhost:4200/api" uv run python scripts/setup_work_pool.py
```

---

## Deploying a schedule

Each deployment is one area + one cron schedule. Deploy from the repo root (scripts auto-load `.env`):

```bash
PREFECT_API_URL="http://localhost:4200/api" uv run python src/schedules/src/schedules/deploy_ingestion.py
```

This deploys `entsoe-backfill-dk1` running hourly for DK1.

### Adding a new area

In [deploy_ingestion.py](src/schedules/deploy_ingestion.py), add a second deployment at the bottom:

```python
if __name__ == "__main__":
    # Existing DK1 deployment
    EntsoeIngestionFlowDeployment(
        name="entsoe-backfill-dk1",
        ...
        parameters={"area": "DK1"},
    ).deploy()

    # New DE deployment
    EntsoeIngestionFlowDeployment(
        name="entsoe-backfill-de",
        work_pool_name="docker-pool",
        image="algo-repo:latest",
        cron="0 * * * *",
        flow=entsoe_backfill_flow,
        parameters={"area": "DE"},
    ).deploy()
```

Run the script again to register the new deployment. No flow code changes needed.

Valid area tags come from `domain.areas` (e.g. `DK1`, `DK2`, `DE`, `NO`, `SE`).

### Changing the cron schedule

Change the `cron` string in the `EntsoeIngestionFlowDeployment` constructor and re-run `deploy_ingestion.py`. Standard cron syntax — `"0 * * * *"` is hourly, `"0 6 * * *"` is daily at 06:00 UTC.

### Changing the lookback window

Edit `LOOKBACK_HOURS` in [ingestion.py](src/schedules/ingestion.py):

```python
LOOKBACK_HOURS = 48  # change this
```

Increasing this means each run fetches more history. Overlapping data is safe to re-ingest.

---

## Adding a new data type

1. Add a service function to `data_cli/entsoe/services.py` following the existing pattern.
2. Add a `@task` wrapper in `ingestion.py`.
3. Call the new task inside `entsoe_backfill_flow`.

No deployment changes needed — the existing deployments will pick up the new task on the next run after code is rebuilt into the Docker image.

---

## Running a flow manually

```bash
# Trigger a one-off run locally (no Prefect server needed)
python -c "from schedules.ingestion import entsoe_backfill_flow; entsoe_backfill_flow(area='DK1')"

# Trigger from Prefect UI / CLI after deploying
prefect deployment run 'entsoe-backfill/entsoe-backfill-dk1'
```

---

## Environment variables

All credentials are baked into the deployment via `deploy_ingestion.py` (read from `.env` on the host at deploy time):

| Variable | Description |
|---|---|
| `ENTSOE_API_KEY` | ENTSOE Transparency Platform API key |
| `CLICKHOUSE_HOST` | ClickHouse hostname (default: `clickhouse`) |
| `CLICKHOUSE_PORT` | ClickHouse HTTP port (default: `8123`) |
| `CLICKHOUSE_USER` | ClickHouse user |
| `CLICKHOUSE_PASSWORD` | ClickHouse password |
