# Observability Split: Grafana vs W&B — Design Spec

**Date:** 2026-05-25
**Status:** Draft, awaiting user review.
**Related work:**
- `docs/superpowers/specs/2026-05-21-wandb-migration-design.md` — established the W&B research surface that this spec cleans up the boundaries of.
- `docs/superpowers/specs/2026-05-23-prometheus-integration-design.md` — the in-flight Prometheus tier (Grafana side); already aligned with this framework.
- `docs/superpowers/plans/2026-05-22-mlops-system-chapter.md` — the thesis chapter whose §3.8 prose this spec updates.

---

## 1. Goal

Define a clean, non-overlapping split of responsibilities between Grafana and W&B across the ML lifecycle, then remove the overlap that exists today. The goals are:

1. **Narrative clarity** for the thesis chapter: one sentence answers "what does Grafana do, what does W&B do, where is the boundary?"
2. **Minimize custom code:** delete Grafana panels/queries that duplicate what W&B already gives for free.
3. **Close two small lineage gaps** in the W&B prod surface (artifact link, drift events) so the research-side view is investigation-complete.

ClickHouse remains the single source of truth for every numerical fact in the system. Grafana and W&B are *views* over the same tables, optimized for different questions.

---

## 2. The framework

**One-line rule.** *Grafana = "is the platform working and how much money did we make?"; W&B = "are the models good and how do they compare?"*

| Tool | Owns | Primary question |
|---|---|---|
| **Grafana** | Infra metrics (Prometheus), data quality, logs (Loki), file-provisioned alert rules, PnL (future) | "Is the platform working and how much money did we make?" |
| **W&B** | Experimentation (backtests, ablations, sweeps, tune), training curves, artifacts + lineage, prod model-quality time-series, ad-hoc Reports | "Are the models good and how do they compare?" |
| **ClickHouse** | All raw data + predictions + actuals + drift reports + retrain events + experiment runs | Single source of truth; both surfaces read from it |

The contested step in the ML lifecycle is **reconciled production accuracy (MAE/RMSE/sMAPE per day)**. Decision: **W&B owns it.** Grafana's Model Performance dashboard is deleted. The accuracy-degradation Slack alert stays in `schedules/reconciliation.py` (Python-side) where it already lives.

A second seam is **drift detection**: Grafana owns the *threshold fire* (the existing `drift-detected-today` alert rule), W&B owns the *investigation view* (a new per-(area, config) drift step series). They are complementary, not duplicative.

---

## 3. Lifecycle map

The full ML loop and the tool that owns each step:

| # | Step | Owner | Notes |
|---|---|---|---|
| 1 | ENTSO-E ingestion | Grafana | Data Quality dashboard + staleness alert |
| 2 | Data prep / EDA | W&B (ad-hoc) | Reports for thesis figures; no Grafana panels for EDA |
| 3 | Experimentation (backtest, ablate) | W&B | `algo-research` project |
| 4 | Training (DNN epochs) | W&B | Lightning `WandbLogger` |
| 5 | Model artifacts | W&B catalog over CH bytes | `algo.model_artifacts` is the byte store; W&B Artifact is the catalog |
| 6 | Live prediction | W&B (`algo-prod`) | One step per (area, config, target_date) |
| 7 | Reconciled accuracy | **W&B (sole owner after this spec)** | Was duplicated in Grafana; that goes |
| 8 | Drift detection | Both | Grafana = fire; W&B = investigate |
| 9 | Retrain audit | Grafana / CH | `algo.retrain_events` time-series; no W&B coupling |
| 10 | Infra health (uptime, CH internals) | Grafana | Prometheus tier per the Prometheus spec |
| 11 | Alerting rules | Grafana (file-provisioned YAML) + Python (`schedules/alerting.notify`) | W&B alerts are out of scope |
| 12 | PnL (future) | Grafana | Reserved slot; out of scope for this spec |

---

## 4. Scope

### In scope

**Deletions**
- `grafana/dashboards/model_performance.json` — removed entirely.
- Any datasource provisioning entry that exists solely for this dashboard (verify at implementation time; the existing Loki + ClickHouse datasources stay).

**Additions to `WandbTracker`**
- New method `log_drift_event(area, config_name, target_date, drift_score, drift_threshold, stat_test, drift_detected)` that posts one step to the `algo-prod` continuous run for `(area, config_name)`.
- Extension to `log_prod_reconciled(...)` accepting an optional `model_artifact_id: str | None = None`; when present, it lands in the step payload as `model_artifact_id`.

**Wiring**
- `schedules/reconciliation.py` reads the `model_artifact_id` already on the run row and passes it through `log_prod_reconciled`.
- `schedules/drift.py` calls `tracker.log_drift_event(...)` after writing each `algo.drift_reports` row. No change to the existing Grafana alert path.

**Documentation**
- `docs/REPO_OVERVIEW.md` §11 (Observability) — rewritten to the framework table above; the piecemeal Grafana/Loki/Drift/W&B subsections collapse into a single "Split of responsibilities" section.
- `Report/chapters/system_implementation.tex` §3.8 P8 prose — Grafana dashboard list changes from `{Data Quality, Model Performance, Operational}` to `{Data Quality, Operational, System Health}` (System Health from the Prometheus plan). One sentence added: "Model-quality metrics live in W&B's `algo-prod` project."
- `scripts/report/README.md` (new) — documents the hybrid figure policy: W&B-sourced figures (training curves, sweeps, ablations) vs matplotlib-sourced figures (architecture diagrams, headline numbers, statistical tests).

### Out of scope (explicit non-decisions)

- **PnL dashboard design.** Acknowledged as a future Grafana dashboard; the framework reserves the slot but no panels, queries, or position-size logic are specified.
- **Migrating all thesis figures to W&B Reports.** Hybrid stays: W&B for sweeps/training, matplotlib for chapter PDF.
- **W&B alerts / alertmanager.** Slack notifications from `schedules/alerting.notify` remain the single notification surface. W&B's native alert rules are not configured.
- **Removing the `algo.experiment_runs.metrics_json` column** from ClickHouse. The data stays in CH (source of truth); only the *Grafana view* over it is deleted.
- **Changing the Prometheus integration plan.** That plan is already framework-aligned; nothing in this spec modifies it.

---

## 5. Detailed changes

### 5.1 Delete Grafana Model Performance dashboard

File: `grafana/dashboards/model_performance.json`

Action: `git rm`. No replacement panel in Grafana. The data the dashboard surfaced (`algo.experiment_runs.metrics_json` per `(area, config)` over time) is exactly what W&B `algo-prod` already shows, with richer comparison.

Verification: after restart, `curl -fs -u admin:admin "http://localhost:3000/api/search?query=Model+Performance"` returns `[]`.

### 5.2 Extend `WandbTracker.log_prod_reconciled`

File: `src/observability_wandb/src/observability_wandb/tracker.py`

Add optional keyword-only param:

```python
def log_prod_reconciled(
    self,
    *,
    area: str,
    config_name: str,
    target_date: str,
    metrics: Mapping[str, float],
    model_artifact_id: str | None = None,   # new
) -> None:
```

When set, include in the step payload:

```python
payload["model_artifact_id"] = model_artifact_id
```

When `None`, the field is omitted (no `null` clutter in W&B history).

### 5.3 Add `WandbTracker.log_drift_event`

Same file. Drift is **per-area** (per `algo.drift_reports` schema and the existing `drift-detection-<area>` deployment), not per-config — it measures input-distribution drift across input curves (`curve_name`), and only the *retrain trigger* downstream is config-aware. Drift events therefore live in a separate per-area continuous run, distinct from the `(area, config_name)` reconciliation runs.

New method on the tracker, no-op when disabled:

```python
def log_drift_event(
    self,
    *,
    area: str,
    curve_name: str,
    target_date: str,
    drift_score: float,
    drift_threshold: float,
    stat_test: str,
    drift_detected: bool,
) -> None:
    if not self._enabled:
        return None
    key = ("__drift__", area)
    run = self._prod_runs.get(key)
    if run is None:
        run = self._wandb.init(
            project=_PROD_PROJECT,
            entity=self._settings.entity,
            id=f"prod-drift-{area.lower()}",
            resume="allow",
            job_type="prod-drift",
            tags=[area, "drift"],
            config={"area": area},
        )
        self._prod_runs[key] = run
    run.log({
        "target_date": target_date,
        "curve_name": curve_name,
        "drift_score": drift_score,
        "drift_threshold": drift_threshold,
        "stat_test": stat_test,
        "drift_detected": int(drift_detected),
    })
```

The cache key `("__drift__", area)` is namespaced so it cannot collide with a reconciliation run keyed by `(area, config_name)` in the same `_prod_runs` dict. The W&B run ID `prod-drift-{area_lower}` parallels the reconciliation IDs `prod-{area_lower}-{config_name}` and makes both kinds discoverable in the `algo-prod` project list.

### 5.4 Wire `model_artifact_id` through reconciliation

File: `src/schedules/src/schedules/reconciliation.py`

The unreconciled run row already includes `model_artifact_id`. Thread it into the W&B call:

```python
tracker.log_prod_reconciled(
    area=run["area"],
    config_name=run["config_name"],
    target_date=target_date_str,
    metrics=metrics,
    model_artifact_id=run.get("model_artifact_id") or None,
)
```

### 5.5 Wire `log_drift_event` into the drift flow

File: `src/schedules/src/schedules/drift.py`

After each `insert_drift_report(...)` call (one per `curve_name`), add:

```python
tracker.log_drift_event(
    area=area,
    curve_name=curve_name,
    target_date=current_end_utc.date().isoformat(),
    drift_score=drift_score,
    drift_threshold=drift_threshold,
    stat_test=stat_test,
    drift_detected=drift_detected,
)
```

One step per `(area, curve_name)` per drift run. All curves for an area land in the same `prod-drift-{area}` W&B run, so the resulting chart shows multiple drift series (one per input curve) on a shared time axis. This mirrors what `algo.drift_reports` already records.

### 5.6 Update `docs/REPO_OVERVIEW.md` §11

Replace the current piecemeal subsections (Grafana / Loki / Drift / W&B) with the framework table from §2 of this spec, the one-line rule, and the lifecycle map from §3 (condensed). The detailed table layouts (datasources, dashboards, alert rules) stay; only the *narrative ordering* changes.

### 5.7 Update thesis chapter §3.8 P8 prose

File: `Report/chapters/system_implementation.tex`

- Change the dashboard list in the *Our implementation* paragraph from three (Data Quality, Model Performance, Operational) to three (Data Quality, Operational, System Health) — System Health enters from the Prometheus plan, Model Performance exits to W&B.
- Add one sentence: *"Model-quality metrics (MAE, RMSE, sMAPE per reconciled day, per area, per config) live in the W&B \texttt{algo-prod} project and are not duplicated in Grafana; Grafana hosts platform-and-money concerns, W&B hosts model-quality concerns."*

### 5.8 Create `scripts/report/README.md`

A short policy file (~20 lines) documenting which thesis figures come from where:

- **From W&B exports:** training curves (`LightningModel`), sweep parallel-coordinate plots (`forecast-cli tune`), ablation comparison charts (`forecast-cli ablate`).
- **From matplotlib scripts in `scripts/report/`:** architecture diagram, headline number tables, DM/GW p-value matrix.
- **Rule of thumb:** if the figure compares ≥2 runs, it comes from W&B. If it's a single static artifact, it comes from a script.

---

## 6. Order of operations

1. Documentation first (§5.6, §5.7, §5.8) — locks the framework before code moves.
2. Tracker extensions (§5.2, §5.3) — tests-first, no consumer wiring yet.
3. Wiring (§5.4, §5.5) — adds the new calls in the two schedule flows.
4. Deletion (§5.1) — Grafana Model Performance dashboard removed, restart Grafana, verify the API search returns empty.

Steps 2 and 3 are tested with the existing `fake_wandb` fixture (see `tests/observability_wandb/conftest.py`); no live W&B calls in tests.

---

## 7. Failure modes

- **W&B disabled (no `WANDB_API_KEY`):** All new methods are no-ops by design (the existing `_enabled` gate). The drift flow and reconciliation flow continue to work; only the W&B-side view is empty. ClickHouse still has everything.
- **Tracker call fails inside `drift.py` or `reconciliation.py`:** today both flows treat tracker calls as non-fatal (existing W&B integration pattern). Confirm at implementation time; if not, wrap in `try/except` with a logged warning so the flow always completes.
- **Stale Grafana dashboards cache:** after deletion, Grafana may keep the panel in browser cache for a session. Hard-refresh or restart the container; verified by API search returning empty.

---

## 8. Acceptance criteria

1. `grafana/dashboards/model_performance.json` no longer exists in the repo.
2. `curl -fs -u admin:admin "http://localhost:3000/api/search?query=Model+Performance"` returns `[]` after restart.
3. `tests/observability_wandb/test_tracker.py` includes passing tests for the new `model_artifact_id` field on `log_prod_reconciled` and for `log_drift_event`.
4. A fresh drift flow run for area `X` lands `N` new W&B steps (one per input `curve_name`) in the `prod-drift-{x_lower}` run inside `algo-prod`, each containing `curve_name`, `drift_score`, `drift_threshold`, `stat_test`, `drift_detected`.
5. A fresh reconciliation flow run lands `model_artifact_id` in the W&B step payload (visible in the W&B run history).
6. `docs/REPO_OVERVIEW.md` §11 contains the framework table and the one-line rule verbatim.
7. `Report/chapters/system_implementation.tex` §3.8 lists three Grafana dashboards (Data Quality, Operational, System Health) and one sentence locating model-quality metrics in W&B.
8. `scripts/report/README.md` exists and documents the W&B vs matplotlib split.
9. No `src/` business logic changed beyond the two `schedules/` files and the one `observability_wandb/tracker.py` file.

---

## 9. Open questions

None at spec-write time. The hybrid thesis-figure policy is deliberately under-specified (§5.8 README is short by design); the per-figure decision lives with the chapter authors.
