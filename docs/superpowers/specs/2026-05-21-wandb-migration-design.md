# Weights & Biases Integration — Design Spec

> **Status.** Draft, awaiting user review.
> **Date.** 2026-05-21.
> **Driver.** Thesis defensibility, supervisor collaboration, and a live demo at the defense. W&B is unlocked under DTU's academic license.
> **Non-goal.** Replacing ClickHouse / Grafana / Loki / Slack. The production data plane is not migrated.

---

## 1. Problem statement

The repo's current MLOps scorecard against Zarour et al. (2025) P1–P9 (see `researh_material/reading_guides/mlops_best_practices_reading_guide.md`, with status updated against `docs/REPO_OVERVIEW.md` commit `2d5989a`) leaves three practices under-served:

- **P5 — Collaboration & Communication.** Solo developer. Grafana is operational-only. Nothing exists for supervisor-facing thesis artifacts.
- **P7 — Track & Log ML Metadata.** ClickHouse captures **run-level** metadata (one row per backtest / prediction). It does *not* capture **training-time** metadata (per-epoch loss, gradient norms, weight histograms, hyperparameter-importance plots), which becomes critical for the DNN/Transformer phase.
- **P4 — Versioning.** Model artifacts live as base64 joblib blobs in `algo.model_artifacts`. There is no lineage UI linking runs → artifacts → deployments.

P1, P2, P3, P6, P8, P9 are already well-covered by existing infra (GitHub Actions + Tailscale CD, Prefect, Docker + `GIT_SHA`, daily refit + drift-triggered retrain, Grafana + Evidently + Slack, `triggered_retrain` flow with audit). Re-instrumenting them in W&B would be pure duplication with no demo or thesis payoff.

A defense demo also needs a single, navigable visual surface — bouncing between ClickHouse queries, Grafana dashboards, and ad-hoc notebooks during a live walkthrough is a poor story.

---

## 2. Goals

1. **Thesis Reports** — produce shareable W&B Reports, one per OPEN gap from `docs/RESEARCH_BRIEF.md` (VST, calibration windows, exogenous features, DM/GW statistical tests, DNN architecture), that double as thesis chapter material.
2. **DNN/Transformer dev velocity** — per-step training visibility (loss curves, gradients, weight histograms, multi-seed ensemble divergence) before the deep-model phase begins.
3. **Defense demo surface** — one URL the audience can follow that covers backtests, ablations, tuning, and deployed-system performance.
4. **Zero production risk** — no change to the daily forecast, reconciliation, drift, or retrain flows beyond an additive sync hook.

---

## 3. Non-goals

- Migrating ClickHouse experiment tables out of ClickHouse.
- Replacing Grafana operational dashboards or Loki structured logging.
- Wiring W&B into ingestion, drift detection, or retrain audit trails.
- Backfilling historical `algo.experiment_runs` rows into W&B (old runs lack the per-step metadata that makes W&B valuable; cost > value).
- Changing the daily prod forecast model code path beyond the dual-write tracker call.

---

## 4. Architecture

```
┌─────────────────── PRODUCTION DATA PLANE (UNCHANGED) ──────────────────────────┐
│                                                                                │
│  Prefect ingestion ─► algo.timeseries ─► daily-forecast (LEAR) ─► algo.*       │
│                                              │                                 │
│                                              ▼                                 │
│                                       reconciliation ─► Slack + Grafana        │
│                                              │                                 │
│                                              ▼                                 │
│                                          drift ─► retrain                      │
└──────────────────────────────────────────────┬─────────────────────────────────┘
                                               │ one new sync hook
                                               ▼
┌─────────────────── W&B SURFACE (NEW) ──────────────────────────────────────────┐
│  algo-prod project       │  algo-research project    │  Reports               │
│  • daily reconciled      │  • backtest runs          │  • VST ablation        │
│    MAE / RMSE / sMAPE    │  • DNN training curves    │  • Calibration windows │
│  • one continuous run    │  • tuning sweeps          │  • Exog. features      │
│    per (area, config)    │  • ablation studies       │  • DM/GW matrices      │
│                          │  • predict runs           │  • DNN architecture    │
│                          │  • W&B Artifacts          │                        │
└──────────────────────────┴───────────────────────────┴────────────────────────┘
                                               ▲
                                               │ writes from
┌─────────────────── FORECAST CLI + TRACKING (DUAL-WRITE) ───────────────────────┐
│  forecast-cli backtest --track   ─► ClickHouse  AND  W&B (algo-research)      │
│  forecast-cli predict --track    ─► ClickHouse  AND  W&B (algo-research)      │
│  forecast-cli tune               ─► ClickHouse  AND  W&B (sweep)              │
│  forecast-cli ablate (NEW)       ─► W&B only (algo-research, as sweep)        │
└────────────────────────────────────────────────────────────────────────────────┘
```

ClickHouse remains the **operational source of truth**. W&B is the **visualization and collaboration surface**.

---

## 5. Scope — what changes, what doesn't

### 5.1 Untouched (zero edits)

- All 9 ClickHouse migrations and tables.
- `src/domain/*`, `src/infrastructure_entsoe/*`, `src/infrastructure_clickhouse/*` (write paths unchanged; new package below imports from them).
- `src/data_cli/*`.
- `src/schedules/ingestion.py`, `src/schedules/forecast.py`, `src/schedules/drift.py`, `src/schedules/retrain.py`, `src/schedules/alerting.py`.
- Grafana dashboards + provisioning + file-provisioned alert rules.
- Loki + `infrastructure_clickhouse.logging_setup`.
- `.github/workflows/*` (CI/CD).
- `docker-compose.yml` (no new service — W&B is SaaS).

### 5.2 Modified (dual-write — additive only)

| File | Change |
|---|---|
| `src/forecast_cli/tracking.py` | After existing `insert_experiment_run()` + `insert_experiment_predictions()` calls, also invoke `WandbTracker.log_backtest_run(...)` / `log_predict_run(...)`. Gated by `WANDB_MODE` env var so it cleanly no-ops without credentials. |
| `src/price_forecasting/.../models/lightning_base.py` | Replace `logger=False` in the `L.Trainer(...)` constructor with the `wandb.sdk.lib.WandbLogger` instance when `wandb_project` is set on the active config. Per-step train/val loss, gradients, learning rate come free. |
| `src/price_forecasting/.../tuning/optuna_storage.py` | Add `build_wandb_sweep_callback(...)` alongside the existing ClickHouse persistence callback. Both run per trial — ClickHouse persists raw rows, W&B builds the sweep view. |
| `src/schedules/.../reconciliation.py` | After each per-area metric write, call `WandbTracker.log_prod_reconciled(area, config_name, date, metrics)`. Writes one step/day to the `algo-prod` project. |
| `src/price_forecasting/.../configs/experiment.py` | Add `wandb_project: str \| None = None` and `wandb_tags: list[str] = []` fields to `ExperimentConfig`. |
| `Dockerfile` | Pass `WANDB_API_KEY` and `WANDB_ENTITY` through as runtime env vars (mirror existing `SLACK_WEBHOOK_URL` pattern). |
| `src/schedules/.../deploy_forecast.py` | Bake `WANDB_*` env vars into each flow container's env block. |
| `pyproject.toml` (workspace + relevant package manifests) | Add `wandb` dependency; add `observability_wandb` to workspace members. |

Net touch surface across modified files is intentionally small. Each call site delegates to a single `WandbTracker` method so the W&B schema lives in one package.

### 5.3 New (net additions)

| Path | Purpose |
|---|---|
| `src/observability_wandb/` | New uv workspace package, mirroring `infrastructure_clickhouse/`. Contains: `client_factory.py` (reads `WANDB_API_KEY`, `WANDB_ENTITY`, `WANDB_PROJECT`; honours `WANDB_MODE=disabled` for offline/no-creds runs), `tracker.py` (the `WandbTracker` class — single owner of "what gets logged" with `log_backtest_run`, `log_predict_run`, `log_prod_reconciled`, `log_artifact`, `start_sweep_run` methods), `logging_setup.py` (mirrors the Loki graceful-no-op pattern). |
| `src/observability_wandb/.../artifacts.py` | Pushes the joblib blob produced by `LiveResult.trained_models` as a W&B Artifact, linked to the run that produced it. ClickHouse `algo.model_artifacts` remains source of truth; W&B Artifact stores a parallel copy keyed by the same `artifact_id`. |
| `src/forecast_cli/.../ablate.py` | New Typer command: `forecast-cli ablate <config> --vary <field> --over <json>`. Drives a backtest sweep across a single config field (e.g. `--vary calibration_windows --over '[[56,84],[56,84,1092],[56,84,1092,1456]]'`), emits all results to W&B as a sweep + Table. Designed to produce content directly for the RESEARCH_BRIEF.md OPEN gaps. |
| `tests/observability_wandb/` | Fake W&B client (mirrors `tests/infrastructure_entsoe/`'s fake-client pattern). Verifies the tracker calls the right API methods with the right payloads without hitting the network. |
| `tests/forecast_cli/test_ablate.py` | Unit tests for the ablation runner — config-field variation, dispatch to backtest, result aggregation. |

### 5.4 Replaced or retired

**Nothing.** ClickHouse remains operational source of truth, artifact store, and Grafana data source. Any future consolidation (e.g. dropping `algo.hyperparam_trials` once W&B sweeps prove sufficient) is out of scope and would be a separate decision.

---

## 6. Duplicated by design

These overlaps are intentional — the cost of keeping ClickHouse authoritative while W&B becomes the visible surface:

| Data | ClickHouse home | W&B home | Why both |
|---|---|---|---|
| Backtest run metadata | `algo.experiment_runs` | `algo-research` run config + summary | ClickHouse = SQL-queryable source of truth. W&B = interactive Reports + cross-run comparison. |
| Per-day predictions / errors | `algo.experiment_predictions` | `algo-research` run history + Table | ClickHouse for reconciliation joins. W&B for visual per-day error charts inside Reports. |
| Optuna trial results | `algo.hyperparam_trials` | `algo-research` sweep | ClickHouse for cross-study SQL. W&B for parallel-coords + HP-importance viz — the killer demo feature. |
| Model artifacts | `algo.model_artifacts` (joblib blob) | W&B Artifact (same blob) | ClickHouse for `load_latest_artifact()` in `LiveRunner`. W&B for the run → artifact → deployment lineage UI. |
| Live prediction metadata | `algo.experiment_runs` + `algo.experiment_predictions` | `algo-research` predict run | Same number, two views. Lets the demo click into any specific day. |
| Reconciled daily prod metric | `algo.experiment_runs.metrics_json` (re-inserted post-reconciliation) | `algo-prod` daily timeseries | Grafana's "Model Performance" dashboard reads CH; the demo dashboard reads W&B. |

Explicitly **not** duplicated: drift reports, retrain audit events, raw `timeseries` / `forecasts` data, Loki logs, Slack alerts.

---

## 7. W&B project structure

Two projects under the DTU team workspace (configurable via `WANDB_ENTITY`).

### `algo-research`
- One run per backtest, predict, ablation, and DNN training session.
- One sweep per `forecast-cli tune` invocation and per `forecast-cli ablate` invocation.
- Run grouping: `area` (`DK1`, `DE`, …).
- Tags: `model_type` (`lear`, `dnn`), `config_name`, `git_sha` (from the same `GIT_SHA` env var already baked into the Docker image), `study_name` when applicable.

### `algo-prod`
- One continuous run per `(area, config_name)` pair — e.g. `dk1_lear_prod`, `de_lear_prod`. Each reconciliation appends one step.
- Logged metrics per step: `mae`, `rmse`, `smape`, `rmae`, `n_periods_evaluated`, `target_date`.
- Tags: `area`, `config_name`.

### Reports
Live at the team-workspace level so a single Report can pull panels from both projects (e.g. backtest accuracy alongside deployed prod accuracy on one page).

Initial Reports to seed:
- `Variance Stabilizing Transformation` (Gap 2)
- `Calibration Window Selection` (Gap 4)
- `Exogenous Feature Selection` (Gap 6)
- `DM / GW Statistical Tests` (Gap 1 — already has a reading guide; Report visualizes the test results)
- `DNN Architecture Search` (driven by `forecast-cli tune` + `ablate`)

Reports start as drafts and accumulate panels as runs land. They are the thesis-chapter deliverable form.

---

## 8. Configuration and secrets

New environment variables (all consumed by `observability_wandb.client_factory`):

| Var | Required | Purpose |
|---|---|---|
| `WANDB_API_KEY` | Yes (for online mode) | DTU academic license key. Stored in host `.env`. |
| `WANDB_ENTITY` | Yes | DTU team workspace name. |
| `WANDB_PROJECT` | Defaults to `algo-research` | Override for the prod-mirror sync (uses `algo-prod`). |
| `WANDB_MODE` | Defaults to `online`. Set to `disabled` in local dev / CI / unit tests to make the tracker a no-op. | Mirrors the `SLACK_WEBHOOK_URL` graceful-degradation pattern. |

Wiring:
- Host `.env` carries the secrets locally.
- `deploy_forecast.py` injects `WANDB_*` into each ephemeral flow container's env block.
- GitHub Actions secrets store `WANDB_API_KEY` **only if** CI is later expanded to log runs; v1 keeps CI offline (`WANDB_MODE=disabled` in workflows).

Local development workflow unchanged: omit the vars, `WANDB_MODE=disabled` is the effective default, tracker no-ops.

---

## 9. Reliability and failure modes

- **W&B outage / unreachable.** `WandbTracker` wraps every API call in a try/except logged to Loki at WARNING. Failures do not propagate up — production reconciliation, daily forecast, and backtests all keep functioning. ClickHouse remains the durable record.
- **Missing credentials.** `WANDB_MODE=disabled` (default when `WANDB_API_KEY` is unset) makes the tracker a no-op. Local dev and CI never fail for missing creds.
- **Schema drift between ClickHouse and W&B.** The `WandbTracker` is the single owner of the W&B-side schema. Any change to logged fields is one place to edit, mirroring the `infrastructure_clickhouse.ingest` pattern.
- **Cost / rate limits.** Academic license is generous; per-step DNN logging is the heaviest path. If rate-limit issues appear, `LightningModel` can switch to per-N-step logging via an existing config knob.

---

## 10. Demo storyboard for defense

1. Open the `algo-research` project. Filter to DK1 + LEAR. Show ~100 backtest runs.
2. Switch to parallel-coordinates view: calibration windows × test MAE. Pick a candidate combination.
3. Click into one backtest run — show per-day error chart, DM/GW p-value matrix Table vs. baseline.
4. Open the **"Variance Stabilizing Transformation" Report** — annotated comparison of `standard` vs `asinh` scaling, significance verdict, embedded recommendation.
5. Open the DNN tuning sweep — HP importance plot, top-10 trials Table, click into best trial → per-epoch loss curves, multi-seed divergence.
6. Open `algo-prod` project — daily reconciled MAE chart for the deployed LEAR model, weekly aggregation overlay.
7. Pivot to Grafana ("…and the operational side") — drift dashboard, alert rules. Acknowledge: W&B for research story, Grafana for ops.

---

## 11. Authoring Reports via W&B MCP (developer tooling)

The W&B MCP server (`mcp.withwandb.com/mcp`, hosted by W&B) is a Model Context Protocol endpoint that lets Claude Code (and other agentic coding tools) read W&B data and create/edit Reports directly. It is **developer tooling**, not part of the algo-repo runtime — no production code path calls it. It exists specifically to accelerate the Report-authoring workflow that motivates this whole migration.

### Capabilities exposed
- **Read-only**: runs, sweeps, configs, metrics, artifacts, registry, project discovery.
- **Read-write**: Reports (create, append panels, edit markdown).
- Works against SaaS W&B with the same `WANDB_API_KEY` already used by `observability_wandb`.

### Setup
Add an entry to the repo-level `.mcp.json` (or the user's `~/.claude/settings.json`):

```jsonc
{
  "mcpServers": {
    "wandb": {
      "url": "https://mcp.withwandb.com/mcp",
      "headers": { "Authorization": "Bearer ${WANDB_API_KEY}" }
    }
  }
}
```

The exact config schema follows W&B's published docs at https://docs.wandb.ai/platform/mcp-server. The setup steps belong in `docs/RUNBOOK.md` under a new "Authoring W&B Reports with Claude" subsection so future contributors can wire it in.

### Intended workflow
1. User opens a Claude Code session with the MCP server connected.
2. User asks: *"Pull the calibration-window sweep for `dk1_lear` and tell me which window combo wins on validation MAE."* Claude calls the MCP `runs` tools, returns the answer with citations to specific run IDs.
3. User asks: *"Draft a Report for the VST ablation referencing runs X, Y, Z."* Claude calls the MCP `reports` tools to create the Report with embedded panels.
4. User reviews the draft in W&B, gives feedback in the Claude session, Claude iterates via further MCP calls.

### Boundaries and risks
- **Auth scope.** The MCP key has read access to everything the W&B API key sees. Use a personal academic API key (not the shared DTU team key) if any sensitivity is a concern.
- **No runtime coupling.** The MCP server is a Claude Code feature; algo-repo itself never imports or calls it. If the MCP server is unavailable, only the human-in-the-loop authoring workflow is affected — system code keeps running.
- **No code in the repo depends on MCP.** This section documents an external tool, not a module under `src/`.

### Out of scope
- Wiring MCP into CI / Prefect / any system process.
- Using MCP-produced Reports as a programmatic output of the system (Reports remain human-curated artifacts).

---

## 12. Open questions

None blocking. The following could refine v2:

- Whether to retire `algo.hyperparam_trials` once W&B sweeps prove sufficient (probably no — SQL access from notebooks is useful).
- Whether reconciliation should also push `actual` and `predicted` per-period series to W&B (one row/day is enough for a chart; per-period would clutter the prod run and is already in Grafana via ClickHouse).
- Whether to add a `predict --no-wandb` flag for ad-hoc one-offs that shouldn't pollute the project.

---

## 13. References

- `docs/REPO_OVERVIEW.md` — current architecture (commit `2d5989a`).
- `CLAUDE.md` — project conventions.
- `researh_material/reading_guides/mlops_best_practices_reading_guide.md` — P1–P9 scorecard against this repo.
- `docs/RESEARCH_BRIEF.md` — open thesis-defensibility gaps that the new Reports address.
- Zarour, M., Alzabut, H. & Al-Sarayreh, K. (2025). *MLOps best practices, challenges and maturity models: A systematic literature review.* Information and Software Technology, 183.
- W&B MCP Server documentation — https://docs.wandb.ai/platform/mcp-server
