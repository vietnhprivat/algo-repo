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
  schedules/                 # Prefect workflows
  price_forecasting/         # Electricity price forecasting models and evaluation
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
- Flag order convention: area, processtype (if applicable), start, end
- Uses flexible datetime parsing (ISO, compact, human-readable)
- Area tags are case-insensitive

### Tests
- Use fake clients (no real API/DB calls)
- Sample XML fixtures in `conftest.py` as byte literals
- Test pattern: one test class per feature, named `Test<Feature>`
- Always test: return type, row count, schema match, key field values, edge cases

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

# Run CLI
uv run python -m data_cli.main --help

# Run migrations
python -m infrastructure_clickhouse.migrations.run_migrations
```
