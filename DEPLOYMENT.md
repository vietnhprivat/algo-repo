# On-Demand Ingestion Setup

This setup uses Prefect workers to run ingestion flows on-demand in Docker containers.

## Architecture

- **Persistent containers:** ClickHouse, Prefect Server, Prefect Worker
- **On-demand containers:** Ingestion flow (spins up hourly, runs, then stops)

**Benefits:**
- 90% less resource usage vs persistent ingestion container
- Worker spawns containers only when scheduled
- Automatic cleanup after each run

---

## Setup Instructions

### 1. Build the Docker image

```bash
docker build -t algo-repo:latest .
```

### 2. Start infrastructure services

```bash
docker-compose up -d
```

This starts:
- ClickHouse (database)
- Prefect Server (orchestration)
- Prefect Worker (executes scheduled jobs)

### 3. Create the work pool

```bash
PREFECT_API_URL="http://localhost:4200/api" uv run python src/schedules/scripts/setup_work_pool.py
```

### 4. Deploy the ingestion flow

The script automatically loads environment variables from `.env`:

```bash
PREFECT_API_URL="http://localhost:4200/api" uv run python src/schedules/scripts/deploy_ingestion.py
```

Make sure your `.env` contains:
```bash
ENTSOE_API_KEY="your-api-key-here"
CLICKHOUSE_USER="default"
CLICKHOUSE_PASSWORD="password"
```

This registers the flow with the Prefect server. The worker will now:
- Poll for scheduled runs every hour
- Spin up `algo-repo:latest` container
- Execute the ingestion flow
- Clean up container after completion

---

## Verify It's Working

### Check worker is running
```bash
docker logs -f prefect-worker
```

### Check deployments in UI
Open http://localhost:4200/deployments

### Trigger manual run (for testing)
```bash
prefect deployment run "entsoe-ingestion/ingestion-hourly"
```

### View flow runs
```bash
docker logs prefect-worker --tail 100
```

---

## How On-Demand Works

```
Every Hour at :00
     |
     v
Worker checks schedule
     |
     v
Worker runs: docker run --rm \
  --network algo-repo_default \
  -e CLICKHOUSE_HOST=clickhouse \
  algo-repo:latest \
  python -m prefect.engine
     |
     v
Container starts -> Runs flow -> Exits
     |
     v
Worker auto-removes container
     |
     v
Worker back to idle (waiting for next hour)
```

**Resource usage:**
- Idle: 50MB (just the worker)
- Running: 700MB (worker + flow container)
- Duration: ~2 minutes per run

---

## Rebuilding After Code Changes

```bash
# 1. Rebuild image
docker build -t algo-repo:latest .

# 2. Restart worker (to pick up new image)
docker-compose restart worker

# Next scheduled run will use new code automatically
```

---

## Troubleshooting

**Worker not picking up jobs:**
```bash
docker logs prefect-worker
# Check for "Worker started" message
```

**Container can't connect to ClickHouse:**
- Verify network: `docker network ls | grep algo-repo_default`
- Check `CLICKHOUSE_HOST=clickhouse` in deployment

**Manual test:**
```bash
docker run --rm \
  --network algo-repo_default \
  -e CLICKHOUSE_HOST=clickhouse \
  -e ENTSOE_API_KEY="your-key" \
  algo-repo:latest \
  python -c "from schedules.ingestion import entsoe_ingestion_flow; entsoe_ingestion_flow()"
```

---

## Comparison: Old vs New

**Old (Persistent):**
- 1 container always running: 650MB RAM
- Runs 24/7, mostly idle

**New (On-Demand):**
- 1 worker always running: 50MB RAM
- Containers only when needed: 650MB for 2 min/hour
- 90% reduction in resource usage
