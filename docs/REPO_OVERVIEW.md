# algo-repo — LLM Context Primer

> **Purpose of this file.** Single-source orientation for Claude (and other LLM
> agents) so a future session can answer most questions and plan most tasks
> **without** reading the full codebase. Skim this top-to-bottom before
> diving into source files. Update it whenever a major subsystem changes
> (see "Update Protocol" at the bottom).
>
> **What this is NOT.** It is not a replacement for `CLAUDE.md` (project
> conventions / hard rules) or `DEPLOYMENT.md` (ops runbook). It is a deep
> **reference** about *what exists and how it fits together*.
>
> Last refreshed against commit `2d5989a` (May 2026, PR #67 — MLOps & EPF research fidelity).

---

## 1. One-paragraph summary

`algo-repo` is an electricity-price forecasting platform for European
day-ahead markets. It (1) ingests ENTSO-E Transparency Platform data (prices,
load, generation, wind/solar) into ClickHouse, (2) trains and evaluates
forecasting models — primarily a **LEAR** (Lasso Estimated AutoRegressive)
ensemble — across calibration windows, with an Optuna-tunable DNN path
that averages a seed-varied ensemble, (3) runs the full production
lifecycle: scheduled ingestion, daily live forecasts, day-after
reconciliation against published actuals, Evidently-based drift detection
and a drift-triggered retraining flow, plus Slack alerts on degraded
accuracy or detected drift. Everything runs in Docker Compose on a single
host; Prefect orchestrates the flows; Grafana + Loki provide observability
(with file-provisioned alert rules); GitHub Actions + Tailscale handle
CI/CD.

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  docker compose (always running on the host)                         │
│                                                                      │
│  ┌──────────┐  ┌────────────────┐  ┌──────────────────┐              │
│  │ClickHouse│  │ Prefect Server │  │  Prefect Worker  │              │
│  │  algo DB │  │ (API + UI)     │  │  (docker-pool)   │              │
│  └──────────┘  └────────────────┘  └────────┬─────────┘              │
│       ▲              ▲                       │ spawns per flow run   │
│       │              │              ┌────────▼──────────┐            │
│       │              │              │  algo-repo:latest │            │
│       │              │              │  ephemeral        │            │
│       │              │              │  container        │            │
│       │              │              └─┬─────────────────┘            │
│       │              │                │ reads CH, calls ENTSOE,      │
│       │              │                │ writes CH + Loki             │
│  ┌────┴─────┐  ┌─────┴────────┐       │                              │
│  │  Loki    │◄─┤    Grafana   │       │                              │
│  │  (logs)  │  │ (dashboards) │       │                              │
│  └──────────┘  └──────────────┘       │                              │
└──────────────────────────────────────────────────────────────────────┘
```

**Data plane.**

```
ENTSO-E  ─►  fetch_*_forecasts()  ─►  mappers → Observations / Forecast
                                                     │
                                                     ▼
                                    insert_*_batch() → algo.timeseries
                                                       algo.forecasts
                                                          │
                  ┌───────────────────────────────────────┘
                  ▼
   load_dataset() → DataPreprocessor → FeatureTransformers → wide matrix
                                                                │
                                                                ▼
                           BacktestEngine (per-window train → ensemble mean)
                                                                │
                                       ┌────────────────────────┴───────────┐
                                       ▼                                    ▼
                        algo.experiment_runs / _predictions         model_artifacts
                                       │
              ┌────────────────────────┴──────────────────┐
              ▼                                           ▼
   reconciliation (next day → metrics)        drift detection (KS vs 90-day window)
              │                                           │
              │  MAE > 1.5× 30-day median?                │  retrain_on_drift=True?
              ▼                                           ▼
   Slack notify (degradation)            triggered_retrain_flow ──► algo.retrain_events
              │                                           │
              └──► algo.experiment_runs (metrics_json)    └──► algo.drift_reports
                                                              └──► Slack notify (drift)
```

Optuna TPE tuning (`forecast-cli tune <config>`) is an offline branch off
the data plane: it loads the same dataset, evaluates DNN candidates over a
validation window, and persists trials to `algo.hyperparam_trials`. Best
params are pasted into the config and the daily-forecast deployment picks
them up on next run.

---

## 3. Tech stack

| Layer | Choice | Notes |
|-------|--------|-------|
| Python | 3.13 | `requires-python = ">=3.13"`, `.python-version` set |
| Package manager | `uv` workspace | 7 workspace members under `src/` |
| DB / OLAP | ClickHouse 25.6 | `algo` database, `ReplacingMergeTree` engines |
| Orchestrator | Prefect 3.x | Docker work pool, ephemeral flow containers |
| ML — baseline | scikit-learn (`Lasso`, `LassoCV`) | One Lasso per period (24 or 96) |
| ML — DNN | PyTorch + Lightning | `LightningModel` base for DNN/Transformer work; seed-varied ensemble averaging in `LiveRunner` |
| ML — boosted | XGBoost | Wrapped via `GBTModel` |
| ML — tuning | Optuna 4.x (TPE multivariate) | `forecast-cli tune`; trials persisted to `algo.hyperparam_trials` |
| ML — scaling | sklearn `StandardScaler` + custom `AsinhScaler` | Target scaler selected by `ExperimentConfig.target_scaler` |
| DataFrames | Polars (ingest path) + pandas (forecast path) | Domain models use Polars; preprocessor/engine use pandas |
| HTTP | `httpx` + `ratelimit` (400 calls / 60 s) | |
| Observability | Loki (logs) + Grafana 12 + auto-provisioned dashboards + file-provisioned alert rules | |
| Alerting | Slack webhook | `schedules.alerting.notify` — no-ops if `SLACK_WEBHOOK_URL` unset |
| Drift | Evidently 0.7 (`DataDriftPreset`) | KS test, in-process inside flow; can trigger retrain |
| Observability — research | W&B (`observability_wandb` package) | Backtests, predict runs, DNN training (Lightning), Optuna sweeps, ablation sweeps, reconciled prod metrics. Algo-research + algo-prod projects. No-op when `WANDB_MODE=disabled`. |
| CLI | Typer | `data-cli` and `forecast-cli` (`backtest`, `predict`, `tune`) |
| CI/CD | GitHub Actions + Tailscale | Pre-merge: pytest + ruff. Post-merge: SSH-deploy and smoke-test flow |

---

## 4. Repo layout

```
algo-repo/
├── CLAUDE.md                     # Conventions, project rules — read first
├── DEPLOYMENT.md                 # One-time setup + CI/CD runbook
├── README.md                     # User-facing overview
├── docs/
│   ├── REPO_OVERVIEW.md          # ◄ THIS file
│   ├── RUNBOOK.md                # Alert response procedures + manual interventions
│   └── CONTRIBUTING.md           # Contributor setup + conventions summary
├── docker-compose.yml            # 5 services: clickhouse, server, worker, loki, grafana
├── Dockerfile                    # The flow-run image (algo-repo:latest)
├── Dockerfile.worker             # The Prefect worker image
├── pyproject.toml                # uv workspace + dependency manifest
├── configs/                      # ExperimentConfig .py files, mounted into containers
│   ├── dk1_lear.py               # Current production LEAR config (DK1)
│   ├── de_lear.py                # Production LEAR config (DE)
│   ├── dk1_dnn.py / de_dnn.py    # DNN scaffolds — placeholder HPs, gated on `forecast-cli tune` before deployment
│   └── *.yaml                    # Orphaned — config_loader only loads .py; YAML files are not wired in
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/          # Loki + ClickHouse data sources
│   │   ├── dashboards/           # Dashboard provider config
│   │   └── alerting/rules.yaml   # File-provisioned alert rules (staleness, drift, missed reconciliation)
│   └── dashboards/               # JSON dashboard definitions
├── researh_material/             # Papers + planning docs (sic — kept as-is)
│   └── reading_guides/           # Section-by-section paper synthesis + codebase mappings
├── results/                      # Local backtest outputs (forecasts.csv, metrics.json)
│
├── src/                          # 7 uv workspace packages
│   ├── domain/                              # Pure dataclasses, no I/O
│   │   └── src/domain/{areas,curves,currency}.py
│   ├── infrastructure_entsoe/               # ENTSO-E HTTP client + XML parsers
│   │   └── src/infrastructure_entsoe/{client,mappers,entsoe_types,client_factory}.py
│   ├── infrastructure_clickhouse/           # CH client + ingest + queries + migrations
│   │   └── src/infrastructure_clickhouse/{ingest,queries,client_factory,logging_setup}.py
│   │       └── migrations/00{1..7}_*.sql
│   ├── data_cli/                            # `data-cli entsoe backfill <kind>` Typer app
│   │   └── src/data_cli/{main,utils,entsoe/{backfill,services}}.py
│   ├── forecast_cli/                        # `forecast-cli {backtest,predict}` Typer app
│   │   └── src/forecast_cli/{main,config_loader,tracking}.py
│   ├── price_forecasting/                   # The actual ML pipeline (see §9)
│   │   └── src/price_forecasting/
│   │       ├── configs/experiment.py        # ExperimentConfig dataclass (+ val dates, target_scaler, n_dnn_ensemble, retrain_on_drift)
│   │       ├── data/{clickhouse_loader,preprocessor,transformers,asinh_scaler}.py
│   │       ├── models/                      # base / lear / dnn / gbt_* / rf / sklearn_base / lightning_base
│   │       ├── backtesting/{engine,runner,splitting}.py   # splitting.py adds three-way date splitter
│   │       ├── evaluation/{metrics,summary,statistical_tests}.py   # DM + multivariate GW + DM/GW matrix
│   │       ├── tuning/{dnn_search,objective,optuna_storage}.py     # Optuna TPE + ClickHouse persistence
│   │       └── live_runner.py
│   └── schedules/                           # Prefect flows + deploy scripts
│       └── src/schedules/{ingestion,forecast,reconciliation,drift,retrain,alerting,deploy_ingestion,deploy_forecast}.py
│
└── tests/                        # Mirrors src/ layout exactly
```

**Mental model.** Three concentric rings:

1. **Domain** (innermost, no deps): pure types (`Area`, `Forecast`, `Observations`).
2. **Infrastructure** (depends on domain): ENTSO-E client, ClickHouse ingest/queries, logging.
3. **Application** (depends on both): `data_cli`, `forecast_cli`, `price_forecasting`, `schedules`.

`schedules` is the only layer that consumes everything; it is the "edge" of
the system.

---

## 5. Domain (`src/domain/`)

Two dataclasses + a registry of bidding zones. No I/O, no dependencies on
infrastructure.

### `domain.areas` — bidding zones

`Area` is a `frozen=True` dataclass: `tag, name, energy_identification_code,
country, currency, timezone (ZoneInfo)`. ~33 areas defined as module-level
constants (`NO, SE, FI, DK1, DK2, DE, AT, CH, ...`). Two lookup dicts:

```python
ENERGY_CODE_TO_AREA: dict[str, Area]     # e.g. "10YDK-1--------W" → DK1
TAG_TO_AREA:         dict[str, Area]     # e.g. "DK1" → DK1
```

Helpers `get_area_from_energy_code(code)` and `get_area_from_tag(tag)` raise
`ValueError` on miss. **The CLI tag lookup is case-sensitive at the dict
level**; case-insensitivity is added by `data_cli.utils.resolve_area`.

### `domain.curves` — observations + forecasts

Both `Observations` and `Forecast` wrap a `polars.DataFrame` validated by
`enforce_schema()` (raises `ValueError` on missing / extra / wrong-dtype /
wrong-order columns).

```python
Observations.SCHEMA = {
    "source":        pl.Utf8,
    "curve_name":    pl.Utf8,
    "area":          pl.Utf8,
    "timezone":      pl.Utf8,
    "timestamp_utc": pl.Datetime(time_zone=utc),
    "value":         pl.Float32,
    "ingested_utc":  pl.Datetime(time_zone=utc),
}

Forecast.SCHEMA = {
    "source", "curve_name", "area", "area_timezone", "model",
    "issued_utc", "issued_timezone", "timestamp_utc", "value", "ingested_utc"
}                                # all str/datetime; "value" is Float32
```

Both expose `.empty(curve_name)` to construct an empty frame with the right
schema.

**Curve name convention** — *spaces, not dots*:

| Type            | Pattern                                                  |
|-----------------|----------------------------------------------------------|
| Energy price    | `ENTSOE {area} EnergyPrice {ContractType} {Currency}`    |
| Total load      | `ENTSOE {area} TotalLoad {ProcessType}`                  |
| Generation      | `ENTSOE {area} Generation {ProcessType}`                 |
| Wind/Solar      | `ENTSOE {area} {Solar|WindOnshore|WindOffshore} {ProcessType}` |

(e.g. `ENTSOE DK1 TotalLoad Dayahead`, `ENTSOE DK1 WindOnshore Dayahead`.)

---

## 6. ENTSO-E client (`src/infrastructure_entsoe/`)

### `client.py` — `EntsoeClient(EntsoeClientBase)`

HTTP client wrapping `https://web-api.tp.entsoe.eu/api`. Four public fetch
methods, each returns a list of domain objects:

| Method                          | Doc type | Returns           | Default process |
|---------------------------------|----------|-------------------|-----------------|
| `fetch_energy_prices`           | `A44`    | `list[Observations]` | n/a             |
| `fetch_total_load_forecasts`    | `A65`    | `list[Forecast]`  | `A01`           |
| `fetch_generation_forecasts`    | `A71`    | `list[Forecast]`  | `A01`           |
| `fetch_wind_solar_forecasts`    | `A69`    | `list[Forecast]`  | `A01`           |

**Chunking.** Price requests are chunked in 12-month windows with pagination
(offset += 100, max 48 pages → safety stop with error log). Forecast
requests use 10-month chunks, no pagination. ZIP responses are auto-detected
(`PK` magic bytes) and extracted via `zipfile`.

**Rate limit.** `@sleep_and_retry @limits(calls=400, period=60)` on
`_rate_limit_get` — i.e. **400 req / 60 s**, blocking sleep when exceeded.

**Context manager.** Use as `with create_entsoe_client() as client:`. The
factory pulls `ENTSOE_API_KEY` from the environment.

**No-data sentinel.** ENTSO-E returns 200 with body `"No matching data
found for data item"`; the client detects that case-insensitively and
breaks the pagination loop without raising.

### `mappers.py` — XML → domain

- `_parse_energy_prices_xml_to_observation(xml_bytes) -> list[Observations]`
  — namespace `urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3`.
- `_parse_gl_market_document_xml_to_forecast(...)` — shared by total-load,
  generation, and wind/solar parsers. Namespace
  `urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0`.
- Helper `get_required_text(element, tag, ns)` raises `ValueError` for
  missing required fields (used to fail fast on schema drift).
- `_map_resolution_to_timedelta("PT15M"|"PT30M"|"PT60M")` → `timedelta`.
- `_map_A03_curve(start_utc, delta, positions)` builds the per-point
  timestamp from ENTSO-E's `position` index.
- All parsers **forward-fill** missing positions (ENTSO-E omits unchanged
  consecutive points; the client expands them).
- `WIND_SOLAR_PSR_NAMES = {"B16": "Solar", "B18": "WindOffshore", "B19":
  "WindOnshore"}`.

### `entsoe_types.py`

Enums for `ProcessType` (`Dayahead=A01, Realised=A16, ...`),
`MarketAgreementType`, etc. Used by both mappers and CLI for human-readable
labels.

---

## 7. ClickHouse infrastructure (`src/infrastructure_clickhouse/`)

### Tables (the `algo` database)

All time-aligned tables use `ReplacingMergeTree` keyed by an ingestion
timestamp so re-ingesting overlapping windows is safe. **Reads** that need
deduplication must use `FINAL` — or the caller must
`drop_duplicates(subset=["timestamp_utc"], keep="last")` after load.

| Table | Engine | ORDER BY | Source migration |
|---|---|---|---|
| `algo.timeseries` | `ReplacingMergeTree(ingested_utc)` | `(curve_name, timestamp_utc)`, `PARTITION BY toStartOfQuarter(timestamp_utc)` | `001` |
| `algo.forecasts` | `ReplacingMergeTree(ingested_utc)` | `(curve_name, model, issued_utc, timestamp_utc)`, partition same | `002` |
| `algo.experiment_runs` | `ReplacingMergeTree(created_utc)` | `(run_id)` | `003` + `006` |
| `algo.experiment_predictions` | `ReplacingMergeTree()` | `(run_id, timestamp_utc)`, partition same | `004` |
| `algo.model_artifacts` | `ReplacingMergeTree(created_utc)` | `(artifact_id)` | `005` |
| `algo.drift_reports` | `ReplacingMergeTree(created_utc)` | `(area, curve_name, report_id)`, partition `toStartOfQuarter(created_utc)` | `007` |
| `algo.hyperparam_trials` | `ReplacingMergeTree(created_utc)` | `(study_name, trial_number)` | `008` |
| `algo.retrain_events` | `ReplacingMergeTree(updated_utc)` | `(event_id)` | `009` |

#### Notable columns

- `algo.timeseries`: `source, curve_name, area, timezone, timestamp_utc, value (Float32), ingested_utc`
- `algo.forecasts`: adds `area_timezone, model, issued_utc, issued_timezone`
- `algo.experiment_runs` (after migration 006): `run_id, created_utc, experiment_name, area, model_type, config_json, metrics_json, training_duration_seconds, data_start_utc, data_end_utc, model_artifact_id`
- `algo.experiment_predictions`: `run_id, timestamp_utc, actual (Float32), predicted (Float32)`
- `algo.model_artifacts`: `artifact_id, created_utc, run_id, area, model_type, config_name, artifact_blob (base64), artifact_size_bytes`
- `algo.drift_reports`: `report_id, created_utc, area, curve_name, reference_start_utc, reference_end_utc, current_start_utc, current_end_utc, stat_test, drift_score, drift_threshold, drift_detected (UInt8), reference_n, current_n`
- `algo.hyperparam_trials`: `study_name, trial_number, created_utc, area, model_type, config_name, val_start_utc, val_end_utc, params_json, value (Float64), state` — one row per Optuna trial
- `algo.retrain_events`: `event_id, created_utc, updated_utc, triggered_by, area, config_name, drift_report_id (Nullable), status, completed_utc (Nullable), new_run_id (Nullable), notes (Nullable)`. **Version key is `updated_utc`**, not `created_utc` — callers must pass a strictly later `updated_utc` on each re-insert so the terminal status row wins deduplication

### `ingest.py` — writes

All inserts go through `insert_polars_dataframe(client, df, table, batch_size=10_000)` which uses `client.insert_arrow(table, df.to_arrow())` in chunks and logs `Starting ClickHouse insert` / `ClickHouse insert failed` to Loki via `LOGGER`.

Public functions:

| Function | Target table |
|---|---|
| `insert_observations_batch(client, observations)` | `algo.timeseries` |
| `insert_forecasts_batch(client, forecasts)` | `algo.forecasts` |
| `insert_experiment_run(client, run_id, created_utc, experiment_name, area, model_type, config_json, metrics_json, *, training_duration_seconds=None, data_start_utc=None, data_end_utc=None, model_artifact_id=None)` | `algo.experiment_runs` |
| `insert_experiment_predictions(client, predictions: pl.DataFrame)` (long format, columns `run_id, timestamp_utc, actual, predicted`) | `algo.experiment_predictions` |
| `insert_model_artifact(client, artifact_id, created_utc, run_id, area, model_type, config_name, artifact_blob, artifact_size_bytes)` | `algo.model_artifacts` |
| `insert_drift_report(client, *, report_id, created_utc, area, curve_name, reference_start_utc, reference_end_utc, current_start_utc, current_end_utc, stat_test, drift_score, drift_threshold, drift_detected, reference_n, current_n)` | `algo.drift_reports` |
| `insert_hyperparam_trial(client, *, study_name, trial_number, created_utc, area, model_type, config_name, val_start_utc, val_end_utc, params_json, value, state)` | `algo.hyperparam_trials` |

`insert_experiment_run` has **keyword-only extras** for the columns added in
migration 006; defaults are `0.0` / epoch / empty-string so reads never see
`NULL`.

### `queries.py` — reads

- `get_unreconciled_runs(client) -> list[dict]` — returns all 11 columns
  for any `experiment_runs FINAL` row where `metrics_json = '{}'`.
- `get_predictions_for_runs(client, run_ids: list[str]) -> list[dict]` — one
  batched query with `IN (?)` placeholders. No N+1.
- `get_actual_prices_for_period(client, area, start_utc, end_utc)` — matches
  any `ENTSOE {area} EnergyPrice %` curve (LIKE), filters time range, uses
  `FINAL`.
- `load_latest_artifact(client, area, model_type, config_name) -> dict | None`
  — most recent `model_artifacts` row, ordered by `created_utc DESC`.
- `get_recent_accuracy(client, area, config_name, days=30) -> float | None`
  — median MAE over completed runs in the last `days` days, used by
  reconciliation's accuracy-degradation alert.

### `migrations/`

Numbered SQL files auto-discovered in sorted order by `run_migrations.py`.
**Never modify an existing migration — always add a new one.** Re-runs
are safe (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`).

### `logging_setup.py` — Loki + console

- `get_logger(name, *, service)` returns a `ServiceLoggerAdapter` that
  attaches the `service` label and propagates the structured fields from
  `extra=`.
- `build_log_extra(**kwargs)` filters `None`/empty values; use it to assemble
  the `extra=` payload.
- Recognized context fields (sent as Loki labels):
  `service, module, area, config_name, target_date, run_id, table_name,
  batch_size, status_code, chunk_start, chunk_end, offset, row_count,
  batch_count, run_count, response_sets, training_duration_seconds,
  total_reconciled, total_skipped`.
- Console formatter appends `key=value` pairs for the same fields when
  present.
- Loki handler activates only when `LOKI_URL` is set; it gracefully
  no-ops if `python-logging-loki` import fails.

**Rule.** `schedules/*` and `infrastructure_*` must never `print()` for
production telemetry — call `LOGGER.info(...)` with `extra=build_log_extra(...)`.
Bare `print()` is used inside Prefect tasks alongside the logger because
Prefect captures stdout in the run UI.

### `client_factory.py`

`create_client()` builds the `clickhouse_connect.driver.client.Client` from
env vars: `CLICKHOUSE_HOST` (default `localhost`), `CLICKHOUSE_PORT` (`8123`),
`CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `CLICKHOUSE_DATABASE` (`algo`).
Always close it via `try/finally` (no context manager).

---

## 8. Price forecasting (`src/price_forecasting/`)

This is the ML core. Pure pandas + numpy + sklearn for LEAR; pandas +
Lightning for the deep models. All resolution-aware: data can be hourly
(24 periods/day) or 15-min (96/day). **Never hardcode `24`** — derive from
`targets.shape[1]` or call `detect_n_periods()`.

### 8.1 `configs/experiment.py` — `ExperimentConfig`

```python
@dataclass
class ExperimentConfig:
    experiment_name: str
    results_dir: str
    area: str                              # e.g. "DK1"

    target_column: str = "price"
    target_scaler: str = "standard"        # "standard" | "asinh" — see AsinhScaler (Lago §4.2)

    # Preferred split mode: explicit dates
    test_start_date: str | None = None     # e.g. "2026-01-01"
    test_end_date:   str | None = None
    val_start_date: str | None = None      # required for `forecast-cli tune`
    val_end_date:   str | None = None

    # Fallback: ratio-based split
    train_ratio:      float = 0.7
    validation_ratio: float = 0.15
    test_ratio:       float = 0.15

    calibration_windows: list[int] = [56, 84, 1092, 1456]   # LEAR-paper default
    refit_interval_days: int = 1                            # 1=LEAR, 7=DNN

    model_type:   str = "LEAR"                              # see MODEL_REGISTRY keys
    exogenous_curve_types: list[str] = []                   # ["TotalLoad","Generation","Solar",...]
    model_params: dict[str, Any]      = {}                  # e.g. {"alpha": 0.01}

    feature_transformers: list | None = None                # None → defaults
    n_dnn_ensemble: int = 1                                 # seed-varied ensemble size for DNN live serving (Lago §4.4)
    retrain_on_drift: bool = False                          # gate for drift→retrain hook in schedules.drift
```

Example config (`configs/dk1_lear.py`):

```python
config = ExperimentConfig(
    experiment_name="dk1_lear",
    area="DK1",
    model_type="lear",
    results_dir="results",
    test_start_date="2026-01-01",
    test_end_date="2026-03-22",
    calibration_windows=[56, 84, 1092, 1456],
    refit_interval_days=1,
    exogenous_curve_types=["TotalLoad"],
    model_params={"alpha": 0.01},
)
```

Config files are **Python**, loaded by `forecast_cli.config_loader.load_config(name)`
which `importlib.util`-loads `configs/{name}.py` and reads its module-level
`config` variable. The flow container mounts `configs/` as a Docker volume
(`-v <host>/configs:/app/configs`), so a config-only change does not require
an image rebuild.

### 8.2 Data path

```
load_dataset(config)                              # data/clickhouse_loader.py
  ├── load_price_series(client, area)             #   reads algo.timeseries, dedups
  └── load_exogenous_series(client, area, types)  #   reads algo.forecasts per type
  → pandas DataFrame, DatetimeIndex (UTC), columns: ["price", *exogenous_types]
                  │
                  ▼
DataPreprocessor(config)                          # data/preprocessor.py
  ├── pivot_to_daily(df, col) → daily wide (date × p0..pN)
  ├── transformers (see 8.3): for t in transformers: t.transform(hourly, daily_prices)
  └── pd.concat blocks column-wise → features (daily index)
  → (features: DataFrame, targets: DataFrame)     # aligned, NaN-dropped
```

Helpers:

- `detect_n_periods(index)` — `≤15 min` → 96, else 24.
- `pivot_to_daily(df, column)` — produces columns `{col}_p0..{col}_pN`.

Scaling lives in `DataPreprocessor`:

- `transform_data(X_train, y_train, X_test)` → fit+transform feature scaler,
  fit+transform target scaler, transform test features. Returns three numpy
  arrays.
- `transform_features(X)` — transform only.
- `inverse_transform_predictions(y_scaled)` — inverse over the target scaler.
- **Target scaler selection** via `config.target_scaler`: `"standard"`
  (sklearn `StandardScaler`) or `"asinh"` (custom `AsinhScaler` in
  `data/asinh_scaler.py`, applies a median/MAD-scaled inverse-hyperbolic-sine
  transform — Uniejewski, Weron & Ziel 2018; recommended by Lago §4.2 for
  EPF because it accommodates negatives and dampens spikes).

> **Circular-import note.** `transformers.py` imports `pivot_to_daily` from
> `preprocessor.py`. `preprocessor.py` imports
> `default_transformers_for_model` **as a lazy local import inside `__init__`**
> to break the cycle. Don't move it to the module top.

### 8.3 Feature transformers (`data/transformers.py`)

Interface:

```python
class FeatureTransformer(ABC):
    @abstractmethod
    def transform(self, hourly_df: pd.DataFrame,
                  daily_prices: pd.DataFrame) -> pd.DataFrame: ...
```

Implementations:

| Transformer | Output columns | Notes |
|---|---|---|
| `PriceLagTransformer(lags=[1,2,3,7])` | `len(lags) × n_periods` | Shifts daily-pivoted price matrix by each lag |
| `ExogenousLagTransformer(exogenous_columns, lags=[("d0",0),("d1",1),("d7",7)])` | `len(cols) × len(lags) × n_periods` | One lag block per (column, lag) |
| `CalendarDummyTransformer()` | 7 (`day_0..day_6`) | Day-of-week one-hot |
| `CyclicalTimeTransformer()` | 2 (`doy_sin`, `doy_cos`) | Annual seasonality |
| `MeanWeeklyForecastTransformer(exogenous_columns, window_days=7)` | 1 per column (`{col}_week_mean`) | Compressed alternative for deep models |

Factory:
```python
default_transformers_for_model(exogenous_columns) -> [
    PriceLagTransformer(lags=[1,2,3,7]),
    ExogenousLagTransformer(exogenous_columns=exogenous_columns),
    CalendarDummyTransformer(),
]
```
Bit-identical to the LEAR paper. Override via `ExperimentConfig.feature_transformers`.

**Feature explosion** with default transformers (hourly):
`4 × 24 + n_exog × 3 × 24 + 7 = 103 + 72 · n_exog` features. Fine for LEAR
(Lasso handles it). Use `MeanWeeklyForecastTransformer` /
`CyclicalTimeTransformer` for deep models to keep dimensionality down.

### 8.4 Models

Common base + three mid-level abstractions:

```
BaseModel(ABC)                  # base.py — fit(features, targets) / predict_day(features) → np.ndarray of length n_periods
  ├── SklearnModel(ABC)         # sklearn_base.py — for native multi-output sklearn estimators
  │     └── RandomForestModel
  ├── GBTModel(ABC)             # gbt_base.py — trains one estimator per period; eval_set hook
  │     └── XGBoostModel
  ├── LightningModel(ABC)       # lightning_base.py — handles full Lightning Trainer loop
  │     └── DNNModel            # dnn.py — feedforward (256, 256) by default
  └── LearModel                 # lear.py — direct; one Lasso(per period); supports LassoCV when alpha is None/"auto"
```

Model registry & factory (`models/__init__.py`):

```python
MODEL_REGISTRY = {
    "lear":     LearModel,
    "dnn":      DNNModel,
    "rf":       RandomForestModel,
    "xgboost":  XGBoostModel,
}

def get_model(name: str, **kwargs) -> BaseModel: ...   # case-insensitive
```

`ExperimentConfig.model_type` is matched against this registry (lowercased).

**LEAR detail** (`lear.py`):

- One `Lasso` per period, stored in `self.hourly_models: dict[period_idx, Lasso]`.
- If `alpha in (None, "auto")`, swaps in `LassoCV(cv=TimeSeriesSplit(n_splits=cross_validation_folds))`; best alpha is recorded in `self.best_alphas`.
- `max_iter = maximum_iterations` (default `5000`) — increase if Lasso warns about non-convergence.

**LightningModel detail** (`lightning_base.py`):

- Constructor knobs: `epochs=500, batch_size=64, learning_rate=1e-3, l1_reg=0.0, validation_fraction=0.2, early_stopping_patience=25, random_seed=42`.
- Loss: L1 (MAE).
- Optimizer: Adam (override `configure_optimizers` to change).
- Includes an in-memory **best-weight callback** (no disk checkpoint) + `EarlyStopping(monitor="val_loss", patience=25)`.
- `trainer = L.Trainer(enable_progress_bar=False, enable_model_summary=False, enable_checkpointing=False, logger=False)` — silent by design; Lightning warnings are suppressed at module import.

**GBTModel detail** (`gbt_base.py`):

- Splits training set into the last `validation_fraction` rows for `eval_set`.
- Subclasses override `_fit_period(estimator, X_train, y_train, X_val, y_val)` to wire native early stopping.
- Per-period estimators in `self._period_models`.

### 8.5 Backtesting (`backtesting/`)

#### `splitting.py`

```python
SplitResult(train: DatasetSplit, validation: DatasetSplit, test: DatasetSplit)
DatasetSplit(features, targets) with .dates property

split_dataset(features, targets, train_ratio, validation_ratio, test_ratio)
split_by_dates(features, targets, test_start_date, test_end_date)              # validation is empty
split_train_val_test_by_dates(features, targets, val_start, val_end, test_start, test_end)
```

`BacktestRunner._split_data` picks the date-based split iff
`test_start_date AND test_end_date` are set; otherwise falls back to ratios.
The three-way splitter is used by `forecast-cli tune` and any code path
that needs a held-out validation window separate from the test set.

#### `engine.py` — `BacktestEngine`

For each test date and each calibration window:

1. Slice training data: `[target_date - window_size, target_date - 1]`.
2. If we haven't fit yet for this window, or `days_since_last_fit ≥ refit_interval_days`:
   - Fit a fresh `DataPreprocessor` (scaling refit on the window slice).
   - Build a new model via `model_factory()`.
   - Predict scaled, inverse-transform.
   - Cache `WindowState(last_fit_date, model, preprocessor)`.
3. Otherwise reuse the cached preprocessor + model to transform test
   features and predict. **The cached scaler is intentionally not
   re-fit between refits** to avoid leakage.

The day's forecast is the simple **mean of all window predictions**
(`np.mean(window_forecasts, axis=0)`).

`run(model_factory, features, targets, test_dates) -> (forecasts_df, actuals_df)`
returns wide-format daily DataFrames with columns `h0..hN`.

#### `runner.py` — `BacktestRunner`

Loads data, splits, calls the engine, writes:

- `results/{experiment_name}_forecasts.csv`
- `results/{experiment_name}_actuals.csv`
- `results/{experiment_name}_metrics.json`
- `results/{experiment_name}_metrics_per_hour.csv`

Naive baseline for `rMAE` is the weekly-naive: `actuals.shift(7)` (the same
weekday last week).

### 8.6 Live runner (`live_runner.py`)

Single-date prediction reusing the engine's ensemble logic:

```python
LiveResult(prediction: pd.Series, data_start_utc, data_end_utc,
           training_duration_seconds, trained_models: dict[...])
```

Used by:
- `forecast-cli predict <config> -d <date>` (just the prediction).
- `schedules.forecast.daily_forecast_flow` (full metadata, persisted via
  `track_prediction()`).

**DNN ensembling.** When `config.model_type == "dnn"` and
`config.n_dnn_ensemble > 1`, `LiveRunner.run_live_with_metadata()` fits
`n_dnn_ensemble` replicates per calibration window with distinct random
seeds and averages their predictions (Lago §4.4). The `trained_models`
dict is then keyed by `(seed, window_size)` rather than bare `window_size`.

### 8.7 Evaluation (`evaluation/`)

`metrics.py` (per-array, flat numpy):

```python
calculate_mae(y_true, y_pred)
calculate_rmse(y_true, y_pred)
calculate_smape(y_true, y_pred)            # symmetric MAPE, ×100
calculate_mape(y_true, y_pred)             # ×100
calculate_rmae(y_true, y_pred, y_naive)    # MAE(y, ŷ) / MAE(y, y_naive); NaN when denom=0
```

`summary.py` (wide-format DataFrames):

```python
build_weekly_naive(actuals) = actuals.shift(7)
compute_metrics_summary(forecasts, actuals, naive_forecasts=None) -> dict
compute_metrics_per_hour(forecasts, actuals, naive_forecasts=None) -> DataFrame  # one row per hour column
compute_dm_pvalue_matrix(error_arrays: dict[str, np.ndarray]) -> pd.DataFrame    # GW-test p-value matrix across models
```

`statistical_tests.py`:

```python
diebold_mariano(errors_a, errors_b, loss="mae" | "mse") -> (stat, p_value)
giacomini_white_multivariate(errors_a, errors_b, h=1, kernel="bartlett") -> (stat, p_value)
```

> **Important.** Reconciliation uses the flat-array helpers from `metrics.py`
> (`np.ndarray` inputs), **not** `compute_metrics_summary()` which is
> wide-format/backtest-oriented.

### 8.8 Tuning (`tuning/`)

Optuna TPE search for DNN architecture hyperparameters, used by
`forecast-cli tune`.

| File | What it does |
|---|---|
| `dnn_search.py` | `build_dnn_search_space(trial)` — 6 architecture HPs (`n_neurons`, `activation`, `dropout`, `learning_rate`, `batch_norm`, `l1_reg`). Lago §4.3.3's feature/selector HPs are intentionally omitted until the preprocessor/model expose constructor toggles. |
| `objective.py` | `dnn_validation_objective(trial, config, search_space_fn)` — trains a DNN per val day with the engine's ensemble logic and returns the mean validation MAE. `n_neurons` → `hidden_units` via `_PARAM_REMAP`. |
| `optuna_storage.py` | `build_persistence_callback(client, study_name, area, ..., val_start_utc, val_end_utc)` — Optuna callback that writes each trial to `algo.hyperparam_trials`. |

After tuning, paste `study.best_params` into the config's `model_params`
dict (architecture keys map 1:1 to `DNNModel.__init__` with `n_neurons`
renamed to `hidden_units`).

---

## 9. CLIs

### 9.1 `data-cli` (`src/data_cli/`)

`uv run python -m data_cli.main entsoe backfill <command>`

| Command | Doc | Target table | Flags |
|---|---|---|---|
| `price-document`     | A44 | `algo.timeseries` | `-a/--area`, `-s/--start`, `-e/--end` |
| `total-load`         | A65 | `algo.forecasts`  | + `-p/--processtype` (`A01,A16,A31,A32,A33`) |
| `generation-forecast`| A71 | `algo.forecasts`  | + `-p/--processtype` |
| `wind-solar`         | A69 | `algo.forecasts`  | + `-p` (`A01,A18,A40`), `--psrtype` (`B16,B18,B19`) |

**Flag order convention** — always use named flags; area is `-a`, never
positional. Datetimes go through `data_cli.utils.parse_flexible_datetime`
(ISO, compact, human-readable). Area tags are normalized case-insensitively
by `resolve_area`.

Service layer (`data_cli/entsoe/services.py`): four pure-Python functions
returning `BackfillResult(data_type, area, sets_fetched, rows_fetched)`,
imported by both the CLI and `schedules.ingestion`. The CLI is a thin
adapter — never duplicate the fetch+insert logic.

### 9.2 `forecast-cli` (`src/forecast_cli/`)

`uv run python -m forecast_cli.main {backtest|predict|tune}`

| Command | Args | Notes |
|---|---|---|
| `backtest <config_name>` | `--track` (optional) | Loads `configs/<config_name>.py`, runs `BacktestRunner`, prints MAE/RMSE/sMAPE/rMAE summary |
| `predict <config_name>`  | `-d/--date`, `--track` | Runs `LiveRunner`, prints `period | HH:MM | predicted` table |
| `tune <config_name>`     | `-n/--n-trials`, `--study-name`, `--dry-run` | Optuna TPE search for DNN architecture HPs. Rejects non-DNN configs and requires `val_start_date`/`val_end_date`. Trials persisted to `algo.hyperparam_trials`. |

**`--track`** writes to ClickHouse:

- Backtest: one `experiment_runs` row + N `experiment_predictions` rows.
- Predict: one `experiment_runs` row (`metrics_json='{}'` until reconciled),
  N predictions (`actual=0.0` placeholder), plus a `model_artifacts` row
  containing the base64-encoded joblib blob of `LiveResult.trained_models`
  (the full ensemble dict).

`tracking.py` is responsible for the long-format reshape, the timestamp
synthesis (`base_date + period × minutes_per_period`), and the artifact
serialization (joblib + base64).

---

## 10. Schedules / Prefect (`src/schedules/`)

Prefect 3.x, Docker work pool. Each flow is registered via a `*FlowDeployment`
class that bakes `image_pull_policy=Never`, network mode, and env vars (read
from host `.env`).

### Flows

| File | Flow name | Default cron | Purpose |
|---|---|---|---|
| `ingestion.py`        | `entsoe-backfill`        | `0 * * * *` (per area) | Fetch last 48 h of all 4 data types per area, idempotent (RMT dedups) |
| `forecast.py`         | `daily-forecast`         | `0 6 * * *` (per config) | LiveRunner → `track_prediction()` for tomorrow |
| `reconciliation.py`   | `reconcile-predictions`  | `0 18 * * *`            | Fetch yesterday's actuals; backfill predictions; compute metrics; re-insert; Slack-alert if MAE > 1.5× 30-day median |
| `drift.py`            | `drift-detection`        | `0 19 * * *` (per area) | Evidently `DataDriftPreset` (KS test), 7-day vs 90-day window; triggers `triggered_retrain_flow` for configs where `retrain_on_drift=True`; posts to Slack on drift |
| `retrain.py`          | `triggered-retrain`      | event-driven           | Re-runs `daily_forecast_flow` for the affected config and writes an audit row to `algo.retrain_events` (version-keyed by `updated_utc`) |
| `alerting.py`         | (helper)                 | n/a                     | `notify(subject, message, severity)` — POSTs to `SLACK_WEBHOOK_URL`; safe no-op when unset, so local dev never fails |

**Ingestion** uses one `@task` per data type (`ingest_energy_prices_task`,
`ingest_total_load_task`, `ingest_generation_forecast_task`,
`ingest_wind_solar_task`), all with `retries=2, retry_delay_seconds=60`. They
run sequentially to respect ENTSO-E's 400/60 s limit. Each calls into
`data_cli.entsoe.services.backfill_*`.

Constants: `LOOKBACK_HOURS = 48`, `LOOKAHEAD_HOURS = 24`.

**Forecast** is a 3-task pipeline: `load_config_task → predict_task →
track_prediction_task`. The middle task wraps `LiveRunner.run_live_with_metadata`
and is the only one with retries — config and tracking are deterministic.

**Reconciliation** is **batched per area** (one prediction query + one
actuals query per area — never N+1):

1. `get_unreconciled_runs()` → rows where `metrics_json='{}'`.
2. Group by area.
3. For each area: one query for predictions across all run_ids, one for
   actual prices over the spanning time window.
4. For each run: match predictions to actuals by timestamp. **If any actual
   is missing, skip the run** (will retry next day — `skipped += 1`).
5. Re-insert `experiment_predictions` with actuals filled in.
6. Re-insert `experiment_run` with new `created_utc=now` and `metrics_json`
   set. `ReplacingMergeTree(created_utc)` keeps the newer row on merge;
   reads use `FINAL`. **Never use `UPDATE` / `OPTIMIZE FINAL`.**

**Drift**: Evidently's `DataDriftPreset` runs in-process. Reference window =
last 90 days (excluding the most recent 7), current window = last 7 days,
both aligned to UTC midnights. Skipped when either window has < 30 samples.
Score, threshold, test name, and the boolean verdict (from
`DriftedColumnsCount > 0`) land in `algo.drift_reports`. A WARNING is
emitted to Loki when drift is detected and a Slack message is posted via
`alerting.notify`. For each config where `retrain_on_drift=True`, the
flow enqueues `triggered_retrain_flow` for that config — which writes a
`running` row to `algo.retrain_events`, runs `daily_forecast_flow`, then
writes a `completed`/`failed` row with a strictly later `updated_utc`.

**Triggered retrain** (`retrain.py`):
1. Generate `event_id = uuid4()`, capture `started = now()`.
2. Insert audit row: `created_utc = started, updated_utc = started, status = "running"`.
3. Call `daily_forecast_flow(config_name=...)` synchronously.
4. Insert terminal row: `created_utc = started` (immutable), `updated_utc = now()` (strictly later, version key), `status = "completed" | "failed"`, `completed_utc = now()`, `new_run_id` on success or `notes` on failure.
5. Reads of `algo.retrain_events` should use `FINAL` (engine `ReplacingMergeTree(updated_utc)`); never `UPDATE`/`OPTIMIZE FINAL`.

**Accuracy degradation alert** (in `reconciliation.py`): after each
successful per-run reconciliation, `_maybe_alert_accuracy_degradation`
compares today's MAE against the 30-day median fetched via
`get_recent_accuracy`. Alert fires when `today_mae > 1.5 × baseline`.
The baseline is cached per `(area, config_name)` for the duration of a
single area-task to avoid N+1 ClickHouse queries.

### Deploy scripts

`deploy_ingestion.py`:
- `AREAS = ["DK1", "DK2", "NL", "BE", "DE", "FR", "PL"]`
- One deployment per area, named `entsoe-backfill-<lower(area)>`.
- All on `cron="0 * * * *"`.

`deploy_forecast.py`:
- `FORECAST_CONFIGS = ["dk1_lear", "de_lear"]` → one `daily-forecast-<config>` per LEAR config at `0 6 * * *`. **DNN configs (`dk1_dnn.py`, `de_dnn.py`) are intentionally excluded** — they ship with placeholder hyperparameters and only join the list once `forecast-cli tune` has produced validated `model_params`.
- One `reconcile-predictions` deployment at `0 18 * * *`.
- `DRIFT_AREAS = ["DK1", "DE"]` → one `drift-detection-<lower(area)>` per area at `0 19 * * *`.
- Mounts `configs/` from the host into `/app/configs` of each ephemeral container.
- `SLACK_WEBHOOK_URL` is read from `.env` and baked into every flow container.

Both scripts are idempotent — rerun any time. New area / config → add to
the list and rerun the script; no flow code changes.

### Env baked into every flow container

`PREFECT_API_URL=http://server:4200/api`,
`CLICKHOUSE_{HOST,PORT,USER,PASSWORD,DATABASE}`, `ENTSOE_API_KEY` (ingestion
only), `LOKI_URL`, `SLACK_WEBHOOK_URL` (optional — alerts no-op if unset).

---

## 11. Observability

### Grafana

Three auto-provisioned dashboards (`grafana/dashboards/*.json`):

1. **Data Quality** — coverage and freshness of `algo.timeseries` and `algo.forecasts`.
2. **Model Performance** — MAE / RMSE / sMAPE per run from `algo.experiment_runs`.
3. **Operational** — Loki log stream filtered by `job=algo-repo`.

> **Always edit dashboards as JSON** in `grafana/dashboards/`. UI edits are
> overwritten on container restart.

### Loki

Logs are pushed directly from Python via `python-logging-loki`. Labels are
the values in `extra=` (filtered through `build_log_extra`). Default
service tags: `job="algo-repo"`, `application="algo-repo"`. Each module's
logger is created with a `service=` name (e.g. `prefect-ingestion`,
`prefect-forecast`, `prefect-reconciliation`, `prefect-drift`,
`entsoe-client`, `clickhouse-ingest`).

### Drift & operational alerts

Two layers:

1. **Slack via `schedules.alerting.notify`** — fired in-process by the
   reconciliation flow (accuracy degradation) and the drift flow (drift
   detected, retrain triggered/completed/failed). Safe no-op when
   `SLACK_WEBHOOK_URL` is unset, so local dev never fails.
2. **Grafana file-provisioned alert rules** at
   `grafana/provisioning/alerting/rules.yaml` — three rules:
   - `data-staleness`: fires when `max(timestamp_utc)` in `algo.timeseries`
     is more than 12 hours stale.
   - `drift-detected-today`: fires when any row in `algo.drift_reports`
     for today has `drift_detected = 1`.
   - `reconciliation-missed`: fires when no `reconcile-predictions` run
     has completed in the last 25 hours.

> **Always edit alert rules as YAML** in `grafana/provisioning/alerting/`.
> UI edits are overwritten on container restart, same as dashboards.

### W&B (research)

`observability_wandb.tracker.WandbTracker` is the single owner of W&B-side
schema. Dual-write call sites: `forecast_cli.tracking.track_backtest_run /
track_prediction`, `price_forecasting.models.lightning_base.LightningModel`
(via `WandbLogger`), `price_forecasting.tuning.optuna_storage`, and
`schedules.reconciliation`. Production system is unaffected when the
tracker is disabled.

- `algo-research` project — backtests, predict runs, DNN training, sweeps,
  ablations.
- `algo-prod` project — one continuous run per `(area, config_name)`,
  one step per reconciled day. Run ID format: `prod-{area_lower}-{config}`.
- Disabled-mode: set `WANDB_MODE=disabled` or unset `WANDB_API_KEY`.
- New CLI: `forecast-cli ablate <config> --vary <field> --over <json>`.

---

## 12. CI/CD

### Pre-merge

- `.github/workflows/pr_test.yml` — `pytest`.
- `.github/workflows/pr_ruff-lint.yaml` — `ruff check`.
- The smoke test `tests/price_forecasting/test_smoke.py` runs in CI like any
  other test — no extra config.

### Post-merge

`.github/workflows/cd_deploy.yml` fires on push to `main`:

1. Joins the tailnet via the Tailscale GitHub Action (OAuth client, `tag:ci`).
2. SSHes into the deploy host via Tailscale SSH (`DEPLOY_HOST`, `DEPLOY_USER`).
3. `git pull && docker build -t algo-repo:latest .`
4. Reruns both deploy scripts.
5. Triggers `daily-forecast/daily-forecast-dk1_lear` via the Prefect Python
   API and polls until completion.

Required GitHub secrets: `TS_OAUTH_CLIENT_ID`, `TS_OAUTH_SECRET`,
`DEPLOY_HOST` (MagicDNS), `DEPLOY_USER`, `DEPLOY_REPO_PATH`.

---

## 13. Conventions, invariants, gotchas

These are the rules that experience has carved into the codebase. Violate
at your peril.

### Naming

- Curve names use **spaces**, not dots: `ENTSOE DK1 TotalLoad Dayahead`.
- Module names: snake_case. Workspace packages mirror folder names.
- CLI flags: short + long, always named (`-a/--area`, `-s/--start`).
- Currency in `Area` is the **physical local currency** (`DK1` → `DKK`),
  not the trading currency (which is usually EUR).

### Data model

- Polars DataFrames with **strict schema** in domain. `enforce_schema()`
  is your friend — let it fail loudly on drift.
- Always `drop_duplicates(subset=["timestamp_utc"], keep="last")` after
  loading from `algo.timeseries` / `algo.forecasts` unless you used `FINAL`.
- `ReplacingMergeTree` deduplicates **lazily**; force a merge with
  `OPTIMIZE TABLE algo.timeseries FINAL` (rare — usually unnecessary).

### Migrations

- One purpose per migration, numbered `NNN_*.sql`. Never modify after merge.
- `CREATE TABLE IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` so reruns are safe.

### Models

- `predict_day(features)` returns a flat `np.ndarray` of length `n_periods`.
- Never hardcode `24`. Derive from `targets.shape[1]` or call
  `detect_n_periods(index)`.
- Cached `WindowState` reuses the **same scaler** across days within a refit
  interval — this is intentional. Refitting the scaler each day would leak
  test info backwards.

### Tracking

- `experiment_runs.metrics_json='{}'` is the **sentinel for unreconciled**.
  Don't use NULL.
- Reconciliation re-inserts with a fresh `created_utc` so RMT picks the new
  row. Don't try to `ALTER`/`UPDATE`.
- `model_artifact_id=''` (empty string) means "no artifact" (e.g. for
  backtests). Don't use NULL.
- `algo.retrain_events` uses **`updated_utc`** as the RMT version column
  (not `created_utc`). `created_utc` is immutable per event; `updated_utc`
  must be strictly later on each re-insert (running → completed/failed)
  so the terminal status row wins deduplication.

### Tuning

- `forecast-cli tune <config>` is **DNN-only**. The command rejects
  configs whose `model_type != "dnn"` with a clear `BadParameter`.
- Configs must declare `val_start_date` / `val_end_date` — the validation
  window is independent of `test_start_date`/`test_end_date`.
- Best params from `study.best_params` paste 1:1 into `model_params`
  except `n_neurons` which is renamed to `hidden_units` by `_PARAM_REMAP`.
- DNN serving averages `n_dnn_ensemble` replicates with distinct random
  seeds. `LiveResult.trained_models` keys are `(seed, window_size)` when
  `n_dnn_ensemble > 1` and bare `window_size` otherwise.

### Prefect

- Add a new area to ingestion → append to `AREAS` in `deploy_ingestion.py`,
  rerun the script. **Do not edit the flow.**
- Add a new forecast config → drop `configs/<name>.py` on the host, append
  to `FORECAST_CONFIGS`, rerun `deploy_forecast.py`. **No image rebuild.**
- All tasks have `retries=2` where retry is safe. Reconciliation tasks
  retry; ingest tasks retry; tracking does not.

### Logging

- Inside flows / infrastructure: `LOGGER.info("msg", extra=build_log_extra(...))`.
- Bare `print()` is fine inside Prefect `@task` bodies (Prefect captures
  stdout for the UI), but **always** log via the structured logger in
  parallel for Loki.

### Imports

- `price_forecasting/*` submodules must **not** import from the top-level
  `price_forecasting/__init__.py` — that's a circular import. Use
  subpackage paths: `from price_forecasting.configs import X`,
  `from price_forecasting.evaluation import X`, etc.
- Re-exports in `__init__.py` use `from x import Y as Y` to satisfy
  ruff F401.

### Tests

- Fake clients only — no live ENTSO-E or live ClickHouse calls.
- Sample XML fixtures are inlined as byte literals in `conftest.py`.
- Pattern: `class Test<Feature>` with one test per case.
- Cover: return type, row count, schema, key field values, edge cases.
- Don't hardcode period counts — derive them.

---

## 14. Common commands

```bash
# Tests
python -m pytest tests/ -v
python -m pytest tests/infrastructure_entsoe/ -v

# Migrations
uv run python -m infrastructure_clickhouse.migrations.run_migrations

# Backfill
uv run python -m data_cli.main entsoe backfill price-document  -a DK1 -s 2024-01-01 -e 2025-01-01
uv run python -m data_cli.main entsoe backfill total-load      -a DK1 -s 2024-01-01 -e 2025-01-01
uv run python -m data_cli.main entsoe backfill generation-forecast -a DK1 -s 2024-01-01 -e 2025-01-01
uv run python -m data_cli.main entsoe backfill wind-solar      -a DK1 -s 2024-01-01 -e 2025-01-01 --psrtype B19

# Forecast
uv run python -m forecast_cli.main backtest dk1_lear --track
uv run python -m forecast_cli.main predict  dk1_lear -d 2026-03-22 --track
uv run python -m forecast_cli.main tune     dk1_dnn  --n-trials 100   # Optuna TPE, DNN-only

# Deploy (set PREFECT_API_URL first)
export PREFECT_API_URL="http://localhost:4200/api"
uv run python src/schedules/src/schedules/deploy_ingestion.py
uv run python src/schedules/src/schedules/deploy_forecast.py

# Manual flow triggers
python -c "from schedules.ingestion import entsoe_backfill_flow; entsoe_backfill_flow(area='DK1')"
python -c "from schedules.forecast import daily_forecast_flow; daily_forecast_flow(config_name='dk1_lear')"
python -c "from schedules.reconciliation import reconcile_predictions_flow; reconcile_predictions_flow()"
python -c "from schedules.drift import drift_detection_flow; drift_detection_flow(area='DK1')"
python -c "from schedules.retrain import triggered_retrain_flow; triggered_retrain_flow(config_name='dk1_lear', triggered_by='manual', area='DK1')"

# Docker
docker build -t algo-repo:latest .
docker compose up -d
docker compose logs worker --tail 50
```

---

## 15. Where to look when…

| Task | Start here |
|---|---|
| "Add a new ENTSO-E data type" | `infrastructure_entsoe/mappers.py` (new `_parse_*` fn) → `client.py` (new `fetch_*`) → `data_cli/entsoe/services.py` (new `backfill_*`) → `data_cli/entsoe/backfill.py` (new Typer command) → `schedules/ingestion.py` (new task) |
| "Add a new model" | `price_forecasting/models/<name>.py` (subclass appropriate base) → register in `models/__init__.py` `MODEL_REGISTRY` → expose via re-export |
| "Add a new feature transformer" | `price_forecasting/data/transformers.py` (subclass `FeatureTransformer`) → set via `ExperimentConfig.feature_transformers` |
| "Add a new target scaler" | `price_forecasting/data/<name>_scaler.py` (sklearn-compatible fit/transform/inverse_transform) → register in `DataPreprocessor._build_target_scaler` → reference via `ExperimentConfig.target_scaler` |
| "Add a new ClickHouse column" | new migration `00N_*.sql` (ADD COLUMN IF NOT EXISTS) → update `queries.py` SELECT lists → update `ingest.py` insert function signature (kw-only, with default) |
| "Add a new area to ingestion" | append to `AREAS` in `deploy_ingestion.py`, rerun |
| "Add a new forecast config" | new file in `configs/`, append to `FORECAST_CONFIGS` in `deploy_forecast.py`, rerun |
| "Investigate a flow failure" | Prefect UI → flow run logs; then Loki via Operational Grafana dashboard for structured fields |
| "Tune LEAR hyperparams" | `ExperimentConfig.model_params={"alpha": ...}` or `{"alpha": None}` for LassoCV |
| "Tune DNN hyperparams" | Set `val_start_date`/`val_end_date` on the config → `uv run python -m forecast_cli.main tune <config>` → paste `best_params` into `model_params` (rename `n_neurons` → `hidden_units`) |
| "Change drift window sizes" | `schedules/drift.py` constants `REFERENCE_DAYS`, `CURRENT_DAYS`, `MIN_SAMPLE_SIZE` |
| "Enable drift-triggered retrain for a config" | Set `retrain_on_drift=True` on the `ExperimentConfig` |
| "Add a Grafana alert rule" | Edit `grafana/provisioning/alerting/rules.yaml` (YAML, NOT the UI) |
| "Diagnose a Slack alert / silence dev alerts" | Unset `SLACK_WEBHOOK_URL` → `alerting.notify` no-ops; see `docs/RUNBOOK.md` for full response playbook |
| "Compare two models statistically" | `price_forecasting/evaluation/statistical_tests.py` (DM, multivariate GW) + `compute_dm_pvalue_matrix` for >2 models |
| "Understand a metrics number" | `price_forecasting/evaluation/metrics.py` (per-array) + `summary.py` (wide-format) |

---

## 16. Things this doc does NOT cover

Read these directly when relevant:

- **`CLAUDE.md`** — hard project rules (this doc summarizes them, but
  `CLAUDE.md` is canonical for conventions).
- **`DEPLOYMENT.md`** — one-time host setup, Tailscale ACL JSON, manual
  redeploy commands, network-troubleshooting incantations.
- **`docs/RUNBOOK.md`** — alert response playbook: what each Slack /
  Grafana alert means and the standard recovery steps.
- **`docs/CONTRIBUTING.md`** — contributor setup, conventions summary,
  PR checklist.
- **Per-package `README.md`** — each `src/<package>/README.md` has the most
  recent module-specific docs.
- **`researh_material/`** — research notes, MLOps SLR plan, the LEAR paper
  itself. The MLOps execution plan in particular drives the roadmap (P1–P9).
  Reading guides under `researh_material/reading_guides/` are the canonical
  per-paper synthesis with codebase pointers.
- **`grafana/dashboards/*.json`** — exact panel queries and thresholds.
- **`grafana/provisioning/alerting/rules.yaml`** — file-provisioned alert
  rule definitions.
- **`memory/MEMORY.md`** — auto-memory index (user preferences, project
  state, dead code candidates).

---

## 17. Update protocol

This file is **load-bearing context**: future sessions read it instead of
the codebase. Keep it accurate.

- **Update when** a new top-level subsystem is added, a migration changes a
  schema, a new model type lands in the registry, a new flow / deploy
  script is added, the curve naming convention changes, or a new
  observability target is wired in.
- **Don't update for**: routine bug fixes, hyperparameter tweaks,
  in-progress experiments. Those live in `memory/` or the relevant config
  file.
- **Strip stale references** rather than leaving them in. A wrong pointer
  is worse than no pointer.
- **Refresh the "Last refreshed against commit" line** at the top when you
  make a substantive update.

Section-level edits are preferred over wholesale rewrites — keep the
structure consistent so future diffs are reviewable.
