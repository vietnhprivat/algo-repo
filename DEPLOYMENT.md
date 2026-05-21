# Deployment Guide

This project orchestrates ingestion, forecasting, reconciliation, and drift detection via Prefect. All services run as containers on one host; Grafana + Loki provide observability; CI/CD deploys to the host over a Tailscale tunnel.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  docker compose (always running)                                     │
│                                                                      │
│  ┌──────────┐  ┌────────────────┐  ┌──────────────────┐              │
│  │ClickHouse│  │ Prefect Server │  │  Prefect Worker  │              │
│  │ (DB)     │  │ (API + UI)     │  │  (Docker type)   │              │
│  └──────────┘  └────────────────┘  └────────┬─────────┘              │
│                                              │ spawns                │
│                                     ┌────────▼──────────┐            │
│                                     │  algo-repo:latest │            │
│                                     │  (ephemeral flow  │            │
│                                     │   container)      │            │
│                                     └───────────────────┘            │
│                                                                      │
│  ┌──────────┐  ┌────────────────┐                                    │
│  │  Loki    │  │    Grafana     │                                    │
│  │  (logs)  │  │ (dashboards)   │                                    │
│  └──────────┘  └────────────────┘                                    │
└──────────────────────────────────────────────────────────────────────┘
```

**Always-running services:** ClickHouse, Prefect Server, Prefect Worker, Loki, Grafana.
**Ephemeral containers:** spawned by the worker per flow run.

**Deployments registered in Prefect:**
- `entsoe-ingestion/ingestion-hourly-<AREA>` — one per area, hourly.
- `daily-forecast/daily-forecast-<CONFIG>` — daily at 06:00 UTC.
- `reconcile-predictions/reconcile-predictions` — daily at 18:00 UTC (4h after ENTSO-E day-ahead publication).
- `drift-detection/drift-detection-<area>` — daily at 19:00 UTC.

---

## Setup

### Prerequisites

Create `.env` in the repo root:
```bash
ENTSOE_API_KEY="your-api-key-here"
CLICKHOUSE_USER="default"
CLICKHOUSE_PASSWORD="password"
GRAFANA_ADMIN_USER="admin"
GRAFANA_ADMIN_PASSWORD="admin"
```

### 1. Build the app image

```bash
docker build -t algo-repo:latest .
docker compose build
```

### 2. Start infrastructure

```bash
docker compose up -d
```

Wait ~15s for the Prefect server, then confirm the worker came up:
```bash
docker compose logs worker --tail 20   # look for "Worker 'docker-pool' started!"
```

### 3. Run migrations

```bash
uv run python -m infrastructure_clickhouse.migrations.run_migrations
```

Current migrations: `001`…`010` (drift reports, hyperparam trials, retrain events, experiment-run git SHA).

In production, migrations auto-apply on every CD deploy (see [CI/CD](#cicd) below). The command above is kept as a recovery procedure for local setup and for manually catching up a host after a CD failure.

### 4. Register Prefect deployments

```bash
export PREFECT_API_URL="http://localhost:4200/api"
uv run python src/schedules/src/schedules/deploy_ingestion.py
uv run python src/schedules/src/schedules/deploy_forecast.py
```

`deploy_ingestion.py` registers one deployment per area in `AREAS`.
`deploy_forecast.py` registers the daily forecast per config in `FORECAST_CONFIGS`, a single reconciliation deployment, and one drift-detection deployment per area in `DRIFT_AREAS`.

Both scripts are idempotent — rerun them any time to pick up config changes.

---

## Verify

### Prefect UI
http://localhost:4200/deployments

### Grafana
http://localhost:3000 (credentials from `.env`). Three auto-provisioned dashboards: **Data Quality**, **Model Performance**, **Operational**.

### Manual flow trigger
```bash
PREFECT_API_URL="http://localhost:4200/api" prefect deployment run "daily-forecast/daily-forecast-dk1_lear"
PREFECT_API_URL="http://localhost:4200/api" prefect deployment run "reconcile-predictions/reconcile-predictions"
PREFECT_API_URL="http://localhost:4200/api" prefect deployment run "drift-detection/drift-detection-dk1"
```

---

## Observability

- **Metrics** live in ClickHouse (`algo.experiment_runs`, `algo.experiment_predictions`, `algo.drift_reports`, `algo.model_artifacts`).
- **Logs** are pushed to Loki directly from Python via `python-logging-loki`. Query them from the Operational dashboard or by adding a Loki explore panel.
- **Drift reports** land in `algo.drift_reports`. The drift flow logs a WARNING to Loki when drift is detected; Grafana alerts can be wired on that.

---

## Rebuild after code changes (local)

```bash
docker build -t algo-repo:latest .
```

The next scheduled or manual run picks up the new image. The worker does not need to restart.

---

## CI/CD

`main` merges trigger [.github/workflows/cd_deploy.yml](.github/workflows/cd_deploy.yml). The job runs on a GitHub-hosted runner, joins the tailnet, SSHes into the deploy host via Tailscale SSH, rebuilds the image, reruns the `deploy_*.py` scripts, and triggers a `daily-forecast` flow run to verify the pipeline end-to-end before reporting success.

### One-time host setup

1. **Enable Tailscale SSH** on the deploy host:
   ```bash
   sudo tailscale up --ssh
   ```

2. **Create a Tailscale OAuth client** at https://login.tailscale.com/admin/settings/oauth with the `devices` scope and permission to mint keys for `tag:ci`.

3. **Declare the `tag:ci` tag** in the tailnet ACL (`tagOwners`) and allow it to SSH as the deploy user:
   ```jsonc
   {
     "tagOwners": {
       "tag:ci": ["autogroup:admin"]
     },
     "ssh": [
       {
         "action": "accept",
         "src":    ["tag:ci"],
         "dst":    ["<deploy-host-tag-or-user>"],
         "users":  ["<deploy-user>"]
       }
     ]
   }
   ```

4. **GitHub repository secrets:**
   - `TS_OAUTH_CLIENT_ID`
   - `TS_OAUTH_SECRET`
   - `DEPLOY_HOST` — MagicDNS name of the host (e.g. `<hostname>.<tailnet>.ts.net`)
   - `DEPLOY_USER` — SSH username on the host
   - `DEPLOY_REPO_PATH` — absolute path to the repo checkout on the host

### Manual redeploy (CD bypass)

When the tunnel is down or the host was offline at merge time, run the same two commands locally on the host:
```bash
PREFECT_API_URL="http://localhost:4200/api" uv run python src/schedules/src/schedules/deploy_ingestion.py
PREFECT_API_URL="http://localhost:4200/api" uv run python src/schedules/src/schedules/deploy_forecast.py
```

---

## Troubleshooting

**Worker not picking up jobs**
```bash
docker compose logs worker --tail 50
```

**Spawned container can't reach ClickHouse**
```bash
docker network ls | grep algo-repo_default
PREFECT_API_URL="http://localhost:4200/api" prefect deployment inspect "daily-forecast/daily-forecast-dk1_lear"
```

**Flow failing silently** — check Loki via the Operational dashboard; every `schedules/*` module logs with `LOKI_URL` enabled.

**CD job hangs on "Join tailnet"** — OAuth client likely missing `tag:ci` in tagOwners, or the secret pair is for the wrong tailnet.

**Manual run via plain Docker:**
```bash
docker run --rm \
  --network algo-repo_default \
  -e PREFECT_API_URL=http://server:4200/api \
  -e CLICKHOUSE_HOST=clickhouse \
  -e CLICKHOUSE_USER=default \
  -e CLICKHOUSE_PASSWORD=password \
  -e ENTSOE_API_KEY="your-key" \
  algo-repo:latest \
  python -c "from schedules.forecast import daily_forecast_flow; daily_forecast_flow(config_name='dk1_lear')"
```
