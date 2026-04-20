# infrastructure-clickhouse

ClickHouse persistence layer: schema migrations, batch ingest, query functions, structured logging setup, and client factory. All tables use `ReplacingMergeTree` — reads use the `FINAL` keyword, updates use re-insert with a newer `created_utc` (never `UPDATE` or `OPTIMIZE FINAL`).

---

## Tables

| Table | Engine (version key) | Partition | Purpose |
|-------|---------------------|-----------|---------|
| `algo.timeseries` | `ReplacingMergeTree(ingested_utc)` | `toStartOfQuarter(timestamp_utc)` | Raw ENTSOE time-series observations |
| `algo.forecasts` | `ReplacingMergeTree(ingested_utc)` | `toStartOfQuarter(timestamp_utc)` | Day-ahead forecasts (load, generation, wind/solar) |
| `algo.energy_prices` | `ReplacingMergeTree` | `toStartOfQuarter(start_utc)` | ENTSOE energy price auction records |
| `algo.experiment_runs` | `ReplacingMergeTree(created_utc)` | — | One row per forecast/backtest run with metrics |
| `algo.experiment_predictions` | `ReplacingMergeTree` | `toStartOfQuarter(timestamp_utc)` | Per-period predictions and actuals |
| `algo.model_artifacts` | `ReplacingMergeTree(created_utc)` | — | Base64-encoded joblib model blobs |
| `algo.drift_reports` | `ReplacingMergeTree(created_utc)` | `toStartOfQuarter(created_utc)` | Evidently drift detection results |

---

## `ingest.py`

| Function | Writes to | Notes |
|----------|-----------|-------|
| `insert_polars_dataframe(client, df, table_name, batch_size=10_000)` | any | Generic; uses Arrow batching via `client.insert_arrow()` |
| `insert_observations_batch(client, observations)` | `algo.timeseries` | Accepts `list[Observations]` |
| `insert_forecasts_batch(client, forecasts)` | `algo.forecasts` | Accepts `list[Forecast]` |
| `insert_experiment_run(client, run_id, created_utc, experiment_name, area, model_type, config_json, metrics_json, *, training_duration_seconds, data_start_utc, data_end_utc, model_artifact_id)` | `algo.experiment_runs` | Last 4 are keyword-only; default to `0.0 / epoch / epoch / ""` |
| `insert_model_artifact(client, artifact_id, created_utc, run_id, area, model_type, config_name, artifact_blob, artifact_size_bytes)` | `algo.model_artifacts` | `artifact_blob` is base64-encoded joblib bytes (string) |
| `insert_experiment_predictions(client, predictions_df)` | `algo.experiment_predictions` | Schema: `run_id`, `timestamp_utc`, `actual` (Float32), `predicted` (Float32) |
| `insert_drift_report(client, *, report_id, created_utc, area, curve_name, reference_start_utc, reference_end_utc, current_start_utc, current_end_utc, stat_test, drift_score, drift_threshold, drift_detected, reference_n, current_n)` | `algo.drift_reports` | All keyword-only; `drift_detected` stored as UInt8 |

---

## `queries.py`

| Function | Reads from | FINAL | Returns |
|----------|-----------|-------|---------|
| `get_unreconciled_runs(client)` | `algo.experiment_runs` | Yes | `list[dict]` — runs where `metrics_json = '{}'` |
| `get_predictions_for_runs(client, run_ids)` | `algo.experiment_predictions` | Yes | `list[dict]` — `run_id, timestamp_utc, actual, predicted` |
| `get_actual_prices_for_period(client, area, start_utc, end_utc)` | `algo.timeseries` | Yes | `list[dict]` — `timestamp_utc, price`; matches `ENTSOE {area} EnergyPrice %` |
| `load_latest_artifact(client, area, model_type, config_name)` | `algo.model_artifacts` | No | `dict \| None` — most recent artifact blob for the given config |

All queries use parameterized placeholders (no string interpolation). `FINAL` forces deduplication before read on `ReplacingMergeTree` tables.

---

## `logging_setup.py`

Structured logging with optional Loki push. Use in every `schedules/*` and `infrastructure_*` module — never `print()`.

**Get a logger:**

```python
from infrastructure_clickhouse.logging_setup import get_logger, build_log_extra

logger = get_logger(__name__, service="my-service")
```

**Log with context fields:**

```python
logger.info("Inserted batch", extra=build_log_extra(
    area="DK1",
    table_name="algo.timeseries",
    row_count=240,
))
```

`build_log_extra(**kwargs)` filters out `None` and `""` values — pass whatever fields are relevant, extras are silently dropped.

**Supported context fields** (become Loki labels):

```
service, module, area, config_name, target_date, run_id, table_name,
batch_size, status_code, chunk_start, chunk_end, offset, row_count,
batch_count, run_count, response_sets, training_duration_seconds,
total_reconciled, total_skipped
```

**Loki configuration:** set `LOKI_URL` env var (e.g. `http://loki:3100/loki/api/v1/push`). If absent or `python-logging-loki` is not installed, logging falls back to console only.

**Console format:** `%(asctime)s %(levelname)s [%(name)s] %(message)s`

---

## `client_factory.py`

```python
from infrastructure_clickhouse.client_factory import create_client

client = create_client()
# ... use client ...
client.close()
```

| Env var | Default |
|---------|---------|
| `CLICKHOUSE_HOST` | `localhost` |
| `CLICKHOUSE_PORT` | `8123` |
| `CLICKHOUSE_USER` | `default` |
| `CLICKHOUSE_PASSWORD` | `password` |
| `CLICKHOUSE_DATABASE` | `algo` |

Reads `.env` via `python-dotenv`. Returns a `clickhouse_connect` `Client`.

---

## Migrations

Run in sorted order by `run_migrations.py` (auto-discovers `migrations/*.sql`).

| File | What it does |
|------|-------------|
| `001_create_timeseries_table.sql` | Creates `algo.timeseries` |
| `002_create_forecasts_table.sql` | Creates `algo.forecasts` |
| `003_create_experiment_runs_table.sql` | Creates `algo.experiment_runs` |
| `004_create_experiment_predictions_table.sql` | Creates `algo.experiment_predictions` |
| `005_create_model_artifacts_table.sql` | Creates `algo.model_artifacts` (base64 blob storage) |
| `006_alter_experiment_runs_add_columns.sql` | Adds `training_duration_seconds`, `data_start_utc`, `data_end_utc`, `model_artifact_id` to `algo.experiment_runs` |
| `007_create_drift_reports_table.sql` | Creates `algo.drift_reports` |

Never modify existing migration files — add a new numbered file for schema changes.

```bash
uv run python -m infrastructure_clickhouse.migrations.run_migrations
```

---

## Key Patterns

**Upsert via re-insert:** `ReplacingMergeTree(created_utc)` keeps the row with the highest `created_utc` per primary key. To update a row, re-insert it with `created_utc = now()`. Do not use `ALTER TABLE ... UPDATE` or `OPTIMIZE TABLE ... FINAL`.

**Read consistency:** Always use the `FINAL` keyword in SELECT queries on `ReplacingMergeTree` tables to force deduplication before returning results. (`load_latest_artifact` is exempt — it uses `ORDER BY created_utc DESC LIMIT 1`.)

**Arrow batching:** All inserts go through `insert_polars_dataframe`, which calls `client.insert_arrow()` in `batch_size=10_000` row slices. Polars DataFrames are used throughout (not pandas) to match the Arrow wire format.
