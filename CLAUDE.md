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
- `Observations` for time-series data, `Forecast` for forecast data, `EnergyPriceObservation` for energy prices
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

# Force ClickHouse deduplication (run in ClickHouse client)
# OPTIMIZE TABLE algo.timeseries FINAL;
# OPTIMIZE TABLE algo.forecasts FINAL;
```
