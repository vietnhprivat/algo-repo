# Observability Split (Grafana vs W&B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the Grafana-vs-W&B responsibility split from the design spec: W&B becomes the sole owner of model-quality metrics (delete the Grafana Model Performance dashboard), add `model_artifact_id` lineage and a per-area drift run to `WandbTracker`, wire both into the existing reconciliation and drift flows, and refresh the prose in `REPO_OVERVIEW.md`, the thesis chapter §3.8 P8, and a new `scripts/report/README.md`.

**Architecture:** No new packages. Two small extensions to `src/observability_wandb/src/observability_wandb/tracker.py` (keyword-only `model_artifact_id` on `log_prod_reconciled`, plus a new `log_drift_event` method with its own per-area run cache key). Two small additions in `src/schedules/`: thread the artifact id through reconciliation, add a single drift-event call in `drift.py`. Documentation transcribes the framework already locked in the spec.

**Tech Stack:** Python 3.13, uv workspace, `wandb` (already declared as a dep of `observability-wandb`), pytest with the existing `fake_wandb` fixture under `tests/observability_wandb/conftest.py`, Markdown for docs, LaTeX for the thesis chapter.

**Source spec:** `docs/superpowers/specs/2026-05-25-observability-split-design.md` (commit `af04ba5`).

---

## Pre-flight reading (mandatory)

Before any task, the implementing engineer reads, in this order:

1. `docs/superpowers/specs/2026-05-25-observability-split-design.md` — authoritative spec.
2. `src/observability_wandb/src/observability_wandb/tracker.py` — current tracker; `log_prod_reconciled` lives at lines 89–114, the `_prod_runs` cache at line 24, `_PROD_PROJECT` at line 17. **The implementations of `log_prod_reconciled` and the new `log_drift_event` share the `_prod_runs` cache; the cache key shape must stay `tuple[str, str]` to avoid a type change.**
3. `tests/observability_wandb/test_tracker.py` — existing tracker tests; class layout is `class TestXxx:` per method. The `enabled_env` fixture and `fake_wandb` fixture both come from `tests/observability_wandb/conftest.py`.
4. `tests/observability_wandb/conftest.py` — `FakeWandb` shape; `FakeRun` has `logged`, `finished`, `tags`, `artifacts_logged`; `FakeWandb.init(**kwargs)` registers an init call and returns a `FakeRun`.
5. `src/schedules/src/schedules/reconciliation.py` — `_log_run_to_wandb` helper at lines 49–62 (currently does not pass `model_artifact_id`); the call site is lines 222–238 (wrapped in try/except already).
6. `src/schedules/src/schedules/drift.py` — no W&B integration yet; `insert_drift_report` call is at lines 176–192; `curve_name` is computed at line 121 (`f"ENTSOE {area} EnergyPrice"`); `drift_score`, `drift_threshold`, `stat_test`, `drift_detected` are all available locally from line 170 onwards.
7. `tests/schedules/test_reconciliation_wandb.py` — existing single test calls `reconciliation._log_run_to_wandb` directly. We extend it.
8. `tests/schedules/test_drift.py` — existing drift tests use Evidently fakes; check structure before adding the W&B test alongside.
9. `docs/REPO_OVERVIEW.md` lines 863–920 — the Observability section we rewrite.
10. `Report/chapters/system_implementation.tex` — three anchor lines: 477–480 (P8 dashboards list), 629 ("Model Performance dashboard" reference in the GIT\_SHA propagation paragraph), 689 (maturity table row for P8).

Reads are cheap; assumptions cost rewrites. Do not skip.

---

## File map

### New files

- `scripts/report/README.md` — hybrid thesis-figure policy.

### Modified files

- `src/observability_wandb/src/observability_wandb/tracker.py` — extend `log_prod_reconciled` with optional `model_artifact_id`; add `log_drift_event` method.
- `tests/observability_wandb/test_tracker.py` — new test cases for the two changes.
- `src/schedules/src/schedules/reconciliation.py` — thread `model_artifact_id` through `_log_run_to_wandb` → `tracker.log_prod_reconciled`.
- `tests/schedules/test_reconciliation_wandb.py` — extend with an artifact-id assertion.
- `src/schedules/src/schedules/drift.py` — add a `tracker.log_drift_event(...)` call after `insert_drift_report(...)`, wrapped in try/except like the reconciliation call.
- `tests/schedules/test_drift.py` (or a new `test_drift_wandb.py` next to it) — assert the drift task posts a step to a `prod-drift-{area}` W&B run.
- `docs/REPO_OVERVIEW.md` — rewrite §11 Observability around the framework.
- `Report/chapters/system_implementation.tex` — §3.8 P8 prose, GIT\_SHA propagation paragraph, P8 maturity-table row.

### Deleted files

- `grafana/dashboards/model_performance.json` — removed entirely.

---

## Conventions enforced by every task

- **Tests before code** for the tracker and wiring tasks. Documentation tasks have no test.
- **No live W&B network calls in tests.** Use the existing `fake_wandb` fixture.
- **No `print()` for new logging in `src/`.** Use the existing module-level `LOGGER`s and `build_log_extra(...)` (already imported in both `reconciliation.py` and `drift.py`).
- **No emojis in code, commit messages, or docs.**
- **Commit message convention:** match existing repo style — short type prefix, no scope (`feat:`, `test:`, `docs:`, `chore:`). No `Co-Authored-By` trailer (the repo does not use them).
- **Each task ends with a `git commit` step.** Tasks land one logical change per commit.
- **All new code is typed.** Return-annotated, keyword-only kwargs for tracker methods.
- **Branch:** all work happens on `feat/observability-split` (already created in the brainstorming session, with the spec committed at `af04ba5`).

---

## Task 1: Rewrite `docs/REPO_OVERVIEW.md` §11 (Observability)

**Files:**
- Modify: `docs/REPO_OVERVIEW.md` — replace lines 863–920 (the `## 11. Observability` section through the end of the `### W&B (research)` subsection, ending just before the `---` and `## 12. CI/CD` separator).

- [ ] **Step 1: Verify the section boundaries**

Run: `sed -n '863p;920p;921p' docs/REPO_OVERVIEW.md`
Expected:
```
## 11. Observability
- New CLI: `forecast-cli ablate <config> --vary <field> --over <json>`.

```

If the lines do not match (line numbers drifted), search instead:

Run: `grep -n '^## 11\.\|^## 12\.' docs/REPO_OVERVIEW.md`

Use the resulting `## 11.` line as the start, the `## 12.` line minus 2 (to skip the trailing `---` and blank line) as the end.

- [ ] **Step 2: Replace the section**

Open `docs/REPO_OVERVIEW.md` and replace the entire `## 11. Observability` block (from the heading down through the last bullet under `### W&B (research)`) with:

```markdown
## 11. Observability

The observability stack splits cleanly along one axis:

> **Grafana** answers *"is the platform working and how much money did we make?"*
> **W&B** answers *"are the models good and how do they compare?"*
> **ClickHouse** is the single source of truth that both surfaces read from.

### Split of responsibilities

| Tool | Owns | Primary question |
|---|---|---|
| **Grafana** | Infra metrics (Prometheus), data quality, logs (Loki), file-provisioned alert rules, PnL (future) | Is the platform working and how much money did we make? |
| **W&B** | Experimentation (backtests, ablations, sweeps, tune), training curves, artifacts + lineage, prod model-quality time-series, ad-hoc Reports | Are the models good and how do they compare? |
| **ClickHouse** | All raw data + predictions + actuals + drift reports + retrain events + experiment runs | Single source of truth |

The contested seam in the ML lifecycle is **reconciled production accuracy**: W&B owns it. The accuracy-degradation Slack alert in `schedules/reconciliation.py` stays Python-side. Drift is dual-surfaced: Grafana fires the threshold alert (`drift-detected-today`), W&B hosts the investigation view (per-area `prod-drift-{area}` run).

### Grafana

Three auto-provisioned dashboards (`grafana/dashboards/*.json`):

1. **Data Quality** — coverage and freshness of `algo.timeseries` and `algo.forecasts`.
2. **Operational** — Loki log stream filtered by `job=algo-repo`.
3. **System Health** — Prometheus-backed uptime and ClickHouse internals (`up{}`, query rate, resident memory, merge backlog).

> **Always edit dashboards as JSON** in `grafana/dashboards/`. UI edits are overwritten on container restart.

### Loki

Logs are pushed directly from Python via `python-logging-loki`. Labels are the values in `extra=` (filtered through `build_log_extra`). Default service tags: `job="algo-repo"`, `application="algo-repo"`. Each module's logger is created with a `service=` name (e.g. `prefect-ingestion`, `prefect-forecast`, `prefect-reconciliation`, `prefect-drift`, `entsoe-client`, `clickhouse-ingest`).

### Drift & operational alerts

Two layers:

1. **Slack via `schedules.alerting.notify`** — fired in-process by the reconciliation flow (accuracy degradation) and the drift flow (drift detected, retrain triggered/completed/failed). Safe no-op when `SLACK_WEBHOOK_URL` is unset.
2. **Grafana file-provisioned alert rules** at `grafana/provisioning/alerting/rules.yaml` — four rules:
   - `data-staleness`: fires when `max(timestamp_utc)` in `algo.timeseries` is more than 12 hours stale.
   - `drift-detected-today`: fires when any row in `algo.drift_reports` for today has `drift_detected = 1`.
   - `reconciliation-missed`: fires when no `reconcile-predictions` run has completed in the last 25 hours.
   - `clickhouse-down`: fires when `up{job="clickhouse"}` has been 0 for five minutes.

> **Always edit alert rules as YAML** in `grafana/provisioning/alerting/`. UI edits are overwritten on container restart, same as dashboards.

### W&B

`observability_wandb.tracker.WandbTracker` is the single owner of W&B-side schema. Dual-write call sites: `forecast_cli.tracking.track_backtest_run / track_prediction`, `price_forecasting.models.lightning_base.LightningModel` (via `WandbLogger`), `price_forecasting.tuning.optuna_storage`, `schedules.reconciliation`, and `schedules.drift`. Production system is unaffected when the tracker is disabled.

- `algo-research` project — backtests, predict runs, DNN training, sweeps, ablations.
- `algo-prod` project — two run families:
  - `prod-{area_lower}-{config_name}` — one continuous run per `(area, config_name)`, one step per reconciled day. Step payload: `mae`, `rmse`, `smape`, `target_date`, and `model_artifact_id` (lineage back to `algo.model_artifacts`).
  - `prod-drift-{area_lower}` — one continuous run per area, one step per drift check (per `(area, curve_name)` pair). Step payload: `target_date`, `curve_name`, `drift_score`, `drift_threshold`, `stat_test`, `drift_detected`.
- Disabled-mode: set `WANDB_MODE=disabled` or unset `WANDB_API_KEY`.
- Ablation CLI: `forecast-cli ablate <config> --vary <field> --over <json>`.
```

- [ ] **Step 3: Spot-check markdown rendering**

Run: `grep -n '^## 11\.' docs/REPO_OVERVIEW.md`
Expected: exactly one match.

Run: `grep -c '^### ' docs/REPO_OVERVIEW.md`
Expected: an integer greater than before; verify by reading the file that the new subsections (`### Split of responsibilities`, `### Grafana`, `### Loki`, `### Drift & operational alerts`, `### W&B`) are present.

- [ ] **Step 4: Commit**

```bash
git add docs/REPO_OVERVIEW.md
git commit -m "docs: rewrite REPO_OVERVIEW observability section around Grafana/W&B split"
```

---

## Task 2: Update `Report/chapters/system_implementation.tex` §3.8 prose

**Files:**
- Modify: `Report/chapters/system_implementation.tex` (three spots: ~lines 475–490, ~line 629, ~line 689).

- [ ] **Step 1: Locate the three anchors**

Run: `grep -n "Three Grafana dashboards auto-provision\|Model Performance dashboard\|P8 --- Continuous monitoring" Report/chapters/system_implementation.tex`

Expected: three line-number hits, one per anchor. Note the line numbers; they may have drifted from the values quoted here.

- [ ] **Step 2: Edit the §3.8 P8 dashboards passage**

In `Report/chapters/system_implementation.tex`, find this passage (currently lines 475–480) inside `\subsection{P8 — Continuous monitoring}`:

```latex
Three Grafana dashboards auto-provision from
\texttt{grafana/dashboards/}: the Data Quality dashboard covers coverage and
freshness of \texttt{algo.timeseries} and \texttt{algo.forecasts}; the Model
Performance dashboard surfaces MAE, RMSE, and sMAPE per run from
\texttt{algo.experiment\_runs}; and the Operational dashboard presents the
Loki log stream filtered by \texttt{job=algo-repo}.
```

Replace it with:

```latex
Three Grafana dashboards auto-provision from
\texttt{grafana/dashboards/}: the Data Quality dashboard covers coverage and
freshness of \texttt{algo.timeseries} and \texttt{algo.forecasts}; the
Operational dashboard presents the Loki log stream filtered by
\texttt{job=algo-repo}; and the System Health dashboard (introduced in §3.8.x
above) covers ClickHouse and Grafana liveness via Prometheus. Model-quality
metrics --- MAE, RMSE, and sMAPE per reconciled day, per area, per config ---
do not live in Grafana; they are owned by the W\&B \texttt{algo-prod} project,
which the dual-write tracker in \texttt{observability\_wandb} updates from
\texttt{schedules.reconciliation}. The split reflects a deliberate boundary:
Grafana hosts platform-and-money concerns, W\&B hosts model-quality concerns,
and the two surfaces read from the same ClickHouse tables for the facts they
care about.
```

(The phrase `(introduced in §3.8.x above)` is a soft reference — the System Health dashboard is introduced earlier in §3.8 by the Prometheus integration; an explicit cross-reference is not required because §3.8 is one subsection.)

- [ ] **Step 3: Edit the GIT\_SHA propagation paragraph**

Find this sentence (currently around line 629):

```latex
from that same image. This means that if the Model Performance dashboard
shows an unexpected MAE spike beginning on a particular day, the Operational
dashboard will show the Loki events from the same period alongside the
\texttt{git\_sha} of the image that produced them
```

Replace with:

```latex
from that same image. This means that if the W\&B \texttt{algo-prod} run for
a given \texttt{(area, config\_name)} shows an unexpected MAE spike beginning
on a particular day, the Grafana Operational dashboard will show the Loki
events from the same period alongside the \texttt{git\_sha} of the image that
produced them
```

- [ ] **Step 4: Edit the P8 maturity-table row**

Find this row (currently around line 689):

```latex
    P8 --- Continuous monitoring        & Realised & 2 & Loki plus three Grafana dashboards plus file-based alert rules \\
```

Replace with:

```latex
    P8 --- Continuous monitoring        & Realised & 2 & Loki plus three Grafana dashboards (Data Quality, Operational, System Health) plus file-based alert rules; model-quality metrics in W\&B \texttt{algo-prod} \\
```

- [ ] **Step 5: Re-compile the standalone**

```bash
cd Report
pdflatex -interaction=nonstopmode system_implementation_standalone.tex >/dev/null && echo OK
cd ..
```

Expected: `OK`. If the compile fails, examine `Report/system_implementation_standalone.log` for an unescaped ampersand or stray brace in the W&B text.

- [ ] **Step 6: Verify no other "Model Performance" references remain**

Run: `grep -n "Model Performance\|model_performance" Report/chapters/system_implementation.tex`
Expected: no output (all three references updated). If a hit remains, repeat the edit at that line.

- [ ] **Step 7: Commit**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): update P8 prose for Grafana/W&B split"
```

---

## Task 3: Create `scripts/report/README.md`

**Files:**
- Create: `scripts/report/README.md`.

- [ ] **Step 1: Verify the directory exists**

Run: `ls scripts/report/`
Expected: `extract_metrics.py`, `__init__.py`, possibly a `__pycache__`. Do NOT create a `__pycache__` entry.

- [ ] **Step 2: Write the file**

Create `scripts/report/README.md` with this content (exact, no placeholders):

```markdown
# Report figure & metric policy

The thesis chapter `Report/chapters/system_implementation.tex` pulls numbers
and figures from two sources. This document records the policy so future
edits stay consistent.

## Where each figure comes from

| Figure / number | Source | Why |
|---|---|---|
| Training loss / val-loss curves | W&B export (`algo-research`) | The W&B run already stores per-epoch series; re-deriving in matplotlib duplicates effort. |
| Hyperparameter-sweep parallel-coordinate plots | W&B export (`algo-research`) | W&B's HP plot is the canonical view of a sweep. |
| Ablation comparison charts (`forecast-cli ablate`) | W&B export (`algo-research`) | Each ablation variant is a sibling run; W&B group-by handles it natively. |
| Reconciled production accuracy time-series | W&B export (`algo-prod`, run `prod-{area}-{config}`) | The continuous run is the source of truth post-spec. |
| Architecture diagrams (`f1-arch`, `f2-flows`, `f3-cicd`) | Hand-built (Excalidraw / TikZ) | Static, not derived from a run. |
| Headline number tables (§5 Quantitative Evaluation) | `scripts/report/extract_metrics.py` → `Report/metrics/quantitative_results.md` | Reproducible from ClickHouse + Prometheus on demand. |
| DM / GW p-value matrix | Hand-built matplotlib in `scripts/report/` (or future module) | Cross-model comparison, derived from `algo.experiment_predictions`. |
| System availability table (§5.2) | `scripts/report/extract_metrics.py:collect_availability` (Prometheus) | Reproducible. |

## Rule of thumb

- If a figure compares **two or more runs** (sweeps, ablations, model A vs model B), it comes from W&B.
- If a figure is a **single static artifact** (architecture diagram, headline number table, p-value matrix), it comes from a matplotlib script under `scripts/report/` (or is hand-built).

## Disabled W&B

When `WANDB_MODE=disabled` (local development), W&B-sourced figures are not
regenerated. The PDF in `main` always ships with the last committed
W&B exports; CI does not re-render them. If a W&B export is updated, commit
the new PNG / PDF alongside the chapter edit that references it.

## Related

- `Report/chapters/system_implementation.tex` — the chapter consuming these figures.
- `docs/REPO_OVERVIEW.md` §11 — the framework these figures support.
- `docs/superpowers/specs/2026-05-25-observability-split-design.md` — the spec that established this policy.
```

- [ ] **Step 3: Sanity-check the file**

Run: `wc -l scripts/report/README.md`
Expected: a count between 30 and 60. (Sanity check that the file was written, not empty.)

- [ ] **Step 4: Commit**

```bash
git add scripts/report/README.md
git commit -m "docs: document hybrid W&B/matplotlib figure policy for the report"
```

---

## Task 4: Extend `WandbTracker.log_prod_reconciled` with `model_artifact_id`

**Files:**
- Modify: `src/observability_wandb/src/observability_wandb/tracker.py` (function at lines 89–114).
- Modify: `tests/observability_wandb/test_tracker.py` (append two new tests in `TestLogProdReconciled`).

- [ ] **Step 1: Write the failing tests**

Open `tests/observability_wandb/test_tracker.py` and append the following two tests **inside** the existing `class TestLogProdReconciled:` block (after `test_distinct_runs_per_area_config`, before the next `class`):

```python
    def test_model_artifact_id_is_logged_when_present(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_prod_reconciled(
            area="DK1",
            config_name="dk1_lear",
            target_date="2026-05-21",
            metrics={"mae": 4.5},
            model_artifact_id="art-uuid-9",
        )

        payload = fake_wandb.runs[0].logged[0][0]
        assert payload["model_artifact_id"] == "art-uuid-9"

    def test_model_artifact_id_omitted_when_none(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_prod_reconciled(
            area="DK1",
            config_name="dk1_lear",
            target_date="2026-05-21",
            metrics={"mae": 4.5},
        )

        payload = fake_wandb.runs[0].logged[0][0]
        assert "model_artifact_id" not in payload
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/observability_wandb/test_tracker.py::TestLogProdReconciled -v`

Expected: the two new tests FAIL — `model_artifact_id` is not an accepted kwarg on `log_prod_reconciled` (TypeError).

- [ ] **Step 3: Extend the method signature and body**

In `src/observability_wandb/src/observability_wandb/tracker.py`, replace the existing `log_prod_reconciled` method (currently lines 89–114) with:

```python
    def log_prod_reconciled(
        self,
        *,
        area: str,
        config_name: str,
        target_date: str,
        metrics: Mapping[str, float],
        model_artifact_id: str | None = None,
    ) -> None:
        if not self._enabled:
            return None
        key = (area, config_name)
        run = self._prod_runs.get(key)
        if run is None:
            run = self._wandb.init(
                project=_PROD_PROJECT,
                entity=self._settings.entity,
                id=f"prod-{area.lower()}-{config_name}",
                resume="allow",
                job_type="prod-reconciled",
                tags=[area, config_name],
                config={"area": area, "config_name": config_name},
            )
            self._prod_runs[key] = run
        payload: dict[str, Any] = dict(metrics)
        payload["target_date"] = target_date
        if model_artifact_id is not None:
            payload["model_artifact_id"] = model_artifact_id
        run.log(payload)
```

- [ ] **Step 4: Run, expect PASS for all `TestLogProdReconciled` tests**

Run: `uv run pytest tests/observability_wandb/test_tracker.py::TestLogProdReconciled -v`
Expected: 5 PASS (the three existing + the two new).

- [ ] **Step 5: Run the full tracker test file to confirm no regression**

Run: `uv run pytest tests/observability_wandb/test_tracker.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/observability_wandb/src/observability_wandb/tracker.py tests/observability_wandb/test_tracker.py
git commit -m "feat(observability_wandb): add model_artifact_id to log_prod_reconciled"
```

---

## Task 5: Add `WandbTracker.log_drift_event`

**Files:**
- Modify: `src/observability_wandb/src/observability_wandb/tracker.py` (add new method).
- Modify: `tests/observability_wandb/test_tracker.py` (append a new test class).

- [ ] **Step 1: Write the failing tests**

Append a new class at the end of `tests/observability_wandb/test_tracker.py`:

```python
class TestLogDriftEvent:
    def test_first_call_inits_drift_run_in_algo_prod_project(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_drift_event(
            area="DK1",
            curve_name="ENTSOE DK1 EnergyPrice",
            target_date="2026-05-21",
            drift_score=0.12,
            drift_threshold=0.05,
            stat_test="ks",
            drift_detected=True,
        )

        call = fake_wandb.init_calls[0]
        assert call["project"] == "algo-prod"
        assert call["id"] == "prod-drift-dk1"
        assert call["resume"] == "allow"
        assert call["job_type"] == "prod-drift"
        assert "DK1" in call["tags"]
        assert "drift" in call["tags"]

        run = fake_wandb.runs[0]
        assert run.finished is False  # continuous, do not finish
        payload = run.logged[0][0]
        assert payload == {
            "target_date": "2026-05-21",
            "curve_name": "ENTSOE DK1 EnergyPrice",
            "drift_score": 0.12,
            "drift_threshold": 0.05,
            "stat_test": "ks",
            "drift_detected": 1,
        }

    def test_second_call_same_area_reuses_run(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_drift_event(
            area="DK1", curve_name="ENTSOE DK1 EnergyPrice",
            target_date="2026-05-20", drift_score=0.10,
            drift_threshold=0.05, stat_test="ks", drift_detected=True,
        )
        tracker.log_drift_event(
            area="DK1", curve_name="ENTSOE DK1 EnergyPrice",
            target_date="2026-05-21", drift_score=0.11,
            drift_threshold=0.05, stat_test="ks", drift_detected=True,
        )

        assert len(fake_wandb.init_calls) == 1
        assert len(fake_wandb.runs[0].logged) == 2

    def test_drift_and_reconciled_runs_are_independent(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        """Drift and reconciliation share a tracker but live in separate runs."""
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_prod_reconciled(
            area="DK1", config_name="dk1_lear",
            target_date="2026-05-21", metrics={"mae": 4.5},
        )
        tracker.log_drift_event(
            area="DK1", curve_name="ENTSOE DK1 EnergyPrice",
            target_date="2026-05-21", drift_score=0.12,
            drift_threshold=0.05, stat_test="ks", drift_detected=True,
        )

        assert len(fake_wandb.init_calls) == 2
        ids = {c["id"] for c in fake_wandb.init_calls}
        assert ids == {"prod-dk1-dk1_lear", "prod-drift-dk1"}

    def test_distinct_drift_runs_per_area(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_drift_event(
            area="DK1", curve_name="ENTSOE DK1 EnergyPrice",
            target_date="2026-05-21", drift_score=0.10,
            drift_threshold=0.05, stat_test="ks", drift_detected=False,
        )
        tracker.log_drift_event(
            area="DE", curve_name="ENTSOE DE EnergyPrice",
            target_date="2026-05-21", drift_score=0.08,
            drift_threshold=0.05, stat_test="ks", drift_detected=True,
        )

        assert len(fake_wandb.init_calls) == 2
        ids = {c["id"] for c in fake_wandb.init_calls}
        assert ids == {"prod-drift-dk1", "prod-drift-de"}

    def test_noop_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch, fake_wandb: FakeWandb
    ) -> None:
        monkeypatch.setenv("WANDB_MODE", "disabled")
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_drift_event(
            area="DK1", curve_name="ENTSOE DK1 EnergyPrice",
            target_date="2026-05-21", drift_score=0.10,
            drift_threshold=0.05, stat_test="ks", drift_detected=False,
        )

        assert fake_wandb.init_calls == []
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/observability_wandb/test_tracker.py::TestLogDriftEvent -v`
Expected: all 5 FAIL with `AttributeError: 'WandbTracker' object has no attribute 'log_drift_event'`.

- [ ] **Step 3: Implement the method**

In `src/observability_wandb/src/observability_wandb/tracker.py`, append a new method **inside the `WandbTracker` class**, after `log_predict_run_with_artifact`:

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
        run.log(
            {
                "target_date": target_date,
                "curve_name": curve_name,
                "drift_score": drift_score,
                "drift_threshold": drift_threshold,
                "stat_test": stat_test,
                "drift_detected": int(drift_detected),
            }
        )
```

The cache key `("__drift__", area)` shares the dict type with reconciliation's `(area, config_name)` key but is namespaced by the literal `"__drift__"` so collisions are impossible.

- [ ] **Step 4: Run, expect PASS for the new class**

Run: `uv run pytest tests/observability_wandb/test_tracker.py::TestLogDriftEvent -v`
Expected: 5 PASS.

- [ ] **Step 5: Run the full tracker test file**

Run: `uv run pytest tests/observability_wandb/test_tracker.py -v`
Expected: all PASS (existing + the two from Task 4 + the five from Task 5).

- [ ] **Step 6: Commit**

```bash
git add src/observability_wandb/src/observability_wandb/tracker.py tests/observability_wandb/test_tracker.py
git commit -m "feat(observability_wandb): add log_drift_event with per-area continuous run"
```

---

## Task 6: Wire `model_artifact_id` through `schedules.reconciliation`

**Files:**
- Modify: `src/schedules/src/schedules/reconciliation.py` (helper at lines 49–62, call site at lines 222–238).
- Modify: `tests/schedules/test_reconciliation_wandb.py` (extend the existing test).

- [ ] **Step 1: Extend the test**

Open `tests/schedules/test_reconciliation_wandb.py` and append, after the existing `test_reconciliation_logs_to_prod_project`:

```python
def test_reconciliation_passes_model_artifact_id_to_wandb(
    enabled_env: None,
    fake_wandb: FakeWandb,
) -> None:
    """When the run has a model_artifact_id, it lands in the W&B step payload."""
    from schedules import reconciliation

    tracker = WandbTracker(wandb_module=fake_wandb)

    reconciliation._log_run_to_wandb(
        tracker=tracker,
        area="DK1",
        config_name="dk1_lear",
        target_date="2026-05-21",
        metrics={"mae": 4.5, "rmse": 6.1, "smape": 11.0},
        model_artifact_id="art-uuid-42",
    )

    payload = fake_wandb.runs[0].logged[0][0]
    assert payload["model_artifact_id"] == "art-uuid-42"


def test_reconciliation_omits_artifact_id_when_blank(
    enabled_env: None,
    fake_wandb: FakeWandb,
) -> None:
    """Empty-string artifact_id (the CH default for old runs) is treated as None."""
    from schedules import reconciliation

    tracker = WandbTracker(wandb_module=fake_wandb)

    reconciliation._log_run_to_wandb(
        tracker=tracker,
        area="DK1",
        config_name="dk1_lear",
        target_date="2026-05-21",
        metrics={"mae": 4.5},
        model_artifact_id="",
    )

    payload = fake_wandb.runs[0].logged[0][0]
    assert "model_artifact_id" not in payload
```

- [ ] **Step 2: Run, expect FAIL**

Run: `uv run pytest tests/schedules/test_reconciliation_wandb.py -v`
Expected: the two new tests FAIL — `_log_run_to_wandb` does not accept `model_artifact_id`.

- [ ] **Step 3: Extend `_log_run_to_wandb`**

In `src/schedules/src/schedules/reconciliation.py`, replace the existing helper (lines 49–62) with:

```python
def _log_run_to_wandb(
    *,
    tracker: WandbTracker,
    area: str,
    config_name: str,
    target_date: str,
    metrics: dict[str, float],
    model_artifact_id: str | None = None,
) -> None:
    # ClickHouse stores model_artifact_id as a non-nullable String; old rows have
    # the empty string. Treat blanks as absent so the W&B payload stays clean.
    cleaned = model_artifact_id if model_artifact_id else None
    tracker.log_prod_reconciled(
        area=area,
        config_name=config_name,
        target_date=target_date,
        metrics=metrics,
        model_artifact_id=cleaned,
    )
```

- [ ] **Step 4: Wire it at the call site**

Find the call site (currently lines 224–231) inside `reconcile_area_task`:

```python
            try:
                _log_run_to_wandb(
                    tracker=tracker,
                    area=area,
                    config_name=config_name,
                    target_date=target_date,
                    metrics=metrics,
                )
```

Replace it with:

```python
            try:
                _log_run_to_wandb(
                    tracker=tracker,
                    area=area,
                    config_name=config_name,
                    target_date=target_date,
                    metrics=metrics,
                    model_artifact_id=run.get("model_artifact_id"),
                )
```

The surrounding `try / except Exception as exc:` block stays unchanged.

- [ ] **Step 5: Run, expect PASS**

Run: `uv run pytest tests/schedules/test_reconciliation_wandb.py -v`
Expected: 3 PASS (the original + the two new).

- [ ] **Step 6: Run the rest of the reconciliation tests to confirm no regression**

Run: `uv run pytest tests/schedules/test_reconciliation.py tests/schedules/test_accuracy_alert.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add src/schedules/src/schedules/reconciliation.py tests/schedules/test_reconciliation_wandb.py
git commit -m "feat(schedules): thread model_artifact_id from reconciliation into W&B"
```

---

## Task 7: Wire `log_drift_event` into `schedules.drift`

**Files:**
- Modify: `src/schedules/src/schedules/drift.py` (add tracker import and call after `insert_drift_report`).
- Create: `tests/schedules/test_drift_wandb.py` (new file, parallels `test_reconciliation_wandb.py`).

- [ ] **Step 1: Inspect the existing `test_drift.py` to confirm how the drift task is tested**

Run: `head -40 tests/schedules/test_drift.py`

Expected: the file uses Evidently fakes or hand-built sample windows to exercise `detect_drift_for_area_task`. Note the import style and any fixtures you can reuse. (If the test file does not exist, the new W&B test will stand alone — that's fine.)

- [ ] **Step 2: Write the failing W&B test**

Create `tests/schedules/test_drift_wandb.py`:

```python
"""Drift flow pushes one step per drift check to the prod-drift-{area} W&B run."""

from __future__ import annotations

import pytest

from observability_wandb.tracker import WandbTracker

from tests.observability_wandb.conftest import FakeWandb


@pytest.fixture
def enabled_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WANDB_API_KEY", "k")
    monkeypatch.setenv("WANDB_ENTITY", "e")
    monkeypatch.setenv("WANDB_MODE", "online")


def test_drift_logs_to_prod_drift_run(
    enabled_env: None,
    fake_wandb: FakeWandb,
) -> None:
    """The drift module's _log_drift_to_wandb helper posts one step to W&B."""
    from schedules import drift

    tracker = WandbTracker(wandb_module=fake_wandb)

    drift._log_drift_to_wandb(
        tracker=tracker,
        area="DK1",
        curve_name="ENTSOE DK1 EnergyPrice",
        target_date="2026-05-21",
        drift_score=0.12,
        drift_threshold=0.05,
        stat_test="ks",
        drift_detected=True,
    )

    call = fake_wandb.init_calls[0]
    assert call["project"] == "algo-prod"
    assert call["id"] == "prod-drift-dk1"

    payload = fake_wandb.runs[0].logged[0][0]
    assert payload["curve_name"] == "ENTSOE DK1 EnergyPrice"
    assert payload["drift_score"] == 0.12
    assert payload["drift_detected"] == 1


def test_drift_helper_swallows_tracker_errors(
    monkeypatch: pytest.MonkeyPatch,
    fake_wandb: FakeWandb,
) -> None:
    """A tracker exception must not abort the drift flow."""
    from schedules import drift

    class BoomTracker:
        def log_drift_event(self, **_: object) -> None:
            raise RuntimeError("boom")

    drift._log_drift_to_wandb(
        tracker=BoomTracker(),
        area="DK1",
        curve_name="ENTSOE DK1 EnergyPrice",
        target_date="2026-05-21",
        drift_score=0.12,
        drift_threshold=0.05,
        stat_test="ks",
        drift_detected=True,
    )
    # No exception bubbled. Nothing else to assert.
```

- [ ] **Step 3: Run, expect FAIL**

Run: `uv run pytest tests/schedules/test_drift_wandb.py -v`
Expected: both tests FAIL — `schedules.drift` has no `_log_drift_to_wandb`.

- [ ] **Step 4: Implement the helper and the call site in `drift.py`**

Open `src/schedules/src/schedules/drift.py`.

(a) Add the tracker import to the existing import block (after the existing `from schedules.retrain import triggered_retrain_flow` line, near line 30):

```python
from observability_wandb.tracker import WandbTracker
```

(b) Add the helper at module scope, after the `_compute_drift` function and before `@task(...)` for `detect_drift_for_area_task` (i.e., between the current line 112 and line 115):

```python
def _log_drift_to_wandb(
    *,
    tracker: WandbTracker,
    area: str,
    curve_name: str,
    target_date: str,
    drift_score: float,
    drift_threshold: float,
    stat_test: str,
    drift_detected: bool,
) -> None:
    try:
        tracker.log_drift_event(
            area=area,
            curve_name=curve_name,
            target_date=target_date,
            drift_score=drift_score,
            drift_threshold=drift_threshold,
            stat_test=stat_test,
            drift_detected=drift_detected,
        )
    except Exception as exc:  # noqa: BLE001 — never crash the drift flow over W&B
        LOGGER.warning(
            "W&B drift-event sync failed; continuing",
            extra=build_log_extra(area=area, curve_name=curve_name, error=str(exc)),
        )
```

(c) Inside `detect_drift_for_area_task`, locate the `try / finally` block currently at lines 137–194. Immediately **after** the `insert_drift_report(...)` call (currently ending at line 192) and **before** the `finally:` line (currently 193), append:

```python
        _log_drift_to_wandb(
            tracker=WandbTracker(),
            area=area,
            curve_name=curve_name,
            target_date=windows.current_end.date().isoformat(),
            drift_score=drift_score,
            drift_threshold=drift_threshold,
            stat_test=stat_test,
            drift_detected=drift_detected,
        )
```

Indentation: the new block sits inside the `try:` body, at the same indent as `insert_drift_report(...)` — eight spaces from the left margin.

- [ ] **Step 5: Run, expect PASS for the new test**

Run: `uv run pytest tests/schedules/test_drift_wandb.py -v`
Expected: 2 PASS.

- [ ] **Step 6: Run the existing drift tests to confirm no regression**

Run: `uv run pytest tests/schedules/test_drift.py tests/schedules/test_drift_retrain_hook.py -v`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add src/schedules/src/schedules/drift.py tests/schedules/test_drift_wandb.py
git commit -m "feat(schedules): emit drift events to W&B prod-drift-{area} run"
```

---

## Task 8: Delete `grafana/dashboards/model_performance.json`

**Files:**
- Delete: `grafana/dashboards/model_performance.json`.

- [ ] **Step 1: Confirm the file exists and confirm nothing else references it**

Run: `ls grafana/dashboards/model_performance.json`
Expected: `grafana/dashboards/model_performance.json`.

Run: `grep -rn "model_performance" --include="*.json" --include="*.yml" --include="*.yaml" --include="*.tex" --include="*.md" --include="*.py" . 2>/dev/null | grep -v '^./docs/superpowers/' | grep -v node_modules | grep -v '__pycache__'`

Expected: the only hit is `./grafana/dashboards/model_performance.json` itself (its title field). If anything else points at this file (a provisioning manifest, a Python script), STOP and adapt — the deletion must not orphan a reference. Spec-related plan / spec files matching `model_performance` are excluded (grep above filters them out via `docs/superpowers/`).

- [ ] **Step 2: Delete the file**

```bash
git rm grafana/dashboards/model_performance.json
```

- [ ] **Step 3: Restart Grafana and verify the dashboard is gone**

```bash
docker compose restart grafana
sleep 10
curl -fs -u admin:admin "http://localhost:3000/api/search?query=Model+Performance"
```

Expected: `[]` (empty JSON array). If the dashboard still appears, the Grafana sidecar may have cached it — `docker compose restart grafana` once more and re-curl.

If you customized `GRAFANA_ADMIN_PASSWORD` in `.env`, substitute it for `admin` in the `-u` flag.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(grafana): remove Model Performance dashboard (now owned by W&B algo-prod)"
```

(The `git rm` already staged the deletion.)

---

## Task 9: Final verification against the acceptance criteria

**Files:**
- No file changes; verification only.

- [ ] **Step 1: Run the entire test suite**

Run: `uv run pytest tests/ -q`
Expected: all PASS. Total count should exceed the pre-plan baseline by at least 9 (Task 4: 2, Task 5: 5, Task 6: 2, Task 7: 2). If any unrelated test fails, investigate — none of the changes in this plan should affect unrelated paths.

- [ ] **Step 2: Spec acceptance criteria pass-through**

Verify each of the spec's nine acceptance criteria (`docs/superpowers/specs/2026-05-25-observability-split-design.md` §8) as shell checks:

```bash
# 1. Dashboard file deleted
test ! -f grafana/dashboards/model_performance.json && echo "1. DELETED ✓" || echo "1. FAIL"

# 2. Grafana API does not list it (requires the stack to be up; skip if not)
if docker compose ps grafana 2>/dev/null | grep -q "Up"; then
  result=$(curl -fs -u admin:admin "http://localhost:3000/api/search?query=Model+Performance")
  [ "$result" = "[]" ] && echo "2. GRAFANA EMPTY ✓" || echo "2. FAIL — $result"
else
  echo "2. SKIPPED (Grafana not running locally)"
fi

# 3. New tracker tests exist
grep -q "test_model_artifact_id_is_logged_when_present" tests/observability_wandb/test_tracker.py && \
grep -q "class TestLogDriftEvent" tests/observability_wandb/test_tracker.py && \
echo "3. TRACKER TESTS ✓" || echo "3. FAIL"

# 4. Drift wiring test exists
grep -q "test_drift_logs_to_prod_drift_run" tests/schedules/test_drift_wandb.py && echo "4. DRIFT TEST ✓" || echo "4. FAIL"

# 5. Reconciliation wiring test exists
grep -q "test_reconciliation_passes_model_artifact_id_to_wandb" tests/schedules/test_reconciliation_wandb.py && echo "5. RECON TEST ✓" || echo "5. FAIL"

# 6. REPO_OVERVIEW framework table present
grep -q "platform is working and how much money did we make" docs/REPO_OVERVIEW.md && echo "6. OVERVIEW ✓" || echo "6. FAIL"

# 7. Chapter §3.8 updated
grep -q "Model Performance" Report/chapters/system_implementation.tex && echo "7. FAIL — Model Performance still in chapter" || echo "7. CHAPTER ✓"

# 8. scripts/report/README.md exists
test -f scripts/report/README.md && echo "8. README ✓" || echo "8. FAIL"

# 9. No src/ business logic changed outside the three expected files
git diff main -- src/ | grep '^+++' | sort -u
```

For criterion 9, the expected output of the last diff line is exactly three files: `src/observability_wandb/src/observability_wandb/tracker.py`, `src/schedules/src/schedules/reconciliation.py`, `src/schedules/src/schedules/drift.py`. Any other file under `src/` appearing in the diff is a scope violation — investigate and revert.

- [ ] **Step 2.5: Optional — re-compile the chapter PDF**

If a fresh PDF is desired:

```bash
cd Report
pdflatex -interaction=nonstopmode system_implementation_standalone.tex
bibtex system_implementation_standalone
pdflatex -interaction=nonstopmode system_implementation_standalone.tex
pdflatex -interaction=nonstopmode system_implementation_standalone.tex
cd ..
```

Expected: final pass exits 0 with no `Warning: There were undefined references`. The PDF is not committed by this plan (build artifact policy in this repo commits PDFs alongside chapter edits in dedicated PDF-refresh commits; do that in a separate commit if desired).

- [ ] **Step 3: Push and open a PR**

```bash
git push -u origin feat/observability-split
gh pr create --title "Observability split: Grafana vs W&B (delete Model Perf, add drift+artifact lineage)" --body "$(cat <<'EOF'
## Summary
- Delete Grafana Model Performance dashboard; W&B `algo-prod` becomes sole owner of model-quality metrics.
- Add `model_artifact_id` lineage to `log_prod_reconciled` and thread it through reconciliation.
- New `WandbTracker.log_drift_event` writing per-area `prod-drift-{area}` runs; wired into the drift flow.
- Refresh `REPO_OVERVIEW.md` §11 and thesis chapter §3.8 P8 prose around the new framework.
- New `scripts/report/README.md` documenting the hybrid W&B / matplotlib figure policy.

## Test plan
- [ ] `uv run pytest tests/ -q` passes locally
- [ ] Grafana restart confirms `/api/search?query=Model+Performance` returns `[]`
- [ ] Manual run of `schedules.reconciliation.reconcile_predictions_flow()` populates `model_artifact_id` on the next W&B step
- [ ] Manual run of `schedules.drift.drift_detection_flow(area="DK1")` creates a `prod-drift-dk1` run

Spec: `docs/superpowers/specs/2026-05-25-observability-split-design.md`
EOF
)"
```

---

## Out-of-band: dependencies between tasks

- Tasks 1, 2, 3 (documentation) are independent of each other and of the code tasks. They can run in any order, including in parallel.
- Task 4 must precede Task 6 — the reconciliation wiring depends on the extended tracker signature.
- Task 5 must precede Task 7 — the drift wiring depends on the new `log_drift_event` method.
- Task 8 (delete dashboard) is independent of the W&B-side tasks but conceptually depends on the W&B side being in place; landing the deletion last is the conservative ordering.
- Task 9 (verification) is strictly last.

---

## Self-Review

**Spec coverage** — checked the spec section by section:

- §2 (framework) → Task 1 (REPO_OVERVIEW), Task 2 (chapter). Covered.
- §3 (lifecycle map) → Task 1 includes the table verbatim. Covered.
- §4 (scope: in/out) → every "in" item maps to a task; every "out" item is honored (no PnL design, no W&B alert config, no `algo.experiment_runs.metrics_json` column removal, no edits to the Prometheus plan). Covered.
- §5.1 (delete dashboard) → Task 8. Covered.
- §5.2 (extend `log_prod_reconciled`) → Task 4. Covered.
- §5.3 (add `log_drift_event`) → Task 5. Covered.
- §5.4 (wire reconciliation) → Task 6. Covered.
- §5.5 (wire drift) → Task 7. Covered.
- §5.6 (REPO_OVERVIEW edits) → Task 1. Covered.
- §5.7 (chapter prose) → Task 2 (three anchors handled, including the GIT\_SHA paragraph and the P8 maturity row, not just the dashboards list). Covered.
- §5.8 (`scripts/report/README.md`) → Task 3. Covered.
- §6 (order of operations) → restated in this plan's "Out-of-band: dependencies" section, with the same ordering. Covered.
- §7 (failure modes) → addressed by the existing `try/except` patterns kept in Task 6 (reconciliation) and added in Task 7 (drift's `_log_drift_to_wandb`); explicitly tested by `test_drift_helper_swallows_tracker_errors`. Covered.
- §8 (acceptance criteria) → Task 9 runs each as a shell check, with criterion 9 specifically constraining the `src/` diff to the three expected files. Covered.
- §9 (open questions) → none open; this plan introduces none. Covered.

**Placeholder scan** — searched the plan for "TBD", "TODO", "implement later", "fill in details", "similar to Task N", "add appropriate error handling". Only literal mentions are in the No-Placeholders rule of the writing-plans skill (this section). No real placeholders remain. The phrase `(introduced in §3.8.x above)` in Task 2 step 2 is a deliberate soft reference inside chapter prose, not a placeholder — see the surrounding sentence in Task 2 for the rationale.

**Type consistency** — cross-checked across tasks:

- `model_artifact_id: str | None = None` — same type at the tracker (Task 4), the reconciliation helper (Task 6 step 3), and the test assertions. Empty string is normalized to `None` only in `reconciliation._log_run_to_wandb` (Task 6 step 3), with a dedicated test (`test_reconciliation_omits_artifact_id_when_blank`).
- `log_drift_event` signature: same kwargs in Task 5 step 3 (impl) and Task 7 step 4(c) (call site) — `area, curve_name, target_date, drift_score, drift_threshold, stat_test, drift_detected`.
- W&B IDs: `prod-{area_lower}-{config_name}` (reconciliation) and `prod-drift-{area_lower}` (drift) used consistently in code, tests, and the REPO_OVERVIEW table.
- Cache key namespacing: `("__drift__", area)` for drift vs `(area, config_name)` for reconciliation — same `dict[tuple[str, str], Any]` type, no collision, matches the existing `_prod_runs` declaration on tracker.py line 24.
