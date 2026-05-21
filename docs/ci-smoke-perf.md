# PR Smoke CI Performance — Handover

## Current state (2026-05-21)

PR #76 merged a BuildKit uv-cache-mount to the Dockerfile. Measured impact:

| Scenario | Build step | Total smoke |
|----------|-----------:|------------:|
| `uv.lock`-stable PR (warm GHA layer cache) | ~30s | **~3–5 min** |
| `uv.lock`-changing PR (cache mount warm, layer cache busted) | **3m 42s** | **6m 49s** |
| Cold (GHA cache eviction) | unmeasured | ~8 min est. |

The cache mount cut lock-change builds by ~30% at zero infra cost, but the warm
path is still floor-limited by buildx export + compose startup + flow execution
(~3 min combined), not the build itself.

To break under 5 min total in all scenarios, the next step is to **move the
smoke job off GHA-hosted runners onto a dedicated self-hosted runner**.

## Decision: self-hosted runner on the secondary server

Use the secondary server (not the prod deploy host) as a dedicated GitHub Actions
runner for PR smoke. Repo is **private** so fork-PR security risk does not apply.

### Why this beats the other options

| Option | Effort | Warm path | Lock-change | Ongoing cost |
|--------|-------:|----------:|------------:|--------------|
| Cache mount (PR #76, **done**) | trivial | unchanged | 6m 49s | none |
| GHCR pre-built base image | ~half day | ~2–3 min | 6–8 min (fallback path) | workflow + GHCR storage |
| Faster GHA runner (Depot/Blacksmith) | ~30 min | ~2 min | ~3 min | per-minute billing |
| **Self-hosted on secondary server** | ~half day | **<2 min** | **<2 min** | runner uptime |

The self-hosted path wins on speed (persistent local Docker layer cache, real
CPU, no cache upload/download), wins on cost (no per-minute billing), and stays
isolated from the prod deploy host so PR builds never compete with the 06:00 UTC
forecast or 18:00 reconciliation cron.

### Why *not* the prod deploy host

Was considered, rejected: a PR firing at 06:00 UTC would fight the daily forecast
flow for CPU/memory; DNN training (future) would make this worse. Use the
secondary server precisely to avoid this.

## Architecture

```
GitHub                        Secondary server (new)              Prod deploy host (unchanged)
─────────                     ──────────────────────              ────────────────────────────
PR opened ──> Actions job ──> myoung34/github-runner              Tailscale ssh from CD
                              (Docker, ephemeral)                  Local docker build (cuda)
                                │                                  Prefect server/worker/CH
                                ├── /var/run/docker.sock
                                │   (host Docker daemon,
                                │   persistent layer cache)
                                │
                                └── docker compose up smoke
                                    services (own project name,
                                    isolated network)
```

Key properties:
- **Ephemeral runner container per job** (no in-container state leakage).
- **Mounted host Docker socket** so the BuildKit layer cache persists across runs.
- **Separate compose project name** (`smoke-pr-${PR_NUMBER}`) to avoid clashes
  if multiple smokes ever overlap.
- **Concurrency group** in `pr_smoke.yml` ensures only one smoke per PR at a
  time (already present).

## Implementation checklist

### 1. Secondary server prerequisites
- [ ] Docker installed (`docker --version` ≥ 24).
- [ ] ≥ 50 GB free disk (image cache + build cache).
- [ ] Outbound network to `github.com`, `ghcr.io`, `pypi.org`,
      `download.pytorch.org`.
- [ ] On the Tailnet (same network as prod deploy host) **if** smoke needs to
      reach prod ClickHouse — currently it doesn't, smoke spins its own. Keep
      it off the prod network unless that changes.

### 2. Register the runner
- [ ] GitHub repo → Settings → Actions → Runners → New self-hosted runner. Copy
      the registration token (short-lived, ~1 h).
- [ ] On the secondary server, launch a single long-lived "registration"
      container using `myoung34/github-runner` with `EPHEMERAL=true`. With
      ephemeral mode, the runner auto-deregisters after one job and the
      container exits — wrap in a systemd service that respawns on exit so a
      fresh runner is always ready.
- [ ] Use labels: `self-hosted`, `linux`, `x64`, **`smoke`** (the `smoke` label
      is what `pr_smoke.yml` will target).
- [ ] Mount `/var/run/docker.sock` into the runner container so jobs use the
      host's Docker daemon (this is the whole point — persistent layer cache).

Reference systemd unit pattern:
```ini
# /etc/systemd/system/gh-runner-smoke@.service
[Service]
ExecStart=/usr/bin/docker run --rm \
  -e REPO_URL=https://github.com/vietnhprivat/algo-repo \
  -e RUNNER_TOKEN=<short-lived-from-github-or-PAT-API> \
  -e RUNNER_NAME=smoke-%i \
  -e LABELS=self-hosted,linux,x64,smoke \
  -e EPHEMERAL=true \
  -v /var/run/docker.sock:/var/run/docker.sock \
  myoung34/github-runner:latest
Restart=always
```
Run two or three instances (`gh-runner-smoke@1`, `@2`) so a queued PR doesn't
wait for the previous one's teardown.

Tokens: registration tokens expire. For long-term, use a PAT with `repo` scope
and the runner image's auto-registration flow that mints a fresh token at boot.
Store in `/etc/gh-runner/env` (mode 0600). **Do not commit.**

### 3. Switch the smoke workflow
- [ ] In `.github/workflows/pr_smoke.yml`:
  ```yaml
  jobs:
    smoke:
      runs-on: [self-hosted, smoke]   # was: ubuntu-latest
  ```
- [ ] Drop the GHA cache backend — local Docker layer cache supersedes it:
  ```yaml
  # remove:
  #   cache-from: type=gha,scope=algo-repo-cpu
  #   cache-to: type=gha,mode=max,scope=algo-repo-cpu
  ```
- [ ] Keep `buildx` (still want BuildKit semantics + the cache mount from PR #76).
- [ ] Use a per-PR compose project name to avoid collisions:
  ```yaml
  env:
    COMPOSE_PROJECT_NAME: smoke-pr-${{ github.event.number }}
  ```
- [ ] Add a post-job cleanup step (runs `if: always()`) to keep disk in check:
  ```yaml
  - name: Prune old build cache and images
    if: always()
    run: |
      docker compose down -v --remove-orphans || true
      docker image prune -f --filter "until=72h" || true
      docker builder prune -f --filter "until=72h" --keep-storage 20GB || true
  ```

### 4. First-run validation
- [ ] Open a no-op PR (touch `docs/`) — confirm smoke routes to the self-hosted
      runner and completes green.
- [ ] Open a `uv.lock`-touching PR (e.g. `uv lock --upgrade-package pytest-cov`)
      — confirm lock-change path completes green and is faster than PR #76's
      6m 49s baseline.
- [ ] Confirm prod cron (06:00/18:00/19:00 UTC) on the deploy host is unaffected
      — it should be, since smoke runs on the secondary server.

### 5. Document and decommission GHA fallback
- [ ] Update `docs/RUNBOOK.md` with: how to restart the runner, where its logs
      are, how to rotate the registration token.
- [ ] Keep `ubuntu-latest` as a documented fallback path (commented in the
      workflow) so a single-line change reverts to GHA-hosted if the secondary
      server is down for an extended period.

## Open questions for the next session

1. **Disk budget on the secondary server.** Each cached layer set is ~300 MB
   (cpu) + ~3 GB (cuda once DNN ships). Decide a hard cap and tune the
   `docker builder prune --keep-storage` value.
2. **How many parallel runners?** Two is probably right (one PR + one queued).
   Three uses more RAM but covers the burst case.
3. **Runner observability.** Do we want runner uptime in Grafana? Easy via
   node-exporter on the secondary server; out of scope for the initial cut.
4. **Single-server SPOF.** If the secondary server is down, no PR can merge.
   Acceptable for solo dev. If later you need redundancy, add a second runner
   on a third box with the same labels — GHA will load-balance.
5. **CD deploy job (`cd_deploy.yml`).** Currently SSHes from `ubuntu-latest`
   into the prod host via Tailscale. Could move that to the self-hosted runner
   too (less Tailscale auth overhead) but the savings are tiny — defer.

## Definition of done

- Smoke runs exclusively on the secondary server.
- Warm-path PR smoke finishes in **< 2 min total**.
- `uv.lock`-changing PR smoke finishes in **< 3 min total**.
- Prod cron windows (06:00, 18:00, 19:00 UTC) are demonstrably unaffected —
  spot-check Loki / experiment_runs table on the next merge that lands in those
  windows.
- Runner survives unattended for ≥ 7 days without manual intervention.
- One-line workflow rollback to `ubuntu-latest` documented in the workflow file.

## Out of scope but related

- **Self-hosted CD runner** — the `cd_deploy.yml` Tailscale path is fine.
- **GHCR base image** — explicitly *not* pursued; the self-hosted runner's
  persistent layer cache delivers the same benefit without the workflow + GHCR
  storage maintenance burden.
- **Depot / Blacksmith** — explicitly *not* pursued; no per-minute billing
  beats their per-minute billing.
- **Node 20 deprecation** on `actions/checkout@v4`, `docker/build-push-action@v5`,
  `docker/setup-buildx-action@v3` — still forced to Node 24 by GHA on
  **2026-06-02**. Bump to v5/v6 successors before then (orthogonal to runner
  choice; same workflow code).
