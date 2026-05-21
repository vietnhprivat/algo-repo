# PR Smoke CI Performance — Handover

## Current state (2026-05-21)

After splitting torch into `cpu`/`cuda` extras (PR #75) the smoke pipeline
finishes successfully but still takes **~12 minutes** on a cold cache and
likely **3–5 minutes** with a warm `algo-repo-cpu` GHA cache. Target should
be **<5 minutes** even cold, since smoke runs on every PR push that touches
`src/price_forecasting/**`, `src/forecast_cli/**`, `Dockerfile`,
`pyproject.toml`, or `uv.lock`.

Workflow: `.github/workflows/pr_smoke.yml`. Cache scope: `algo-repo-cpu`.

## Where the 12 minutes go

Approximate cold-cache breakdown (from the run that landed in PR #75):

| Stage                                    | ~Time | Notes |
|------------------------------------------|------:|-------|
| Checkout + buildx setup                  |   30s | irreducible |
| Build: heavy `uv sync --extra cpu`       |  6–8m | downloads ~250 MB torch+CPU + all other deps fresh |
| Build: workspace `uv sync`               |  10s  | already small, fine |
| Layer export + buildx cache-to upload    |  1–2m | exports image to docker daemon, uploads cache to GHA |
| `docker compose up` clickhouse/server/worker | ~30s | irreducible-ish |
| Wait for ClickHouse readiness            |   ~5s |  |
| Wait for Prefect server readiness        |  10–30s | most variance lives here |
| Migrations + seed + register deployments |  ~20s | three separate `docker run` invocations |
| Run daily-forecast-smoke deployment       |  20–40s |  |
| Run reconcile-predictions deployment      |  20–30s |  |
| Assert reconciled smoke run               |   ~5s |  |
| Teardown                                  |  ~10s |  |

Sum: ~12 min cold. The dominant cost is the **heavy uv sync layer**.

## Things to try (ranked by impact / effort)

### 1. Pre-built base image with deps baked in (high impact, moderate effort)

The biggest win: stop reinstalling deps on every PR. Today's first
`uv sync --frozen --no-install-workspace` rebuilds the entire dep graph
whenever `pyproject.toml` or `uv.lock` changes. Instead:

- Build a `algo-repo-deps:<lock-hash>` image once, push to GHCR.
- PR smoke uses that image as `FROM`, only runs the workspace `uv sync`.
- Refresh the base image on a CD job that triggers when `uv.lock` changes
  on `main`.

Expected: smoke drops to ~3 min cold, ~1 min warm.

Files: `Dockerfile`, new `.github/workflows/build-deps-image.yml`.

### 2. Skip smoke when only configs change (low impact, very low effort)

Currently the workflow's path filter includes `configs/dk1_lear.py`.
Many config-only PRs trigger a full smoke run. Either:

- Drop config paths from the trigger filter (config edits are pure data).
- Or add a `paths-ignore` for `configs/*.py` to short-circuit.

Tradeoff: a typo in `dk1_lear.py` wouldn't be caught by smoke until merge.
Acceptable if `pr_test.yml` covers it (it should, via config-loader tests).

### 3. Buildx registry cache instead of GHA cache (medium impact, medium effort)

GHA's `cache-from: type=gha` is limited to 10 GB org-wide and is slow
on uploads. Move to `type=registry,ref=ghcr.io/vietnhprivat/algo-repo-cache:cpu`
— faster uploads and no eviction churn.

Files: `.github/workflows/pr_smoke.yml`, GHCR token in repo secrets.

### 4. Parallelize compose readiness with the build (low impact, low effort)

Today the workflow does:
build → `docker compose up` → wait → ...

`docker compose up -d clickhouse server` could fire concurrently with the
buildx step in a separate job and pass over the network namespace, or
ClickHouse could be pre-started in a service container. Saves ~30s.

### 5. Drop torch from smoke entirely if smoke only exercises LEAR (high impact, low effort, controversial)

LEAR is scikit-learn-only. `tests/smoke/*` and `daily-forecast-smoke`
should not need torch at all. If we can audit and confirm no smoke path
imports torch, we could:

- Move `torch>=2.11.0` from `price-forecasting` base deps into a `dnn`
  optional extra.
- Smoke installs the workspace without `[dnn]`, finishing the heavy uv
  sync in ~30 seconds.

Verify by grepping the smoke import graph:
```bash
docker run --rm algo-repo:latest python -c "import sys; \
  import tests.smoke.seed, schedules.forecast, schedules.reconciliation; \
  print([m for m in sys.modules if 'torch' in m])"
```

If torch isn't imported, this is the largest possible win.

### 6. Smaller base image (low impact, low effort)

`python:3.13-slim` is already small (~120 MB). Switching to `python:3.13-alpine`
saves ~50 MB but breaks manylinux wheels. Not worth it.

## Out of scope but related

- Node 20 deprecation warning on `actions/checkout@v4`, `docker/build-push-action@v5`,
  `docker/setup-buildx-action@v3`. Forced to Node 24 by GHA on **2026-06-02**. Bump
  to the v5/v6 successors before then.
- `Dockerfile.worker` is unrelated — only ships prefect-docker, no torch.

## Definition of done

A PR-touching change in `src/forecast_cli/**` produces a green smoke check
in under 5 minutes on a cold cache, under 2 minutes on a warm cache.
