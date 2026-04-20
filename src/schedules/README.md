# schedules

Prefect workflows for ingestion, forecasting, reconciliation, and drift detection. Four pipelines run on staggered daily/hourly crons; all business logic is delegated to service layers — tasks are thin orchestration wrappers.

---

## Flows

| Flow | Function | Cron (UTC) | Purpose |
|------|----------|-----------|---------|
| `entsoe-backfill` | `entsoe_backfill_flow(area)` | `0 * * * *` | Ingest all 4 ENTSOE data types for one area (last 48h + next 24h) |
| `daily-forecast` | `daily_forecast_flow(config_name, target_date)` | `0 6 * * *` | Train LEAR ensemble and store tomorrow's price prediction |
| `reconcile-predictions` | `reconcile_predictions_flow()` | `0 18 * * *` | Backfill actual prices into predictions; compute live MAE/RMSE/sMAPE |
| `drift-detection` | `drift_detection_flow(area)` | `0 19 * * *` | Evidently KS-test: 7-day current vs 90-day reference window |

**Schedule rationale:** ENTSOE publishes day-ahead actuals ~14:00 UTC. Reconciliation at 18:00 gives a 4-hour margin. Drift at 19:00 runs after reconciliation completes.

---

## Tasks

### `entsoe_backfill_flow`

| Task | Retries | Delegates to |
|------|---------|-------------|
| `ingest_energy_prices_task` | 2 × 60s | `data_cli.entsoe.services.backfill_energy_prices` |
| `ingest_total_load_task` | 2 × 60s | `data_cli.entsoe.services.backfill_total_load` |
| `ingest_generation_forecast_task` | 2 × 60s | `data_cli.entsoe.services.backfill_generation_forecast` |
| `ingest_wind_solar_task` | 2 × 60s | `data_cli.entsoe.services.backfill_wind_solar` |

Tasks run sequentially (ENTSOE rate limit: 400 calls/60s shared). One failed task does not abort the others.

### `daily_forecast_flow`

| Task | Retries | Delegates to |
|------|---------|-------------|
| `load_config_task` | none (fail fast) | `forecast_cli.config_loader.load_config` |
| `predict_task` | 2 × 60s | `price_forecasting.LiveRunner.run_live_with_metadata` |
| `track_prediction_task` | none (fail visible) | `forecast_cli.tracking.track_prediction` |

`target_date` defaults to tomorrow (`now + 1 day`) if not provided.

### `reconcile_predictions_flow`

| Task | Retries | What it does |
|------|---------|-------------|
| `find_unreconciled_runs_task` | none | Fetches runs where `metrics_json = '{}'` |
| `reconcile_area_task(area, runs)` | 2 × 60s | One predictions query + one actuals query per area (no N+1); re-inserts with actuals and computed metrics |

Runs are all-or-nothing: if any timestamp lacks an actual, the whole run is skipped (retried next day). Update via re-insert with newer `created_utc` — `ReplacingMergeTree` keeps the winning row. Never `UPDATE` or `OPTIMIZE FINAL` on writes.

### `drift_detection_flow`

| Task | Retries | What it does |
|------|---------|-------------|
| `detect_drift_for_area_task(area)` | 2 × 60s | Fetches current + reference windows; runs Evidently `DataDriftPreset`; inserts report to `algo.drift_reports`; logs WARNING if drift detected |

Minimum 30 samples per window required. Skips and returns `status: "skipped_insufficient_samples"` otherwise.

---

## Service-Layer Delegation

```
data_cli.entsoe.services   ←─── ingestion.py   (fetch + insert ENTSOE data)
price_forecasting          ←─── forecast.py    (LiveRunner, ExperimentConfig)
forecast_cli               ←─── forecast.py    (load_config, track_prediction)
infrastructure_clickhouse  ←─── reconciliation.py, drift.py  (queries + ingest)
price_forecasting.evaluation ←─ reconciliation.py  (calculate_mae/rmse/smape)
evidently                  ←─── drift.py       (DataDriftPreset)
```

Flows and tasks contain no fetch/insert/ML logic — they orchestrate and handle retries.

---

## Deployment Scripts

### `deploy_ingestion.py`

Registers one deployment per area in `AREAS`:

```python
AREAS = ["DK1", "DK2", "NL", "BE", "DE", "FR", "PL"]
```

Each deployment: `entsoe-ingestion/ingestion-hourly-{area}`, cron `0 * * * *`.

**Add a new area:** append its tag to `AREAS` and rerun the script. No flow code changes needed.

### `deploy_forecast.py`

Registers deployments for three flows:

```python
FORECAST_CONFIGS = ["dk1_lear"]   # one daily-forecast deployment per config
DRIFT_AREAS = ["DK1"]              # one drift-detection deployment per area
```

| Deployment name | Flow | Cron |
|----------------|------|------|
| `daily-forecast/daily-forecast-{config}` | `daily_forecast_flow` | `0 6 * * *` |
| `reconcile-predictions/reconcile-predictions` | `reconcile_predictions_flow` | `0 18 * * *` |
| `drift-detection/drift-detection-{area}` | `drift_detection_flow` | `0 19 * * *` |

**Add a new forecast config:** append to `FORECAST_CONFIGS` and rerun. The `configs/` directory is volume-mounted at `/app/configs` — no Docker image rebuild needed for config changes.

**Add a new drift area:** append to `DRIFT_AREAS` and rerun.

**Deploy:**

```bash
export PREFECT_API_URL="http://localhost:4200/api"
uv run python src/schedules/src/schedules/deploy_ingestion.py
uv run python src/schedules/src/schedules/deploy_forecast.py
```

Both scripts are idempotent.

---

## Environment Variables

| Variable | Default | Used by |
|----------|---------|---------|
| `ENTSOE_API_KEY` | — (required) | ingestion |
| `CLICKHOUSE_HOST` | `clickhouse` | all flows |
| `CLICKHOUSE_PORT` | `8123` | all flows |
| `CLICKHOUSE_USER` | `default` | all flows |
| `CLICKHOUSE_PASSWORD` | `password` | all flows |
| `CLICKHOUSE_DATABASE` | `algo` | all flows |
| `LOKI_URL` | `http://loki:3100/loki/api/v1/push` | all flows |
| `PREFECT_API_URL` | `http://server:4200/api` | all flows (in container) |

Credentials are read from `.env` at deploy time and baked into Docker job variables. `LOKI_URL` is optional — logging falls back to console if absent.

---

## Manual Triggers

```bash
# Run without Prefect server (local)
python -c "from schedules.ingestion import entsoe_backfill_flow; entsoe_backfill_flow(area='DK1')"
python -c "from schedules.forecast import daily_forecast_flow; daily_forecast_flow(config_name='dk1_lear')"
python -c "from schedules.reconciliation import reconcile_predictions_flow; reconcile_predictions_flow()"
python -c "from schedules.drift import drift_detection_flow; drift_detection_flow(area='DK1')"

# Trigger via Prefect CLI (server must be running)
PREFECT_API_URL="http://localhost:4200/api" prefect deployment run "entsoe-ingestion/ingestion-hourly-DK1"
PREFECT_API_URL="http://localhost:4200/api" prefect deployment run "daily-forecast/daily-forecast-dk1_lear"
PREFECT_API_URL="http://localhost:4200/api" prefect deployment run "reconcile-predictions/reconcile-predictions"
PREFECT_API_URL="http://localhost:4200/api" prefect deployment run "drift-detection/drift-detection-DK1"
```

---

## Adding a New Data Type (ingestion)

1. Add a service function to `data_cli/entsoe/services.py`.
2. Add a `@task` wrapper in `ingestion.py`.
3. Call the new task inside `entsoe_backfill_flow`.

No deployment changes needed — existing deployments pick up the new task on the next image rebuild.
