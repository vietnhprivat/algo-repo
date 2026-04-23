# algo-repo

Electricity price forecasting platform for European day-ahead markets. Ingests ENTSOE price, load, wind/solar, and generation data into ClickHouse; trains and evaluates **LEAR** (Lasso Estimated AutoRegressive) ensemble models; runs the full lifecycle — scheduling, reconciliation, drift detection, and observability — on a single Docker Compose host.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  docker compose (always running)                                     │
│                                                                      │
│  ┌──────────┐  ┌────────────────┐  ┌──────────────────┐              │
│  │ClickHouse│  │ Prefect Server │  │  Prefect Worker  │              │
│  │ (DB)     │  │ (API + UI)     │  │  (Docker type)   │              │
│  └──────────┘  └────────────────┘  └────────┬─────────┘              │
│                                             │ spawns                 │
│                                    ┌────────▼──────────┐             │
│                                    │  algo-repo:latest │             │
│                                    │  (container)      │             │
│                                    └───────────────────┘             │
│                                                                      │
│  ┌──────────┐  ┌────────────────┐                                    │
│  │  Loki    │  │    Grafana     │                                    │
│  │  (logs)  │  │ (dashboards)   │                                    │
│  └──────────┘  └────────────────┘                                    │
└──────────────────────────────────────────────────────────────────────┘
```

Always-running: ClickHouse, Prefect Server, Prefect Worker, Loki, Grafana.  

---

## Tech Stack

| Software | Role |
|----------|------|
| Python 3.13 + uv | Runtime and package management |
| ClickHouse | Time-series storage, experiment tracking, model artifact blobs |
| Prefect 3.x | Workflow orchestration and scheduling |
| scikit-learn | LEAR model (per-period Lasso regression ensemble) |
| pandas / polars / NumPy | Feature engineering and data manipulation |
| Grafana + Loki | Dashboards (Data Quality, Model Performance, Operational) + structured logging |
| Evidently | In-process data drift detection (KS test, 7-day vs 90-day window) |
| GitHub Actions + Tailscale | CI/CD — rebuild image and redeploy flows on merge to `main` |

---

## Modules

| Module | What it does | Docs |
|--------|-------------|------|
| [src/domain/](src/domain/) | Core domain models: `Area`, `Observations`, `Forecast`, curve naming conventions | [README](src/domain/README.md) |
| [src/infrastructure_entsoe/](src/infrastructure_entsoe/) | ENTSOE Transparency Platform HTTP client — rate-limited, chunked, ZIP + XML parsing | [README](src/infrastructure_entsoe/README.md) |
| [src/infrastructure_clickhouse/](src/infrastructure_clickhouse/) | ClickHouse schema, ingest functions, query functions, logging setup, migrations | [README](src/infrastructure_clickhouse/README.md) |
| [src/data_cli/](src/data_cli/) | Typer CLI for historical backfills (price, load, generation, wind/solar) | [README](src/data_cli/README.md) |
| [src/forecast_cli/](src/forecast_cli/) | Typer CLI for backtests and live predictions; ClickHouse tracking via `--track` | [README](src/forecast_cli/README.md) |
| [src/price_forecasting/](src/price_forecasting/) | LEAR model, multi-window ensemble backtesting engine, evaluation metrics | [README](src/price_forecasting/README.md) |
| [src/schedules/](src/schedules/) | Prefect flows: ingestion, forecast, reconciliation, drift detection + deployment scripts | [README](src/schedules/README.md) |

---

## Scheduled Pipelines

| Flow | Cron (UTC) | Purpose |
|------|-----------|---------|
| `entsoe-backfill` (×7 areas) | `0 * * * *` | Ingest prices, load, wind/solar, generation for last 48h |
| `daily-forecast` | `0 6 * * *` | Train LEAR ensemble, store tomorrow's prediction |
| `reconcile-predictions` | `0 18 * * *` | Backfill actual prices, compute live MAE/RMSE/sMAPE |
| `drift-detection` | `0 19 * * *` | Evidently KS-test on current vs reference price distribution |

---

## Quickstart

```bash
# 1. Configure credentials
cp .env .env.local   # edit with your values
# Required vars: ENTSOE_API_KEY, CLICKHOUSE_USER, CLICKHOUSE_PASSWORD,
#                GRAFANA_ADMIN_USER, GRAFANA_ADMIN_PASSWORD

# 2. Build and start
docker build -t algo-repo:latest .
docker compose up -d

# 3. Run migrations (001–007)
uv run python -m infrastructure_clickhouse.migrations.run_migrations

# 4. Register Prefect deployments
export PREFECT_API_URL="http://localhost:4200/api"
uv run python src/schedules/src/schedules/deploy_ingestion.py
uv run python src/schedules/src/schedules/deploy_forecast.py
```

**Prefect UI:** http://localhost:4200  
**Grafana:** http://localhost:3000

Full setup, CI/CD configuration, and troubleshooting: [DEPLOYMENT.md](DEPLOYMENT.md)

---

## Key Commands

```bash
# Tests
python -m pytest tests/ -v

# Backfill historical data
uv run python -m data_cli.main entsoe backfill price-document -a DK1 -s 2024-01-01 -e 2025-01-01
uv run python -m data_cli.main entsoe backfill total-load -a DK1 -s 2024-01-01 -e 2025-01-01

# Run backtest / live prediction
uv run python -m forecast_cli.main backtest dk1_lear --track
uv run python -m forecast_cli.main predict dk1_lear -d 2026-03-22 --track

# Trigger flows manually
python -c "from schedules.forecast import daily_forecast_flow; daily_forecast_flow(config_name='dk1_lear')"
python -c "from schedules.reconciliation import reconcile_predictions_flow; reconcile_predictions_flow()"
python -c "from schedules.drift import drift_detection_flow; drift_detection_flow(area='DK1')"

# Run migrations
uv run python -m infrastructure_clickhouse.migrations.run_migrations
```
