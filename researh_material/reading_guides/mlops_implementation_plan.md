# MLOps Implementation Plan — Electricity Price Forecasting Platform

## Context

This plan addresses the gaps identified by systematically reviewing 9 MLOps best practices (P1-P9) from Zarour et al. (2025) "MLOps best practices, challenges and maturity models: A systematic literature review", mapped against the current codebase. The goal is an MVP for DK1 area with LEAR model that is easy to extend for DNN/Transformer models and additional areas.

**Current maturity:** Google Level 1 / Microsoft Level 1-2
**Target maturity after MVP:** Google Level 2 / Microsoft Level 2-3

---

## Progress

### Phase 0: Foundation — DONE (2026-04-06)

- Created `src/schedules/src/schedules/forecast.py` — Prefect flow with 3 tasks (load config, predict with retries, track prediction). Defaults to tomorrow. Daily cron.
- Created `src/schedules/src/schedules/deploy_forecast.py` — Deploys forecast flow with daily 06:00 UTC cron, DK1 only. Mounts `configs/` as Docker volume (no image rebuild on config change).
- Modified `src/forecast_cli/src/forecast_cli/config_loader.py` — Added early check for missing `configs/` directory with Docker-specific error message.
- All 238 tests pass.

**Deploy with:**
```bash
docker build -t algo-repo:latest .
PREFECT_API_URL="http://localhost:4200/api" uv run python src/schedules/src/schedules/deploy_forecast.py
```

---

### Phase 1: Metadata & Storage — DONE (2026-04-10)

- Created `migrations/005_create_model_artifacts_table.sql` — `algo.model_artifacts` table storing base64-encoded joblib blobs (`artifact_id`, `run_id`, `area`, `model_type`, `config_name`, `artifact_blob`, `artifact_size_bytes`). `ReplacingMergeTree(created_utc)` ordered by `artifact_id`.
- Created `migrations/006_alter_experiment_runs_add_columns.sql` — single ALTER adding `training_duration_seconds`, `data_start_utc`, `data_end_utc`, `model_artifact_id` to `algo.experiment_runs` with sensible defaults.
- Modified `infrastructure_clickhouse/ingest.py` — extended `insert_experiment_run()` with keyword-only params for the 4 new columns (backward compatible). Added `insert_model_artifact()`.
- Modified `infrastructure_clickhouse/queries.py` — added `load_latest_artifact(area, model_type, config_name)`.
- Modified `price_forecasting/live_runner.py` — added `LiveResult` dataclass (`prediction`, `data_start_utc`, `data_end_utc`, `training_duration_seconds`, `trained_models`) and `run_live_with_metadata()`. Existing `run_live()` delegates for backward compatibility.
- Modified `price_forecasting/__init__.py` — re-exported `LiveResult`.
- Modified `forecast_cli/tracking.py` — added `_serialize_model()` (joblib + base64), extended `track_prediction()` to serialize the trained ensemble, insert the artifact row, and link `model_artifact_id` to the run.
- Modified `schedules/forecast.py` — `predict_task` returns `LiveResult`; `track_prediction_task` forwards metadata kwargs.
- All 238 tests pass.

---

### Phase 2: Reconciliation — DONE (2026-04-10)

- Modified `infrastructure_clickhouse/queries.py` — added three query functions:
  - `get_unreconciled_runs(client)` — all 11 columns of runs where `metrics_json = '{}'` (backtests are untouched).
  - `get_predictions_for_runs(client, run_ids)` — batch prediction fetch, `IN {Array(String)}` parameterized.
  - `get_actual_prices_for_period(client, area, start_utc, end_utc)` — matches `ENTSOE {area} EnergyPrice %` in `algo.timeseries`.
- Created `src/schedules/src/schedules/reconciliation.py` — Prefect flow `reconcile_predictions_flow`:
  - `find_unreconciled_runs_task` pulls candidate runs.
  - `reconcile_area_task(area, runs)` batches queries **by area** (one predictions query + one actuals query, no N+1), matches each prediction timestamp to an actual, skips any run with a missing hour (retried tomorrow), computes MAE/RMSE/sMAPE from flat `np.ndarray`s, re-inserts the predictions (with actuals) and the `experiment_runs` row (with updated `metrics_json` and newer `created_utc` so `ReplacingMergeTree(created_utc)` keeps it as the winning row). All other columns preserved.
- Modified `src/schedules/src/schedules/deploy_forecast.py` — added `reconcile-predictions` deployment at cron `0 18 * * *` (4h after ENTSO-E day-ahead publication ~14:00 UTC). Reuses existing `ForecastFlowDeployment` class.
- Migrations 005 + 006 applied against ClickHouse. Both deployments (`daily-forecast-dk1_lear`, `reconcile-predictions`) registered in Prefect.
- All 238 tests pass.

**Design decisions:**
1. Two-step query batching by area avoids N+1.
2. All-or-nothing reconciliation — partial metrics would be misleading vs backtest metrics.
3. Metrics computed from flat arrays (`calculate_mae/rmse/smape`), not the wide-format `compute_metrics_summary()` which is multi-day backtest-oriented.
4. Update via re-insert with newer `created_utc` — no `UPDATE`, no `OPTIMIZE FINAL`. `FINAL` keyword handles reads.
5. Deployed in the existing `deploy_forecast.py` rather than a separate file — `ForecastFlowDeployment` is already generic.

**This closes P6 (Continuous Training & Evaluation)** and feeds the data Phase 3 (Grafana Model Performance dashboard) will need.

**Trigger manually:**
```bash
prefect deployment run 'reconcile-predictions/reconcile-predictions'
```

---

### Phase 5: CI/CD & Polish — DONE (2026-04-20)

- Created `tests/price_forecasting/test_smoke.py` — two smoke tests (hourly 24-period and quarter-hourly 96-period) that fit a real `LearModel` on synthetic data from the existing `make_synthetic_features_and_targets()` helper and assert shape + finiteness. Runs in <0.1s, no network.
- Created `.github/workflows/cd_deploy.yml` — fires on push to `main`. Uses `tailscale/github-action@v2` with OAuth (`tag:ci`) to join the tailnet from an `ubuntu-latest` runner, then uses Tailscale SSH (no keypair) to run `git reset --hard origin/main`, `docker build`, and both `deploy_*.py` scripts on the host. A second step triggers `daily-forecast/daily-forecast-dk1_lear` via `prefect deployment run`, polls `prefect flow-run inspect` every 15s, and fails the job if the run does not reach `COMPLETED` within 10 minutes.
- Modified `DEPLOYMENT.md` — full rewrite covering Phases 0–5: updated architecture diagram (Loki + Grafana), migration list (001–007), `deploy_forecast.py` registration, observability section, and Tailscale OAuth + ACL one-time setup including the five required GH secrets (`TS_OAUTH_CLIENT_ID`, `TS_OAUTH_SECRET`, `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_REPO_PATH`).
- Modified `CLAUDE.md` — added Phase 0–4 conventions: forecast/reconciliation/drift deployments, model artifact storage (`algo.model_artifacts`, `load_latest_artifact`), `LiveResult` metadata, reconciliation via re-insert with newer `created_utc`, Loki logging via `logging_setup` (no `print()`), Evidently in-process drift flow, CI/CD workflow summary. Added manual-trigger commands for the three new flows.
- Modified `docker-compose.yml` — deleted the 5-line `model-store` volume TODO (superseded by ClickHouse blob storage in Phase 1).
- All 240 tests pass (238 existing + 2 new smoke tests).

**Design decisions:**
1. Tailscale SSH over keypair-SSH — cleaner ACL model, short-lived per-run auth, no long-lived secrets.
2. Ephemeral tailnet nodes via OAuth — auto-deregister, no device-count drift on the free plan.
3. GitHub-hosted runner over self-hosted — avoids PR-triggered code execution on the deploy host.
4. Integration smoke runs `daily-forecast/daily-forecast-dk1_lear` with a fixed historical date, not a dedicated test flow — same path as production, no parallel validation surface to maintain.
5. `concurrency: cd-deploy, cancel-in-progress: false` — queue rapid merges instead of killing in-flight deploys.

**One-time host setup required before first CD run:** `tailscale up --ssh`, OAuth client in tailnet admin with `tag:ci` tagOwner, ACL `ssh` rule allowing `tag:ci` to SSH as the deploy user, and the five GitHub repository secrets. Steps documented in `DEPLOYMENT.md` § CI/CD.

---

## 1. Per-Practice Detail (P1-P9)

---

### P1 — Automating CI/CD

**Current State:**
- GitHub Actions: `pr_test.yml` (pytest on PR), `pr_ruff-lint.yaml` (ruff on PR)
- No model smoke tests, no CD for Prefect deployments

**What Needs to Be Done:**
1. Add model smoke test to `tests/price_forecasting/test_smoke.py` — fit LearModel on tiny synthetic data, call `predict_day()`. Already picked up by existing `pytest tests/` in CI.
2. Add CD workflow `.github/workflows/cd_deploy.yml` — on merge to main: rebuild Docker image, re-register Prefect deployments via `deploy_ingestion.py` + `deploy_forecast.py`.

**Technology:** GitHub Actions (already in use)
**Rejected:** Jenkins, GitLab CI — already on GitHub Actions, no reason to switch.

**Files:**
- Create: `tests/price_forecasting/test_smoke.py`, `.github/workflows/cd_deploy.yml`
- Modify: none

**Depends on:** P2 (needs `deploy_forecast.py` to exist)

---

### P2 — Orchestrating Workflows

**Current State:**
- Prefect orchestrates ingestion (hourly cron, 7 areas) — working
- `schedules/forecast.py` is **EMPTY** — most critical gap in the entire system
- Forecasting is manual-only via `forecast_cli predict`

**What Needs to Be Done:**
1. **Implement `forecast.py`** as a Prefect flow — accepts `config_name` + `target_date`, uses `LiveRunner`, stores via `tracking.track_prediction()`, default target = tomorrow (day-ahead convention)
2. **Create `deploy_forecast.py`** — mirrors `deploy_ingestion.py`, cron `0 6 * * *` (06:00 UTC daily), MVP: DK1 only, same Docker image + network pattern
3. Architecture: separate cron (NOT chained to ingestion). Future live-trigger possible — flow signature already supports it.

**Technology:** Prefect (already in use)
**Rejected:**
- Airflow — heavier (separate metadata DB, webserver, scheduler). Prefect already running.
- Dagster — would require rewriting existing ingestion flows.
- Kubeflow — requires Kubernetes. Single machine, one GPU, Docker Compose.

**Files:**
- Create: `src/schedules/src/schedules/forecast.py`, `src/schedules/src/schedules/deploy_forecast.py`
- Modify: `src/forecast_cli/src/forecast_cli/config_loader.py` (config path resolution in Docker)

**Depends on:** Nothing — this is the foundation that unblocks P6, P7, P8, P9

---

### P3 — Ensuring Reproducibility

**Current State:** Strong — `ExperimentConfig`, git-tracked configs, `uv.lock`, date-based splits, ClickHouse tracking, Docker containers via Prefect.

**What Needs to Be Done:**
1. Minor: log git commit SHA in experiment metadata — link every prediction to exact code version
2. Everything else comes for free when `forecast.py` runs in Prefect's Docker worker

**Technology:** Existing stack (Git + uv.lock + Docker + ExperimentConfig)
**Rejected:** DVC (data in ClickHouse not files), MLflow (redundant with Docker + uv.lock)

**Files:**
- Modify: `src/schedules/src/schedules/forecast.py` (add git SHA capture), optionally `Dockerfile` (bake SHA as build arg)

**Depends on:** P2

---

### P4 — Versioning

**Current State:**
- Code: Git (complete)
- Data: None — but ClickHouse data is append-only with deduplication
- Model artifacts: None — retrained from scratch every run. `docker-compose.yml` has a `model-store` volume TODO (never implemented)

**What Needs to Be Done:**
1. **Create `algo.model_artifacts` table** — store serialized model as ClickHouse blob (base64-encoded joblib bytes). Schema: `artifact_id`, `created_utc`, `run_id`, `area`, `model_type`, `config_name`, `artifact_blob`, `artifact_size_bytes`
2. **Add `data_start_utc`/`data_end_utc` to `algo.experiment_runs`** — records exact data window per run
3. **Add `model_artifact_id` to `algo.experiment_runs`** — links run to stored artifact
4. **Implement save/load functions** — `insert_model_artifact()`, `load_latest_artifact()`
5. **Remove `model-store` volume TODO** from docker-compose.yml

**Technology:** ClickHouse blob storage
**Rejected:**
- DVC — data in ClickHouse not files
- MLflow Registry — overkill at 1 config. Revisit at ~10+ configs.
- Local disk / Docker volume — ClickHouse keeps everything queryable in one place
- Note: ClickHouse blob works for small LEAR models (~100KB). Revisit for large DNN/Transformer weights.

**Files:**
- Create: `migrations/005_create_model_artifacts_table.sql`, `migrations/006_alter_experiment_runs_add_columns.sql`
- Modify: `infrastructure_clickhouse/ingest.py`, `infrastructure_clickhouse/queries.py`, `forecast_cli/tracking.py`

**Depends on:** P7 (new columns feed metadata tracking)

---

### P5 — Collaboration & Communication

**Current State:** Solo developer. Git + GitHub + CLAUDE.md + DEPLOYMENT.md.

**What Needs to Be Done:** Nothing. N/A at current team size.

**Revisit when:** Team grows. Then add shared Grafana dashboards (from P8), PR templates, Slack notifications.

---

### P6 — Continuous Training & Evaluation

**Current State:**
- `BacktestEngine` with `refit_interval_days` — manual only
- `LiveRunner` retrains from scratch every call
- Live predictions store `actual=0.0` — never backfilled

**What Needs to Be Done:**
1. **Solved by P2** — daily `forecast.py` cron IS continuous training. LEAR retrains daily by design.
2. **Reconciliation flow** — standalone `reconciliation.py` Prefect flow, runs daily after actuals are published (e.g., 18:00 UTC):
   - Query `algo.experiment_predictions` for rows where `actual = 0.0` and `timestamp_utc < now()`
   - Fetch actual prices from `algo.timeseries`
   - Re-insert with real actuals (ReplacingMergeTree deduplication handles the update)
3. **Evaluation after reconciliation** — compute live MAE/RMSE/sMAPE, store in `metrics_json`

**Technology:** Prefect (same as P2)
**Rejected:** Kubeflow, SageMaker, Vertex AI — cloud/Kubernetes, single GPU + Docker Compose is the constraint

**Files:**
- Create: `src/schedules/src/schedules/reconciliation.py`
- Modify: `infrastructure_clickhouse/queries.py` (add `get_unreconciled_predictions()`, `get_actual_prices_for_timestamps()`), `forecast_cli/tracking.py` (add `reconcile_actuals()`)

**Depends on:** P2 (forecast flow must exist), P7 (reconciled actuals feed metadata), P8 (reconciled actuals enable dashboards)

---

### P7 — Track & Log ML Metadata

**Current State:**
- `algo.experiment_runs`: run_id, created_utc, experiment_name, area, model_type, config_json, metrics_json
- `algo.experiment_predictions`: run_id, timestamp_utc, actual, predicted
- No structured logging — `print()` statements, ENTSOE client silently swallows HTTP errors

**What Needs to Be Done:**

#### ML Metadata Enhancements
1. Add `training_duration_seconds` to `experiment_runs` (new migration)
2. Add `data_start_utc`/`data_end_utc` (shared with P4 migration)
3. Add `model_artifact_id` (shared with P4)
4. Fix `actual=0.0` in live predictions (solved by P6 reconciliation)

#### Structured Logging via Loki
5. Add Loki to `docker-compose.yml`
6. Integrate `python-logging-loki` — direct push, no Promtail
7. Instrument modules by priority:

| Priority | Module | Why |
|----------|--------|-----|
| CRITICAL | `infrastructure_entsoe/client.py` | HTTP errors silently `continue` — must log failed requests, status codes, retries |
| HIGH | `schedules/ingestion.py` | Replace `print()` with structured logging |
| HIGH | `schedules/forecast.py` | Build with logging from day one |
| HIGH | `infrastructure_clickhouse/ingest.py` | Log insert failures, batch sizes |
| LOW | `forecast_cli/`, `data_cli/` | CLI tools — `typer.echo()` is fine for interactive use |
| NONE | `domain/` | Pure models, no I/O |

**Technology:** ClickHouse (ML metadata) + Loki (structured logging)
**Rejected:**
- MLflow Tracking — overkill at 1 config, would replace working ClickHouse tracking
- W&B/Neptune — deferred, not rejected (see below)
- ELK Stack — massively overengineered, Loki does the job
- Promtail — `python-logging-loki` pushes directly, no sidecar needed

**Files:**
- Create: `infrastructure_clickhouse/logging_setup.py` (Loki handler config)
- Modify: `docker-compose.yml` (add Loki), `pyproject.toml` (add `python-logging-loki`), `infrastructure_entsoe/client.py`, `schedules/ingestion.py`, `schedules/forecast.py`

**Depends on:** P4 (shared migrations), P8 (Loki logs displayed in Grafana)

---

### P8 — Continuous Monitoring

**Current State:** Nothing. No Grafana, no dashboards, no drift detection.

**What Needs to Be Done:**

#### Infrastructure
1. Add Grafana to `docker-compose.yml` (port 3000)
2. Auto-provision ClickHouse + Loki as datasources via `grafana/provisioning/datasources/datasources.yml`

#### Dashboard 1: Data Quality (ClickHouse datasource)
3. Data freshness — max `timestamp_utc` per area/curve. Alert if >3 hours old.
4. Row count trends — daily counts per table. Detect anomalies.
5. Null/missing value detection — count `value = 0` or NULL per area per day.

#### Dashboard 2: Model Performance (ClickHouse datasource)
6. Daily MAE/RMSE/sMAPE — time series over last 30 days (requires P6 reconciliation)
7. Predicted vs Actual overlay — 24-hour comparison chart
8. Prediction coverage — are predictions being generated daily?

#### Dashboard 3: Operational (Loki datasource)
9. Live log stream — filter by severity
10. Error rate — count of ERROR-level entries over time

#### Drift Detection: Evidently AI
11. Install `evidently` — Mode 1 (report generation, no server)
12. Implement as Prefect task in `drift.py` — compare current week's distributions vs reference
13. Store drift scores in `algo.drift_reports` table
14. Grafana alert on drift exceeding threshold

**MVP Scope:** DK1 only. Extend to other areas via Grafana variable.

**Technology:** Grafana + ClickHouse datasource + Loki datasource + Evidently AI
**Rejected:**
- Prometheus — infrastructure metrics only, critical metrics are in ClickHouse. Revisit if infra monitoring needed.
- Arize/WhyLabs — cloud-hosted, data leaves machine. Evidently is open source + self-hosted.
- Datadog — cloud, paid, overkill
- Tempo — Prefect UI already covers task timing

**Files:**
- Create: `grafana/provisioning/datasources/datasources.yml`, `src/schedules/src/schedules/drift.py`, `migrations/007_create_drift_reports_table.sql`
- Modify: `docker-compose.yml` (add Grafana), `pyproject.toml` (add `evidently`)

**Depends on:** P2 (predictions must exist), P6 (actuals must be reconciled), P7 (Loki must be running)

---

### P9 — Implementing Feedback Loops

**Current State:** Nothing.

**What Needs to Be Done (MVP = Log + Alert Only):**
1. Drift detection (from P8) triggers WARNING-level Loki log with drift details
2. Grafana alert fires on drift — email/webhook notification
3. Manual intervention — developer investigates, decides action

**Why log-only for MVP:**
- Auto-retrain adds complexity (validation, bad data risk)
- LEAR already retrains daily — drift likely means window adjustment, not more frequent retraining
- Observability first: understand drift patterns before automating responses

**Future (post-MVP):**
- Add `auto_retrain_on_drift: bool = False` to `ExperimentConfig`
- Champion/challenger pattern: retrain, backtest, only deploy if metrics improve
- This becomes critical when DNN/Transformer models are added (expensive to retrain)

**Technology:** Loki (logging) + Grafana Alerting (notification)

**Files:**
- Modify: `src/schedules/src/schedules/drift.py` (add Loki logging for drift events)
- Future: `src/price_forecasting/src/price_forecasting/configs/experiment.py` (add `auto_retrain_on_drift`)

**Depends on:** P8 (drift detection must exist), P7 (Loki), P6 (reconciled actuals)

---

## 2. Updated Px Table

| # | Concept | Current Tools | Planned Tools (after MVP) | Status Change |
|---|---------|---------------|---------------------------|---------------|
| P1 | CI/CD | GitHub Actions (pytest + ruff) | GitHub Actions (+ model smoke test + CD deploy) | Partial -> Functional |
| P2 | Workflow Orchestration | Prefect (ingestion only), Typer CLI | Prefect (ingestion + daily forecast + reconciliation) | Partial -> Complete |
| P3 | Reproducibility | Git + uv.lock + ExperimentConfig + Docker | Same (+ git SHA in metadata) | Strong -> Strong |
| P4 | Versioning | Git (code + configs only) | Git + ClickHouse blob (model artifacts) + data window columns | Partial -> Complete |
| P5 | Collaboration | Git + GitHub + CLAUDE.md | Same (N/A for solo dev) | N/A -> N/A |
| P6 | Continuous Training | Manual CLI only | Prefect daily cron + reconciliation flow | Missing -> Automated |
| P7 | ML Metadata & Logging | ClickHouse tables (basic) + print() | ClickHouse tables (enhanced) + Loki (structured logging) | Basic -> Comprehensive |
| P8 | Monitoring | None | Grafana (3 dashboards) + Evidently AI (drift detection) | Missing -> Operational |
| P9 | Feedback Loops | None | Loki alerts + Grafana alerting (log + alert only, no auto-retrain) | Missing -> Observable |

---

## 3. Critical Implementation Order

### Phase 0: Foundation (Day 1-2) — Unblocks Everything

**Goal:** Automated daily forecasting running.

| Step | Task | Files |
|------|------|-------|
| 0.1 | Implement `forecast.py` Prefect flow | `src/schedules/src/schedules/forecast.py` |
| 0.2 | Create `deploy_forecast.py` | `src/schedules/src/schedules/deploy_forecast.py` |
| 0.3 | Test flow locally (no Prefect server) | Run `forecast.py` directly |
| 0.4 | Handle config path in Docker | `src/forecast_cli/src/forecast_cli/config_loader.py` |

**Validation:** `algo.experiment_predictions` has new rows daily without manual intervention.

---

### Phase 1: Metadata & Storage (Day 3-5)

**Goal:** Enrich what gets stored so monitoring has data to query.

| Step | Task | Files |
|------|------|-------|
| 1.1 | Create `005_create_model_artifacts_table.sql` | `migrations/` |
| 1.2 | Create `006_alter_experiment_runs_add_columns.sql` | `migrations/` |
| 1.3 | Update `insert_experiment_run()` for new columns | `ingest.py` |
| 1.4 | Add `insert_model_artifact()` + `load_latest_artifact()` | `ingest.py`, `queries.py` |
| 1.5 | Update `forecast.py` to save artifacts + enhanced metadata | `forecast.py` |
| 1.6 | Update `tracking.py` to pass new fields | `tracking.py` |

**Validation:** `algo.experiment_runs` rows have non-null `data_start_utc`, `training_duration_seconds`, and `model_artifact_id`.

---

### Phase 2: Reconciliation (Day 6-8)

**Goal:** Backfill actual prices so we can measure accuracy.

| Step | Task | Files |
|------|------|-------|
| 2.1 | Implement reconciliation flow | `src/schedules/src/schedules/reconciliation.py` |
| 2.2 | Add queries for unreconciled predictions | `queries.py` |
| 2.3 | Add reconciliation logic | `tracking.py` or new module |
| 2.4 | Deploy reconciliation flow (daily, 18:00 UTC) | `deploy_forecast.py` |
| 2.5 | Compute and store live metrics after reconciliation | `reconciliation.py` |

**Validation:** `algo.experiment_predictions` rows from previous days have non-zero `actual` values.

---

### Phase 3: Observability Stack (Day 9-13)

**Goal:** Loki + Grafana + structured logging + dashboards.

| Step | Task | Files |
|------|------|-------|
| 3.1 | Add Loki to `docker-compose.yml` | `docker-compose.yml` |
| 3.2 | Add Grafana to `docker-compose.yml` | `docker-compose.yml` |
| 3.3 | Provision datasources (ClickHouse + Loki) | `grafana/provisioning/datasources/datasources.yml` |
| 3.4 | Create logging setup module | `infrastructure_clickhouse/logging_setup.py` |
| 3.5 | Instrument `infrastructure_entsoe/client.py` (CRITICAL) | `client.py` |
| 3.6 | Instrument `schedules/ingestion.py` | `ingestion.py` |
| 3.7 | Instrument `schedules/forecast.py` | `forecast.py` |
| 3.8 | Add `python-logging-loki` dependency | `pyproject.toml` |
| 3.9 | Build Data Quality dashboard | Grafana |
| 3.10 | Build Model Performance dashboard | Grafana |
| 3.11 | Build Operational dashboard | Grafana |

**Validation:** Grafana at `localhost:3000` shows three dashboards. Loki receives structured logs.

---

### Phase 4: Drift Detection & Alerts (Day 14-16)

**Goal:** Detect data and model drift, alert on anomalies.

| Step | Task | Files |
|------|------|-------|
| 4.1 | Add `evidently` dependency | `pyproject.toml` |
| 4.2 | Create `007_create_drift_reports_table.sql` | `migrations/` |
| 4.3 | Implement drift detection flow | `src/schedules/src/schedules/drift.py` |
| 4.4 | Log drift events to Loki | `drift.py` |
| 4.5 | Add drift panel to Grafana | Grafana |
| 4.6 | Configure Grafana alerts | Grafana |

**Validation:** Weekly drift reports appear in ClickHouse. Simulated drift triggers a Grafana alert.

---

### Phase 5: CI/CD & Polish (Day 17-19) — Parallelizable with Phase 3-4

**Goal:** Automate deployment, add safety nets, update docs.

| Step | Task | Files |
|------|------|-------|
| 5.1 | Write model smoke test | `tests/price_forecasting/test_smoke.py` |
| 5.2 | Create CD workflow | `.github/workflows/cd_deploy.yml` |
| 5.3 | Update `DEPLOYMENT.md` | `DEPLOYMENT.md` |
| 5.4 | Update `CLAUDE.md` | `CLAUDE.md` |
| 5.5 | Remove `model-store` volume TODO | `docker-compose.yml` |

**Validation:** Merge to `main` auto-rebuilds Docker image and re-deploys Prefect flows.

---

### Phase Summary

```
Phase 0 (Day 1-2)   ████ Foundation      -> Automated daily forecasting
Phase 1 (Day 3-5)   ████ Metadata        -> Rich experiment tracking + model storage
Phase 2 (Day 6-8)   ████ Reconciliation   -> Actual vs predicted comparison
Phase 3 (Day 9-13)  ████ Observability    -> Loki + Grafana + dashboards
Phase 4 (Day 14-16) ████ Drift Detection  -> Evidently + alerts
Phase 5 (Day 17-19) ████ CI/CD + Polish   -> Automated deployment + docs
```

**Critical path:** Phase 0 -> Phase 1 -> Phase 2 -> Phase 3 -> Phase 4
Phase 5 can run in parallel with Phases 3-4.

**After MVP — extending the system:**
- More areas: Add entries to `AREAS` list in `deploy_forecast.py` + create config files. No code changes.
- DNN model: Implement `DNNModel` in `models/dnn.py`, create config, deploy. Entire pipeline works unchanged. Add W&B for training curve monitoring.
- Transformer model: Same as DNN — add to `MODEL_REGISTRY`, create config, deploy.

---

## Future TODOs

### 15-Minute Evaluation Granularity

**Context:** Most European power markets (including DK1 via ENTSO-E) allow bidding on 15-minute intervals, not just hourly. Currently, the model predicts at hourly resolution and actuals are reconciled at hourly resolution. This means reported metrics (MAE/RMSE/sMAPE) do not reflect the true financial exposure of a 15-minute bidding strategy.

**What this means:**
- The **model stays hourly** — no change to `LiveRunner`, `ExperimentConfig`, or the prediction pipeline.
- The **reconciliation and evaluation should be against 15-minute actuals** — fetch 15-min `ENTSOE {area} EnergyPrice 15min %` curves from `algo.timeseries`, compare each predicted hourly value against the four 15-min actuals within that hour (or use the mean, depending on how the bid is structured), and compute metrics over all 96 periods/day rather than 24.
- This gives metrics that accurately represent real-world P&L: a flat hourly bid is exposed to all four 15-min settlement prices within each hour.

**What needs to change when implementing:**
- `reconciliation.py` — `get_actual_prices_for_period()` must fetch 15-min curve; expand each hourly prediction to 4 rows (one per 15-min slot) before computing metrics.
- `algo.experiment_predictions` schema — already supports sub-hourly `timestamp_utc`; no migration needed.
- `queries.py` — `get_actual_prices_for_period()` needs a `resolution` parameter or separate function for 15-min curves.
- Grafana — update the predicted-vs-actual overlay panel to show 15-min granularity.

**Why deferred:** Requires 15-min price data to be consistently ingested first. Validate ingestion coverage before changing evaluation logic.

---

## 4. Software Overview

### Currently Used

| Software | What It Does | Problem It Solves | Where Used |
|----------|-------------|-------------------|------------|
| Python 3.14 | Runtime language | Core development | Everywhere |
| uv | Package manager + workspace | Reproducible deps, monorepo | `pyproject.toml`, `uv.lock`, CI |
| Docker | Containerization | Reproducible environments, Prefect flow isolation | `Dockerfile`, `Dockerfile.worker` |
| Docker Compose | Multi-container orchestration | Run full stack as one unit | `docker-compose.yml` |
| ClickHouse 25.6.1 | Column-oriented OLAP database | Fast time-series queries, experiment tracking | All `algo.*` tables |
| clickhouse-connect | Python ClickHouse client | Insert/query via Arrow batching | `infrastructure_clickhouse/` |
| Prefect 3.x | Workflow orchestration | Schedule ingestion, retry on failure | `schedules/ingestion.py` |
| GitHub Actions | CI/CD | Automated testing + linting on PRs | `.github/workflows/` |
| scikit-learn | ML library | Lasso/LassoCV for LEAR model | `models/lear.py` |
| pandas | Data manipulation | Feature engineering, pivoting | `price_forecasting/data/`, `backtesting/` |
| polars | Data manipulation | Schema-enforced domain models, Arrow inserts | `domain/curves.py`, `ingest.py` |
| NumPy | Numerical computing | Array ops for model training | `models/`, `backtesting/engine.py` |
| httpx | HTTP client | ENTSOE API requests | `infrastructure_entsoe/client.py` |
| Typer | CLI framework | User-facing backfill + forecast commands | `data_cli/`, `forecast_cli/` |
| ruff | Linter/formatter | Code quality in CI | `.github/workflows/` |
| pytest | Testing | Unit/integration tests | `tests/`, CI |
| ratelimit | Rate limiting decorator | Respect ENTSOE API limits (400/60s) | `client.py` |
| python-dotenv | Env var loading | Load `.env` for credentials | `client_factory.py` |
| joblib | Serialization | Serialize trained Lasso models | `models/` (via scikit-learn) |

### New Software (to be added)

| Software | What It Does | Problem It Solves | Where Used | Phase |
|----------|-------------|-------------------|------------|-------|
| Grafana 11.6 | Dashboard + alerting | Visualize data quality, model performance, logs. Alert on anomalies. | `docker-compose.yml`, `localhost:3000` | 3 |
| Loki 3.4 | Log aggregation | Centralized structured logging. Replaces scattered `print()`. Queryable from Grafana. | `docker-compose.yml`, Python handler | 3 |
| python-logging-loki | Python Loki client | Push structured logs to Loki without Promtail sidecar | `client.py`, `schedules/*.py` | 3 |
| Evidently AI | ML drift detection | Detect distribution drift in features, predictions, targets. Generate reports. | `schedules/drift.py`, `algo.drift_reports` | 4 |
| grafana-clickhouse-datasource | Grafana plugin | Query ClickHouse from Grafana dashboards | Grafana provisioning | 3 |

### Future Software (deferred, not rejected)

| Software | When to Add | Why Deferred |
|----------|-------------|-------------|
| **W&B (Weights & Biases)** | When DNN/Transformer development starts | Live training curves, experiment comparison, hyperparameter sweeps. Not needed for LEAR (trains in seconds). Cloud free tier confirmed. |
| **MLflow** | When experiment configs grow to ~10+ | Experiment comparison UI. Current ClickHouse tracking sufficient at 1 config. |
| **Prometheus** | When infrastructure monitoring becomes necessary | Infrastructure metrics (CPU, memory). Critical metrics are domain-specific in ClickHouse. |

### Software Explicitly Rejected

| Software | Why Rejected |
|----------|-------------|
| DVC | Data in ClickHouse, not files. File-based versioning doesn't fit. |
| Airflow | Heavier than Prefect. Already running Prefect. |
| Kubeflow | Requires Kubernetes. Single machine, Docker Compose. |
| Kubernetes | Single machine, one GPU. Docker Compose sufficient. |
| Tempo | Distributed tracing. Prefect UI already covers task timing. |
| Promtail | `python-logging-loki` pushes directly. No sidecar needed. |
| ELK Stack | Overengineered. Loki does the job with less resources. |
| Arize / WhyLabs | Cloud-hosted monitoring. Data leaves machine. Evidently is open source. |
| SageMaker / Vertex AI | Cloud ML platforms. One GPU + Docker Compose is the constraint. |
| Datadog | Cloud, paid, overkill for solo project. |
| PagerDuty / OpsGenie | Solo developer. Grafana email/webhook alerts sufficient. |

---

## Appendix: Complete File Change Manifest

### New Files

| File | Phase | Purpose |
|------|-------|---------|
| `src/schedules/src/schedules/forecast.py` | 0 | Daily forecast Prefect flow |
| `src/schedules/src/schedules/deploy_forecast.py` | 0 | Deploy forecast flow to Prefect |
| `src/schedules/src/schedules/reconciliation.py` | 2 | Backfill actual prices into predictions |
| `src/schedules/src/schedules/drift.py` | 4 | Evidently drift detection flow |
| `migrations/005_create_model_artifacts_table.sql` | 1 | Model artifact blob storage |
| `migrations/006_alter_experiment_runs_add_columns.sql` | 1 | Enhanced metadata columns |
| `migrations/007_create_drift_reports_table.sql` | 4 | Drift detection results |
| `infrastructure_clickhouse/logging_setup.py` | 3 | Loki logging configuration |
| `tests/price_forecasting/test_smoke.py` | 5 | Model smoke test for CI |
| `.github/workflows/cd_deploy.yml` | 5 | CD workflow for post-merge deployment |
| `grafana/provisioning/datasources/datasources.yml` | 3 | Auto-provision Grafana datasources |

### Modified Files

| File | Phase | Changes |
|------|-------|---------|
| `docker-compose.yml` | 3 | Add Loki + Grafana services and volumes, remove model-store TODO |
| `pyproject.toml` | 3, 4 | Add `python-logging-loki`, `evidently` |
| `infrastructure_clickhouse/ingest.py` | 1 | Add `insert_model_artifact()`, update `insert_experiment_run()` |
| `infrastructure_clickhouse/queries.py` | 1, 2 | Add `load_latest_artifact()`, `get_unreconciled_predictions()` |
| `infrastructure_entsoe/client.py` | 3 | Add structured logging (replace silent `continue`) |
| `schedules/ingestion.py` | 3 | Replace `print()` with structured logging |
| `forecast_cli/tracking.py` | 1, 2 | Pass new metadata fields, add `reconcile_actuals()` |
| `forecast_cli/config_loader.py` | 0 | Handle config path in Docker containers |
| `DEPLOYMENT.md` | 5 | Document new services |
| `CLAUDE.md` | 5 | Document new conventions |
