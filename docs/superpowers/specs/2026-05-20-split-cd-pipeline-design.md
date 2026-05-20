# Split CD Pipeline — Design

**Date:** 2026-05-20
**Status:** Draft, pending review
**Touches:** `.github/workflows/`, `tests/smoke/`

## 1. Problem

Today, `.github/workflows/cd_deploy.yml` runs the *entire* deploy on every push to `main`: rebuild the flow image, rerun both `deploy_*.py` scripts, trigger a smoke flow. This happens even when nothing relevant changed — a tweak to `researh_material/`, `docs/`, or a README still triggers a full rebuild + redeploy.

Two problems follow:

1. **Wasted cycles.** Most commits don't touch code that goes into `algo-repo:latest`, yet trigger a 5–10 min rebuild + redeploy.
2. **No PR-time integration testing.** The smoke flow only runs *after* merge, against real prod. Regressions in flow registration, image build, or end-to-end forecast→reconciliation flow surface only post-merge.

This spec splits CD into selective jobs gated by path filters, and adds a PR-time smoke that exercises forecast + reconciliation end-to-end against an ephemeral stack.

## 2. Decisions (locked in during brainstorming)

| # | Decision | Rationale |
|---|---|---|
| 1 | PR smoke runs on the **GitHub-hosted runner** (`ubuntu-latest`, 2 vCPU / 7 GB), not on the prod host | Isolation is free, no schema/image refactor needed, host stays uncoupled from PR feedback loop |
| 2 | PR smoke scope: **forecast + reconciliation** end-to-end. No migrations validation (manual). No ingestion (no real ENTSO-E in PR) | Catches the highest-value integration regressions; fixtures stay manageable |
| 3 | CD scope: image rebuild + Prefect deploy script reruns + Grafana auto-reload + `configs/` new-file detection. **Migrations and `docker-compose.yml` stay manual** | Auto-running migrations on `main` is too risky; compose changes are rare and operationally sensitive |
| 4 | Single workflow file (`cd_deploy.yml`) with `dorny/paths-filter` gating | Ordering matters across slices; single workflow keeps the success/failure signal in one run |
| 5 | Image tag stays `algo-repo:latest` | SHA tagging + rollback is a separate, valuable project — not bundled into this spec |
| 6 | Migrations stay manual | Bad migration against years of CH data is the kind of thing that needs a human watching |

## 3. Architecture

```
.github/workflows/
├── cd_deploy.yml       (REWRITTEN — selective jobs gated by paths-filter)
├── pr_smoke.yml        (NEW — runner-side compose stack smoke)
├── pr_test.yml         (unchanged — pytest)
└── pr_ruff-lint.yaml   (unchanged — ruff)

tests/smoke/            (NEW)
├── __init__.py
├── fixtures.py         (synthetic Polars frames: prices + 1 exogenous curve)
└── seed.py             (entrypoint: connects to CH on localhost, inserts fixtures)
```

### Key non-isolation caveat

The flow image `algo-repo:latest` is **shared across ingestion, forecast, reconciliation, drift, retrain**. "Selective deploy" means skipping unnecessary *rebuilds* and *registration reruns* — it does **not** isolate slices at runtime. A forecast-only code change still affects ingestion's next scheduled run, because ingestion uses the same image. This is a property of the existing architecture, unchanged by this spec.

## 4. `cd_deploy.yml` — rewritten

### Trigger

```yaml
on:
  push:
    branches: [main]

concurrency:
  group: cd-deploy
  cancel-in-progress: false
```

### Job graph

```
on push to main
        │
        ▼
┌──────────────┐
│   changes    │  dorny/paths-filter v3, outputs booleans
└──────┬───────┘
       │
   ┌───┴────────────────────┬────────────────┐
   ▼                        ▼                ▼
┌────────────┐         ┌──────────┐    ┌──────────────┐
│ build_image│         │ grafana  │    │   (skip all) │
│ if: image  │         │_reload   │    │ if all false │
│  || shared │         │if:grafana│    └──────────────┘
└─────┬──────┘         └──────────┘
      │
  ┌───┴────────────────────────────────┐
  ▼                                    ▼
┌─────────────────────┐    ┌──────────────────────┐
│ deploy_ingestion    │    │ deploy_forecast      │
│ if: ingestion ||    │    │ if: forecast ||      │
│     shared          │    │     shared ||        │
│                     │    │     configs_new      │
└─────────────────────┘    └──────────┬───────────┘
                                      │
                                      ▼
                           ┌──────────────────────┐
                           │ smoke_run            │
                           │ if: smoke            │
                           │ triggers daily-      │
                           │ forecast-dk1_lear    │
                           └──────────────────────┘
```

### Path-filter outputs (the `changes` job)

| Output | Triggers when these paths change |
|---|---|
| `image` | `Dockerfile`, `pyproject.toml`, `uv.lock`, `src/data_cli/**`, `src/forecast_cli/**`, `src/price_forecasting/**`, `src/schedules/**` |
| `shared` | `src/domain/**`, `src/infrastructure_entsoe/**`, `src/infrastructure_clickhouse/**` (touched by everything; forces both deploy scripts to rerun) |
| `ingestion` | `src/data_cli/**`, `src/schedules/src/schedules/ingestion.py`, `src/schedules/src/schedules/deploy_ingestion.py` |
| `forecast` | `src/forecast_cli/**`, `src/price_forecasting/**`, `src/schedules/src/schedules/{forecast,reconciliation,drift,retrain}.py`, `src/schedules/src/schedules/deploy_forecast.py` |
| `configs_new` | `configs/*.py` (covers new files and edits; rerun is idempotent so we don't distinguish) |
| `grafana` | `grafana/**` |
| `smoke` | `src/price_forecasting/**`, `src/forecast_cli/**`, `src/schedules/src/schedules/{forecast,reconciliation}.py`, `configs/dk1_lear.py` |

**Paths that intentionally trigger nothing:** `docs/**`, `researh_material/**`, `README.md`, `CLAUDE.md`, `tests/**`, `.github/workflows/pr_*.yml`, `Dockerfile.worker`, `src/infrastructure_clickhouse/migrations/**`. When only these change, the `changes` job runs (~10 s) and the workflow finishes green with all downstream jobs skipped.

### Job specs (sketch)

All host-side jobs use the same Tailscale + SSH pattern as today.

**`build_image`** — `if: needs.changes.outputs.image == 'true' || needs.changes.outputs.shared == 'true'`
```
- Tailscale connect
- SSH: cd $REPO_PATH && git fetch origin main && git reset --hard origin/main
- SSH: docker build -t algo-repo:latest .
```

**`deploy_ingestion`** — `needs: [changes, build_image]`, `if: always() && (needs.build_image.result == 'success' || needs.build_image.result == 'skipped') && (needs.changes.outputs.ingestion == 'true' || needs.changes.outputs.shared == 'true')`
```
- Tailscale connect
- SSH: export PREFECT_API_URL=http://localhost:4200/api
       && uv run python src/schedules/src/schedules/deploy_ingestion.py
```
Retry once on failure (job-level `continue-on-error: false`, manual rerun for second failure).

**`deploy_forecast`** — symmetric to `deploy_ingestion`, gated on `forecast || shared || configs_new`. Runs `deploy_forecast.py`.

**`reload_grafana`** — `if: needs.changes.outputs.grafana == 'true'`. Independent of `build_image`.
```
- Tailscale connect
- SSH: cd $REPO_PATH && git pull --ff-only origin main
       && docker compose restart grafana
```

**`smoke_run`** — `needs: [changes, deploy_forecast]`, `if: needs.changes.outputs.smoke == 'true' && needs.deploy_forecast.result == 'success'`
```
- Tailscale connect
- SSH: trigger daily-forecast/daily-forecast-dk1_lear via prefect.deployments.run_deployment
       parameters={"target_date": "2026-03-22"}, timeout=600
- Exit 0 iff flow state == COMPLETED
```

## 5. `pr_smoke.yml` — new

### Trigger

```yaml
on:
  pull_request:
    branches: [main]
    paths:
      - 'src/price_forecasting/**'
      - 'src/forecast_cli/**'
      - 'src/schedules/src/schedules/forecast.py'
      - 'src/schedules/src/schedules/reconciliation.py'
      - 'configs/dk1_lear.py'
      - 'Dockerfile'
      - 'pyproject.toml'
      - 'uv.lock'
      - 'tests/smoke/**'
      - 'docker-compose.smoke.yml'
      - '.github/workflows/pr_smoke.yml'

concurrency:
  group: pr-smoke-${{ github.event.number }}
  cancel-in-progress: true
```

### Single job: `smoke`

```
runs-on: ubuntu-latest
timeout-minutes: 15

steps:
1. actions/checkout@v4
2. astral-sh/setup-uv@v5 with enable-cache: true, cache-dependency-glob: uv.lock
3. docker/setup-buildx-action@v3
4. docker/build-push-action@v5
   - context: .
   - tags: algo-repo:latest
   - load: true                    (load into local Docker, not push)
   - cache-from: type=gha
   - cache-to:   type=gha,mode=max
5. docker compose -f docker-compose.smoke.yml up -d clickhouse server worker
   (smoke compose override — no Grafana, no Loki, no exposed ports beyond what's needed)
6. wait-for-it: localhost:8123, localhost:4200
7. uv run python -m infrastructure_clickhouse.migrations.run_migrations
8. uv run python -m tests.smoke.seed
   (writes ~100 days of synthetic hourly DK1 prices + TotalLoad exogenous + future actuals)
9. uv run python src/schedules/src/schedules/deploy_forecast.py
10. uv run python -c "from prefect.deployments import run_deployment; ..."
    - trigger daily-forecast-dk1_lear, target_date=2026-03-22, timeout=300
11. uv run python -c "from schedules.reconciliation import reconcile_predictions_flow; reconcile_predictions_flow()"
12. uv run python -c "import clickhouse_connect; ..."
    - assert: count of rows in algo.experiment_runs FINAL where metrics_json != '{}' >= 1
13. always(): docker compose -f docker-compose.smoke.yml down -v
```

### Env in the smoke job

- `CLICKHOUSE_HOST=localhost`, `CLICKHOUSE_PORT=8123`, `CLICKHOUSE_DATABASE=algo`
- `PREFECT_API_URL=http://localhost:4200/api`
- `SLACK_WEBHOOK_URL` **explicitly unset** — `alerting.notify` no-ops; PRs cannot post to Slack.
- `LOKI_URL` unset — Loki not started in smoke compose. Logger handles missing Loki gracefully.
- `ENTSOE_API_KEY` unset — smoke does not call ENTSO-E.

### `docker-compose.smoke.yml`

A minimal override of `docker-compose.yml`:
- Drops `loki`, `grafana` services (not needed for smoke).
- Keeps `clickhouse`, `server`, `worker`.
- Keeps host port bindings (`8123:8123`, `4200:4200`) so the workflow can hit them via `localhost`.
- Same image refs as prod compose.

### `tests/smoke/fixtures.py`

Builds Polars frames matching `Observations.SCHEMA` and `Forecast.SCHEMA`:
- 100 days of hourly synthetic DK1 prices (sine wave + noise + weekly pattern), curve name `ENTSOE DK1 EnergyPrice Dayahead EUR`.
- 100 days of hourly synthetic `TotalLoad` forecasts (sine wave + slight trend), curve name `ENTSOE DK1 TotalLoad Dayahead`.
- 1 day of "future actuals" covering the target date (`2026-03-22`) so reconciliation has rows to match.

Total fixture size: ~5,000 rows. Memory footprint trivial.

### `tests/smoke/seed.py`

CLI entrypoint:
```python
def main() -> None:
    client = create_client()
    insert_observations_batch(client, build_price_observations())
    insert_forecasts_batch(client, build_load_forecasts())
    insert_observations_batch(client, build_future_actuals())
```

Idempotent (uses the same ingest functions as prod, which write to `ReplacingMergeTree`).

### Speed budget

| Step | Cold cache | Warm cache |
|---|---|---|
| Checkout + uv setup | 30s | 20s |
| `docker build` | 90s | 30s (layer cache hit) |
| `docker compose up` + service readiness | 50s | 50s |
| Migrations + seed | 15s | 15s |
| Deploy + forecast flow + reconcile | 90s | 90s |
| Assertion + teardown | 15s | 15s |
| **Total** | **~5 min** | **~3.5 min** |

Hard timeout: 15 min.

## 6. Concurrency and failure modes

### Concurrency

- `cd_deploy.yml`: `concurrency: group: cd-deploy, cancel-in-progress: false`. Merges queue.
- `pr_smoke.yml`: `concurrency: group: pr-smoke-${{ github.event.number }}, cancel-in-progress: true`. New pushes to the same PR cancel in-flight smokes.

### Failure modes — `cd_deploy.yml`

| Job fails | Effect | Recovery |
|---|---|---|
| `changes` | Whole workflow fails. Nothing deployed. | Fix filter syntax, push again. |
| `build_image` | Downstream deploy jobs skip. `reload_grafana` may still run. | Fix Dockerfile / deps, push again. Prod runs on previous `:latest`. |
| `deploy_ingestion` | Image is new, ingestion deployments stale. **Half-deployed.** | Manual rerun of `deploy_ingestion.py`, or push no-op commit. |
| `deploy_forecast` | Same for forecast/recon/drift. `smoke_run` skips. | Manual rerun or no-op commit. |
| `reload_grafana` | Dashboards stale. Nothing else affected. | `docker compose restart grafana`. |
| `smoke_run` | Deployments updated but smoke flow failed end-to-end. **Possible real-prod regression.** | Investigate via Prefect UI + Loki. Manual rollback (no automation in this spec). |

The "half-deployed state" gap exists in today's CD too; this spec does not introduce it. Mitigation: deploy scripts are idempotent and re-runnable. Failed deploy jobs can be retried via the GitHub Actions UI "Re-run failed jobs" button.

### Rollback

**Explicitly out of scope.** Today's rollback story is `git revert` + push, which re-runs CD with the reverted code. This spec preserves that — no automated rollback workflow, no SHA-tagged images, no deployment version pinning.

## 7. Non-goals (call them out so they don't sneak in)

- **Migrations stay manual.** No CD job applies migrations.
- **`docker-compose.yml` changes stay manual.** Restarting the stack mid-day could interrupt a running flow.
- **`Dockerfile.worker` rebuilds stay manual.** Rare.
- **No staging environment.** No second host, no separate compose project on the prod host.
- **No SHA-tagged images.** `algo-repo:latest` remains mutable.
- **No automated rollback.** `git revert` is the supported path.
- **PR smoke does not call ENTSO-E.** XML drift caught only via manual testing or post-merge.
- **PR smoke uses fresh empty CH.** Migration-against-real-data issues caught only on prod.
- **Drift / retrain flows are not exercised by smoke.** They run on prod cron only.
- **Ingestion is not exercised by smoke.** Wiring breaks surface only post-merge.

## 8. Open questions for review

1. Are the path filters in §4 the right partition? Specifically: should `src/schedules/src/schedules/retrain.py` count as `forecast` (current proposal) or split out separately?
2. Is `configs/dk1_lear.py` the right config for the prod `smoke_run` to trigger? Or should it use a dedicated `configs/smoke.py`?
3. The `smoke` filter currently fires the prod smoke for forecast/reconciliation code changes. Should it also fire for `Dockerfile`/`pyproject.toml` changes (which can break the image but not the smoke filter today)?
4. Acceptable to assume Tailscale's `tailscale ssh` pattern continues to work as it does in `cd_deploy.yml` today, or should we switch to a regular SSH key approach for any of the new jobs?
5. In the PR smoke (§5 step 11), should reconciliation be invoked via `run_deployment("reconcile-predictions/reconcile-predictions")` for consistency with how CD triggers the forecast flow, or by calling the flow function directly (`reconcile_predictions_flow()`)? Direct call is simpler; deployment call exercises more of the Prefect registration path.

## 9. Implementation order (preview, not the plan itself)

The writing-plans skill will turn this into a step-by-step plan. Rough ordering:

1. Add `tests/smoke/` (fixtures + seed) and `docker-compose.smoke.yml`. Verify locally.
2. Add `pr_smoke.yml`. Open a draft PR to validate it green on PR-time.
3. Rewrite `cd_deploy.yml` with the path-filter structure. Test by pushing a docs-only commit (should skip everything) and a forecast-code commit (should rebuild + redeploy forecast).
4. Documentation: update `DEPLOYMENT.md` to describe the new CD behavior and the manual operations (migrations, compose, worker rebuild).
