# On-Demand Ingestion Setup

This setup uses Prefect to orchestrate flows that run as ephemeral Docker containers.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  docker compose (always running)                            │
│                                                             │
│  ┌──────────┐  ┌────────────────┐  ┌──────────────────┐    │
│  │ClickHouse│  │ Prefect Server │  │  Prefect Worker   │    │
│  │ (DB)     │  │ (API + UI)     │  │  (Docker type)    │    │
│  └──────────┘  └────────────────┘  └────────┬─────────┘    │
│                                              │ spawns       │
│                                    ┌─────────▼──────────┐   │
│                                    │  algo-repo:latest   │   │
│                                    │  (ephemeral flow    │   │
│                                    │   container)        │   │
│                                    └─────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

- **Persistent containers:** ClickHouse, Prefect Server, Prefect Worker
- **Ephemeral containers:** Spawned by the worker for each flow run, auto-removed after completion

**How it works:**
1. The worker polls the Prefect Server for scheduled flow runs
2. When a run is due, the worker spawns an `algo-repo:latest` container
3. The container executes the flow, reports results to the server, and exits
4. The worker auto-removes the container and goes back to polling

---

## Setup Instructions

### Prerequisites

Create a `.env` file in the project root:
```bash
ENTSOE_API_KEY="your-api-key-here"
CLICKHOUSE_USER="default"
CLICKHOUSE_PASSWORD="password"
```

### 1. Build all images

```bash
# Build the app image (used by spawned flow containers)
docker build -t algo-repo:latest .

# Build infrastructure (worker image with prefect-docker)
docker compose build
```

### 2. Start infrastructure

```bash
docker compose up -d
```

This starts:
- **ClickHouse** — database
- **Prefect Server** — orchestration API + UI at http://localhost:4200
- **Prefect Worker** — Docker worker that auto-creates the `docker-pool` work pool

Wait ~15 seconds for the server to be ready.

### 3. Deploy the ingestion flow

```bash
PREFECT_API_URL="http://localhost:4200/api" uv run python src/schedules/scripts/deploy_ingestion.py
```

This registers the `entsoe-ingestion/ingestion-hourly` deployment with:
- Cron schedule: every hour at `:00`
- Image: `algo-repo:latest`
- Network: `algo-repo_default` (same as compose services)
- Environment variables for ClickHouse + ENTSOE passed to the spawned container

---

## Verify It's Working

### Check services
```bash
docker compose ps
docker compose logs worker --tail 20
```

### View Prefect UI
Open http://localhost:4200/deployments

### Trigger a manual run (for testing)
```bash
PREFECT_API_URL="http://localhost:4200/api" prefect deployment run "entsoe-ingestion/ingestion-hourly"
```

### Watch the worker spawn and run a container
```bash
docker compose logs -f worker
```

---

## Rebuilding After Code Changes

```bash
# 1. Rebuild the app image
docker build -t algo-repo:latest .

# That's it — the next scheduled (or manual) run will use the new image.
# No need to restart the worker.
```

---

## Troubleshooting

**Worker not picking up jobs:**
```bash
docker compose logs worker
# Look for "Worker 'docker-pool' started!" message
```

**Spawned container can't connect to ClickHouse:**
```bash
# Verify the network exists
docker network ls | grep algo-repo_default

# Check env vars in the deployment
PREFECT_API_URL="http://localhost:4200/api" prefect deployment inspect "entsoe-ingestion/ingestion-hourly"
```

**Manual test — run the flow image directly:**
```bash
docker run --rm \
  --network algo-repo_default \
  -e PREFECT_API_URL=http://server:4200/api \
  -e CLICKHOUSE_HOST=clickhouse \
  -e CLICKHOUSE_USER=default \
  -e CLICKHOUSE_PASSWORD=password \
  -e ENTSOE_API_KEY="your-key" \
  algo-repo:latest \
  python -c "from schedules.ingestion import entsoe_ingestion_flow; entsoe_ingestion_flow()"
```