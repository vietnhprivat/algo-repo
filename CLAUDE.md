# CLAUDE.md

## Project Overview

Energy market data platform: fetches data from external APIs (ENTSOE), maps to domain models, stores in ClickHouse, and runs electricity price forecasting models.

## Project Structure

```
src/
  domain/                    # Core domain models (areas, curves). No external dependencies.
  infrastructure_entsoe/     # ENTSOE API client, XML mappers, type enums
  infrastructure_clickhouse/ # ClickHouse client, migrations, ingestion
  data_cli/                  # Typer CLI for backfilling data
  forecast_cli/              # Typer CLI for running backtests and live predictions
  schedules/                 # Prefect workflows
  price_forecasting/         # Electricity price forecasting models and evaluation
    backtesting/             # BacktestEngine, BacktestRunner, splitting logic
    evaluation/              # Metrics (MAE, RMSE, sMAPE, rMAE) and summary functions
    models/                  # LEAR, DNN, BaseModel, model registry
    configs/                 # ExperimentConfig dataclass
    data/                    # ClickHouse loader and preprocessor
    live_runner.py           # LiveRunner for single-date predictions
configs/                     # Python config files for forecast-cli experiments (git-tracked)
tests/                       # Mirrors src/ structure
```

## Key Conventions

### Domain Models
- Use Polars DataFrames with strictly enforced schemas (`enforce_schema()` in `curves.py`)
- `Observations` for time-series data, `Forecast` for forecast data
- Curve names use **spaces** as separators: `ENTSOE DK1 TotalLoad Dayahead` (not dots)
- Area definitions live in `areas.py` as frozen dataclasses with lookup dicts

### Infrastructure
- **ENTSOE client**: rate-limited (400 calls/60s), handles both ZIP and raw XML responses
- **XML mappers**: each data type gets its own parser function returning domain model lists
- **ClickHouse migrations**: numbered SQL files (`001_*.sql`, `002_*.sql`) in `migrations/`, auto-discovered by `run_migrations.py` via sorted glob
- **Ingest functions**: one per domain model, use `insert_polars_dataframe()` with Arrow batching

### CLI (data_cli)
- Built with Typer, structured as `data-cli <source> backfill <command>`
- Flag order convention: **always use named flags** (`-a`, `-s`, `-e`) — area is not positional
- Uses flexible datetime parsing (ISO, compact, human-readable)
- Area tags are case-insensitive

### Schedules (Prefect)
- **Shared service layer**: `data_cli.entsoe.services` holds the core fetch + insert logic — no Typer dependency. Both the CLI (`backfill.py`) and Prefect (`ingestion.py`) import from it. Never duplicate fetch/insert logic in the flow.
- **Parameterized flows**: one flow definition (`entsoe_backfill_flow(area: str)`), one deployment per area. Add a new area by adding a new `EntsoeIngestionFlowDeployment(parameters={"area": "XX"})` in `deploy_ingestion.py` and re-running it — no flow code changes.
- **Task granularity**: one task per data type (`ingest_energy_prices_task`, etc.), tasks run sequentially to respect ENTSOE rate limits. Task-level retries (`retries=2`) mean one failure doesn't abort the others.
- **Lookback window**: `LOOKBACK_HOURS = 48` in `ingestion.py`. Re-ingesting overlapping data is always safe — ClickHouse `ReplacingMergeTree` deduplicates.
- **Deploying**: `PREFECT_API_URL="http://localhost:4200/api" uv run python src/schedules/src/schedules/deploy_ingestion.py`
- **Forecast deployments** live in `deploy_forecast.py`: `daily-forecast-<config>` (06:00 UTC), `reconcile-predictions` (18:00 UTC), `drift-detection-<area>` (19:00 UTC). All reuse the generic `ForecastFlowDeployment` class — add a new config by appending to `FORECAST_CONFIGS` and rerunning the script.
- **Config mounting**: `deploy_forecast.py` mounts `configs/` as a Docker volume at `/app/configs` so a config change does not require rebuilding the image. `config_loader.py` resolves paths accordingly.

### Model Lifecycle & Tracking
- **Model artifacts** are stored in `algo.model_artifacts` as base64-encoded joblib blobs (see migration `005`). Do not add a filesystem model store. Load the latest artifact via `load_latest_artifact(area, model_type, config_name)` in `infrastructure_clickhouse.queries`.
- **Live prediction metadata**: `LiveRunner.run_live_with_metadata()` returns a `LiveResult` dataclass with `prediction`, `data_start_utc`, `data_end_utc`, `training_duration_seconds`, and `trained_models`. `forecast_cli.tracking.track_prediction()` serializes the trained ensemble, inserts the artifact row, and links `model_artifact_id` on the experiment run.
- **Experiment run columns** (migration `006`): `training_duration_seconds`, `data_start_utc`, `data_end_utc`, `model_artifact_id`. Populate them via the keyword-only params of `insert_experiment_run()`.
- **Reconciliation** (`schedules/reconciliation.py`): fetches all unreconciled runs, batches queries **per area** (one predictions query + one actuals query — never N+1), skips any run with a missing hour (retried the next day), and updates via **re-insert with newer `created_utc`** so `ReplacingMergeTree` keeps the new row. Never use `UPDATE` or `OPTIMIZE FINAL` — reads use the `FINAL` keyword.
- **Metrics on live predictions**: computed from flat `np.ndarray`s via `calculate_mae/rmse/smape`, not the wide-format `compute_metrics_summary()` (which is backtest-oriented).

### Observability
- **Structured logging via Loki**: use the handler configured in `infrastructure_clickhouse.logging_setup`. Never `print()` in `schedules/*` or `infrastructure_*` — use the module logger with `build_log_extra(**context)` so fields reach Loki as labels.
- **Grafana dashboards** auto-provision from `grafana/provisioning/` and `grafana/dashboards/`. Three dashboards: Data Quality, Model Performance, Operational (Loki log stream). Adding a panel = editing the JSON file in `grafana/dashboards/` (do not edit through the UI — changes will be overwritten on restart).
- **Drift detection** (`schedules/drift.py`): Evidently runs **in-process** inside the Prefect flow, no Evidently service. Reference window = 90 days, current window = 7 days. Results land in `algo.drift_reports` (migration `007`); a drift event emits a WARNING to Loki.

### Alerting
- **Slack notifications** via `SLACK_WEBHOOK_URL`. Helper `schedules.alerting.notify(subject, message, severity)` no-ops if the var is unset, so local dev never fails.
- **Drift** posts a warning + triggers retrain when `retrain_on_drift=True` on the config (migration 009 records each event in `algo.retrain_events`).
- **Accuracy degradation**: `reconciliation._maybe_alert_accuracy_degradation` alerts when today's MAE > 1.5× the 30-day median.
- **Grafana alert rules** file-based in `grafana/provisioning/alerting/rules.yaml`: data-staleness, drift-detected-today, reconciliation-missed. Never edit via the UI.

### Hyperparameter tuning
- `uv run python -m forecast_cli.main tune <config>` runs Optuna TPE with the search space from `price_forecasting.tuning.dnn_search` (Lago §4.3.3: 10 binary feature/selector + 8 architecture HPs). Trials persist to `algo.hyperparam_trials` (migration `008`). Config must declare `val_start_date` and `val_end_date`.
- After tuning, paste the best params into the config's `model_params` dict and commit. The objective filters Optuna keys the model class doesn't accept (`use_price_d_*`, `use_exog_*`, `preprocessing`, `init_method`); only architecture HPs reach the model.
- DNN serving averages `n_dnn_ensemble` replicates with distinct random seeds (Lago §4.4).

### CI/CD
- **PR workflows**: `pr_test.yml` runs pytest, `pr_ruff-lint.yaml` runs ruff. The LEAR smoke test (`tests/price_forecasting/test_smoke.py`) is picked up automatically.
- **CD workflow**: `cd_deploy.yml` fires on merge to `main`, joins the tailnet via the Tailscale GitHub Action, SSHes into the deploy host, rebuilds `algo-repo:latest`, reruns both `deploy_*.py` scripts, then triggers `daily-forecast/daily-forecast-dk1_lear` and polls until it completes. One-time setup is in `DEPLOYMENT.md`.

### CLI (forecast_cli)
- Typer app with two commands: `backtest <config_name>` and `predict <config_name> -d <date>`
- Config files live in `configs/` (Python files), loaded via `importlib` — full IDE support
- `--track` flag stores results in ClickHouse (`algo.experiment_runs`, `algo.experiment_predictions`)
- Config name is the filename without `.py` (e.g. `dk1_lear` → `configs/dk1_lear.py`)

### Price Forecasting
- **ExperimentConfig**: prefer `test_start_date` / `test_end_date` over ratio-based splitting — reproducible, comparable across runs, no mental math. Ratios remain as fallback.
- **Resolution-aware pipeline**: data can be hourly (24 periods/day) or 15-min (96 periods/day). Never hardcode `24` — use `n_periods = targets.shape[1]` or `_detect_n_periods()` from the preprocessor.
- **Circular imports**: internal submodules must NOT import from top-level `price_forecasting` (its `__init__.py` imports them). Use subpackage-level imports: `from price_forecasting.configs import X`, `from price_forecasting.evaluation import X`.
- **Re-export `__init__.py` files**: use `X as X` syntax to satisfy ruff F401. e.g. `from pkg.module import Foo as Foo`.
- **ClickHouse deduplication**: `ReplacingMergeTree` deduplicates lazily — always call `drop_duplicates(subset=["timestamp_utc"], keep="last")` after loading from `algo.timeseries` and `algo.forecasts`. Force immediate dedup with `OPTIMIZE TABLE algo.timeseries FINAL`.
- **Experiment tracking**: `algo.experiment_runs` (one row per run) and `algo.experiment_predictions` (one row per period per day). Use `insert_experiment_run()` and `insert_experiment_predictions()` from `infrastructure_clickhouse.ingest`.

### Feature Engineering (price_forecasting/data/)
- **FeatureTransformer pipeline**: `DataPreprocessor` applies a list of `FeatureTransformer` objects in order. Each transformer gets `(hourly_df, daily_prices_df) -> pd.DataFrame`. Results are `pd.concat`'d column-wise. Override via `ExperimentConfig.feature_transformers`.
- **LEAR defaults**: `default_transformers_for_model(exogenous_columns)` returns `[PriceLagTransformer, ExogenousLagTransformer, CalendarDummyTransformer]` — bit-identical to the research paper. Never change these defaults; add new transformers alongside them.
- **Feature explosion**: adding an exogenous curve adds `3 × n_periods` columns (d0, d-1, d-7 lags). Formula: `4×24 + n_exog×3×24 + 7 = 103 + 72k` for hourly. This is by design for LEAR (Lasso handles the explosion). For deep models, use `MeanWeeklyForecastTransformer` or `CyclicalTimeTransformer` instead to keep dimensionality low.
- **Cyclical encoding**: `CyclicalTimeTransformer` encodes annual seasonality as `sin/cos(2π × dayofyear / 365.25)` — 2 columns instead of 365. Use for models that benefit from smooth temporal features. Not in LEAR defaults (calendar dummies are sufficient for Lasso).
- **Circular import between transformers and preprocessor**: `transformers.py` imports `pivot_to_daily` from `preprocessor.py`. `preprocessor.py` must import `default_transformers_for_model` as a **lazy local import** inside `__init__` to avoid the circular dependency.

### Tests
- Use fake clients (no real API/DB calls)
- Sample XML fixtures in `conftest.py` as byte literals
- Test pattern: one test class per feature, named `Test<Feature>`
- Always test: return type, row count, schema match, key field values, edge cases
- Never hardcode period counts like `24` in assertions — derive from `targets.shape[1]` or a class-level `N_PERIODS` constant

## Development Workflow

### When planning
- Explore the existing codebase before proposing changes — find patterns to reuse
- Ask clarifying questions about field mappings, naming conventions, and data semantics rather than assuming
- Confirm understanding of the task before implementing

### When implementing
- Follow existing patterns in the codebase — mirror the structure of similar features
- Reuse helper functions (e.g., `_map_A03_curve`, `get_required_text`, `_map_resolution_to_timedelta`)
- Keep domain models minimal — only include fields that are actually needed
- Add migrations as new numbered SQL files, never modify existing ones
- Update ingest.py and queries.py when adding new tables/models

### When testing
- Run the full test suite: `python -m pytest tests/ -v`
- Ensure all existing tests still pass after changes
- Write tests that cover: happy path, schema validation, edge cases, error handling

## Commands

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test module
python -m pytest tests/infrastructure_entsoe/ -v

# Backfill data (note: area is a named flag -a, not positional)
uv run python -m data_cli.main entsoe backfill price-document -a DK1 -s 2023-01-01 -e 2026-03-22
uv run python -m data_cli.main entsoe backfill total-load -a DK1 -s 2023-01-01 -e 2026-03-22

# Run forecast CLI
uv run python -m forecast_cli.main backtest dk1_lear
uv run python -m forecast_cli.main predict dk1_lear -d 2026-03-22
uv run python -m forecast_cli.main backtest dk1_lear --track

# Run migrations
python -m infrastructure_clickhouse.migrations.run_migrations

# Deploy Prefect ingestion schedule
PREFECT_API_URL="http://localhost:4200/api" uv run python src/schedules/src/schedules/deploy_ingestion.py

# Deploy forecast / reconciliation / drift deployments
PREFECT_API_URL="http://localhost:4200/api" uv run python src/schedules/src/schedules/deploy_forecast.py

# Trigger a flow run manually (no Prefect server needed)
python -c "from schedules.ingestion import entsoe_backfill_flow; entsoe_backfill_flow(area='DK1')"
python -c "from schedules.forecast import daily_forecast_flow; daily_forecast_flow(config_name='dk1_lear')"
python -c "from schedules.reconciliation import reconcile_predictions_flow; reconcile_predictions_flow()"
python -c "from schedules.drift import drift_detection_flow; drift_detection_flow(area='DK1')"

# Force ClickHouse deduplication (run in ClickHouse client)
# OPTIMIZE TABLE algo.timeseries FINAL;
# OPTIMIZE TABLE algo.forecasts FINAL;
```
