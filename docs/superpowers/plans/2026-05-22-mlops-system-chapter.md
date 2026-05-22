# MLOps System Chapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a thesis-grade LaTeX chapter that documents the
algo-repo platform's MLOps implementation, structured around Zarour
(2025)'s nine practices, so an examiner with no prior project context
can read it cold and judge the system.

**Architecture:** One `.tex` chapter file at
`Report/chapters/system_implementation.tex` plus four standalone TikZ
figures under `Report/figures/system_implementation/`. Content is
driven by `docs/REPO_OVERVIEW.md`, `CLAUDE.md`, the MLOps plan
(`docs/superpowers/plans/2026-05-20-mlops-and-epf-fidelity.md`), and
the live `deploy_*.py` + `.github/workflows/*` files — the writing
agent reads these before drafting each section.

**Tech Stack:** LaTeX (lualatex or pdflatex), TikZ, BibTeX. No Python
code, no application code changes. Spec at
`docs/superpowers/specs/2026-05-22-mlops-system-chapter-design.md` is
the authoritative source for structure, citation rules, and forbidden
patterns — re-read whenever in doubt.

---

## Pre-flight reading (mandatory)

Before any task, the writing agent reads, in this order:

1. `docs/superpowers/specs/2026-05-22-mlops-system-chapter-design.md`
2. `docs/REPO_OVERVIEW.md`
3. `CLAUDE.md`
4. `docs/superpowers/plans/2026-05-20-mlops-and-epf-fidelity.md`
   (specifically the "Self-Review Notes" P-mapping near the bottom)
5. `src/schedules/src/schedules/deploy_ingestion.py`
6. `src/schedules/src/schedules/deploy_forecast.py`
7. `.github/workflows/pr_test.yml`,
   `.github/workflows/pr_ruff-lint.yaml`,
   `.github/workflows/pr_smoke.yml`,
   `.github/workflows/cd_deploy.yml`,
   `.github/workflows/main_cache_warm.yml`

Reads are cheap; assumptions cost rewrites. Do not skip.

---

### Task 0: Bootstrap directories and bibliography

**Files:**
- Create: `Report/chapters/` (directory)
- Create: `Report/figures/system_implementation/` (directory)
- Create or modify: `Report/references.bib`

- [ ] **Step 1: Verify directory state**

Run: `ls Report/`
Expected: shows `ProjectPlan.pdf`, no `chapters/` or `figures/` yet.

- [ ] **Step 2: Create the two directories**

```bash
mkdir -p Report/chapters Report/figures/system_implementation
```

- [ ] **Step 3: Create or extend `Report/references.bib` with the two required entries**

If `Report/references.bib` exists, append. If absent, create with:

```bibtex
@article{zarour2025,
  author  = {Zarour, Mohammad and Alzabut, Hussein and Al-Sarayreh, Khalid T.},
  title   = {{MLOps} best practices, challenges and maturity models: A systematic literature review},
  journal = {Information and Software Technology},
  volume  = {183},
  pages   = {107733},
  year    = {2025},
  doi     = {10.1016/j.infsof.2025.107733}
}

@article{lago2021,
  author  = {Lago, Jesus and Marcjasz, Grzegorz and De Schutter, Bart and Weron, Rafa{\l}},
  title   = {Forecasting day-ahead electricity prices: A review of state-of-the-art algorithms, best practices and an open-access benchmark},
  journal = {Applied Energy},
  volume  = {293},
  pages   = {116983},
  year    = {2021},
  doi     = {10.1016/j.apenergy.2021.116983}
}
```

- [ ] **Step 4: Commit**

```bash
git add Report/chapters Report/figures Report/references.bib
git commit -m "docs(report): bootstrap chapters/, figures/, and references.bib"
```

---

### Task 1: Figure F1 — Host-level architecture

**Files:**
- Create: `Report/figures/system_implementation/f1-architecture.tex`
- Create: `Report/figures/system_implementation/f1-architecture.pdf`

- [ ] **Step 1: Read the ASCII source diagram**

Read `docs/REPO_OVERVIEW.md` §2 — the first ASCII figure showing the
docker-compose host with ClickHouse, Prefect server + worker, Loki,
Grafana, and the ephemeral `algo-repo:latest` container that spawns
per flow run.

- [ ] **Step 2: Author `f1-architecture.tex` as a standalone TikZ document**

Constraints:

- `\documentclass[tikz,border=5pt]{standalone}`.
- Use `positioning`, `arrows.meta`, `shapes.geometric` libraries.
- Boxes: ClickHouse (cylinder), Prefect Server, Prefect Worker, Loki,
  Grafana, ephemeral `algo-repo:latest` container.
- Arrow semantics: solid for synchronous reads/writes, dashed for log
  push to Loki, "spawns" arrow from Prefect Worker to the ephemeral
  container.
- No colour beyond grayscale — prints clean.

- [ ] **Step 3: Compile to PDF**

Run:
```bash
cd Report/figures/system_implementation && \
  lualatex -interaction=nonstopmode f1-architecture.tex
```

Expected: `f1-architecture.pdf` produced, no errors.

If neither `lualatex` nor `pdflatex` is installed in the agent's
environment, the agent reports this in the final handoff message and
leaves only the `.tex` file behind.

- [ ] **Step 4: Commit**

```bash
git add Report/figures/system_implementation/f1-architecture.tex \
        Report/figures/system_implementation/f1-architecture.pdf
git commit -m "docs(report): add F1 host architecture figure (TikZ)"
```

---

### Task 2: Figure F2 — Data plane

**Files:**
- Create: `Report/figures/system_implementation/f2-data-plane.tex`
- Create: `Report/figures/system_implementation/f2-data-plane.pdf`

- [ ] **Step 1: Read the ASCII data-plane source**

Read `docs/REPO_OVERVIEW.md` §2 — the second ASCII figure (ENTSO-E →
mappers → ClickHouse → preprocessor → BacktestEngine / LiveRunner →
experiment tracking + model_artifacts → reconciliation → drift).

- [ ] **Step 2: Author `f2-data-plane.tex`**

Constraints:

- Standalone TikZ as in Task 1.
- Left-to-right flow with a vertical branch at `experiment_runs`
  going down to reconciliation and drift.
- Distinct shapes: external systems (ENTSO-E) as cloud,
  ClickHouse tables as cylinders, processing stages as rectangles,
  Slack as a hexagon.
- Annotate the two MAE-degradation and KS-drift conditional arrows
  with the threshold text (`MAE > 1.5× 30-day median`,
  `retrain_on_drift=True`).

- [ ] **Step 3: Compile to PDF**

```bash
cd Report/figures/system_implementation && \
  lualatex -interaction=nonstopmode f2-data-plane.tex
```

Expected: `f2-data-plane.pdf` produced, no errors.

- [ ] **Step 4: Commit**

```bash
git add Report/figures/system_implementation/f2-data-plane.tex \
        Report/figures/system_implementation/f2-data-plane.pdf
git commit -m "docs(report): add F2 data-plane figure (TikZ)"
```

---

### Task 3: Figure F3 — CI/CD pipeline

**Files:**
- Create: `Report/figures/system_implementation/f3-cicd.tex`
- Create: `Report/figures/system_implementation/f3-cicd.pdf`

- [ ] **Step 1: Read the source workflows**

Read all five `.github/workflows/*.yml` files. The figure must reflect
their actual triggers and steps as committed.

- [ ] **Step 2: Author `f3-cicd.tex`**

Constraints:

- Two horizontal swimlanes labelled "GitHub Actions" and "Deploy
  host". The Tailscale link sits on the boundary between them as a
  labelled arrow.
- GitHub Actions lane shows the PR-time workflows (`pr_test`,
  `pr_ruff-lint`, `pr_smoke`) feeding the PR gate, and the post-merge
  `cd_deploy` and `main_cache_warm` workflows.
- Deploy-host lane shows: rebuild `algo-repo:latest`, rerun
  `deploy_ingestion.py` and `deploy_forecast.py`, trigger
  `daily-forecast-dk1_lear`, poll until completion.
- Label the Tailscale arrow with "SSH over Tailscale" so the figure
  is self-explanatory.

- [ ] **Step 3: Compile to PDF**

```bash
cd Report/figures/system_implementation && \
  lualatex -interaction=nonstopmode f3-cicd.tex
```

Expected: `f3-cicd.pdf` produced, no errors.

- [ ] **Step 4: Commit**

```bash
git add Report/figures/system_implementation/f3-cicd.tex \
        Report/figures/system_implementation/f3-cicd.pdf
git commit -m "docs(report): add F3 CI/CD pipeline figure (TikZ)"
```

---

### Task 4: Figure F4 — Drift → retrain feedback loop

**Files:**
- Create: `Report/figures/system_implementation/f4-drift-feedback.tex`
- Create: `Report/figures/system_implementation/f4-drift-feedback.pdf`

- [ ] **Step 1: Read source modules**

Read `src/schedules/src/schedules/drift.py` and
`src/schedules/src/schedules/retrain.py`. Confirm node identities
(`algo.drift_reports`, `algo.retrain_events`, Slack webhook) match the
modules.

- [ ] **Step 2: Author `f4-drift-feedback.tex`**

Constraints:

- Compact three-node loop: `drift_detection_flow` →
  (`algo.drift_reports` + Slack) → `triggered_retrain_flow` →
  `algo.retrain_events` → back to "next-day drift check".
- The `retrain_on_drift=True` branch is highlighted; the alert-only
  branch is dotted.

- [ ] **Step 3: Compile to PDF**

```bash
cd Report/figures/system_implementation && \
  lualatex -interaction=nonstopmode f4-drift-feedback.tex
```

Expected: `f4-drift-feedback.pdf` produced, no errors.

- [ ] **Step 4: Commit**

```bash
git add Report/figures/system_implementation/f4-drift-feedback.tex \
        Report/figures/system_implementation/f4-drift-feedback.pdf
git commit -m "docs(report): add F4 drift feedback figure (TikZ)"
```

---

### Task 5: Chapter scaffold

**Files:**
- Create: `Report/chapters/system_implementation.tex`

- [ ] **Step 1: Author the scaffold**

Write the file with the full sectional skeleton, no content prose yet,
no figure includes yet, no table rows yet — just `\chapter`,
`\section`, `\subsection`, and one-line placeholder *comments* (`%
fill in Task N`). The scaffold must:

- Open with `\chapter{System Implementation}` (the chapter is
  designed to be `\input`-ed into a master thesis document, not
  compiled alone).
- Contain `\section{...}` headings exactly matching spec §6.
- Contain a `\bibliography{../references}` line at the end so the
  later compilation check can resolve `\cite` keys when the chapter
  is rendered standalone for proofing.
- Contain a leading `\iffalse … \fi` block with a one-paragraph
  abstract of the chapter intent — used by the writing agent itself
  as a re-grounding cue, never typeset.

- [ ] **Step 2: Sanity-compile via a temporary wrapper**

Create a throwaway wrapper at
`Report/figures/system_implementation/.scaffold-check.tex`:

```latex
\documentclass{report}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{tikz}
\begin{document}
\input{../../chapters/system_implementation.tex}
\end{document}
```

Run:
```bash
cd Report/figures/system_implementation && \
  lualatex -interaction=nonstopmode .scaffold-check.tex
```

Expected: compiles to a near-empty PDF with chapter and section
headings visible, no errors. Delete the wrapper after the check.

- [ ] **Step 3: Commit**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): scaffold system implementation chapter"
```

---

### Task 6: Section 1 — Introduction

**Files:**
- Modify: `Report/chapters/system_implementation.tex` (replace the
  `% fill in` comment under `\section{Introduction}`)

- [ ] **Step 1: Draft §1.1, §1.2, §1.3**

Content:

- §1.1 *Problem framing — production EPF requires more than a model*:
  two short paragraphs. Cite `\cite{lago2021}` once when noting that
  the EPF research literature focuses on accuracy on offline
  benchmarks while production demands ingestion, retraining,
  monitoring, and roll-forward evaluation.
- §1.2 *Scope of this chapter*: one paragraph explicitly stating
  what is *not* covered (modeling research, RUNBOOK operational
  prose).
- §1.3 *Methodology — Zarour (2025) as the structuring lens*: one
  paragraph explaining why the chapter is organised around P1–P9 and
  what each P-section will contain. Cite `\cite{zarour2025}`.

- [ ] **Step 2: Re-compile via wrapper to confirm well-formed**

Same wrapper approach as Task 5 step 2. Expected: compiles without
errors, §1 content now visible.

- [ ] **Step 3: Commit**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): write section 1 introduction"
```

---

### Task 7: Section 2 — System at a Glance (figures + tables)

**Files:**
- Modify: `Report/chapters/system_implementation.tex` (§2)

- [ ] **Step 1: Verify inventory data at write-time**

Run:
```bash
grep -n "AREAS\|FORECAST_CONFIGS\|DRIFT_AREAS\|cron=" \
  src/schedules/src/schedules/deploy_ingestion.py \
  src/schedules/src/schedules/deploy_forecast.py
```

Read the output. Record the exact values in the agent's working
notes. These values appear verbatim in the inventory table — *not
paraphrased*.

- [ ] **Step 2: Write §2.1 with `\includegraphics{...}` for F1**

```latex
\begin{figure}[h]
  \centering
  \includegraphics[width=\linewidth]{../figures/system_implementation/f1-architecture}
  \caption{Host-level architecture: a single Docker Compose host runs
           ClickHouse, the Prefect server and worker, Loki, and
           Grafana. Flow runs spawn ephemeral \texttt{algo-repo:latest}
           containers that read from ClickHouse, call ENTSO-E, and
           emit logs back to Loki.}
  \label{fig:f1-architecture}
\end{figure}
```

Add one paragraph of prose explaining the figure.

- [ ] **Step 3: Write §2.2 with `\includegraphics{...}` for F2**

Same pattern. One paragraph of prose covering the data plane from
ingestion to drift, with a one-sentence note on `ReplacingMergeTree`
deduplication.

- [ ] **Step 4: Write §2.3 — operational inventory table**

Use `booktabs`. Columns: Deployment name · Area / scope · Cron (UTC)
· Flow module · Purpose · Closes Zarour P*x*.

Rows (write verbatim — agent verifies count and values against the
grep output from step 1):

```
entsoe-ingestion-DK1   DK1   0 * * * *   schedules.ingestion.entsoe_backfill_flow   Hourly ENTSO-E ingest   P1, P2
entsoe-ingestion-DK2   DK2   0 * * * *   …                                          …                        P1, P2
entsoe-ingestion-NL    NL    0 * * * *   …                                          …                        P1, P2
entsoe-ingestion-BE    BE    0 * * * *   …                                          …                        P1, P2
entsoe-ingestion-DE    DE    0 * * * *   …                                          …                        P1, P2
entsoe-ingestion-FR    FR    0 * * * *   …                                          …                        P1, P2
entsoe-ingestion-PL    PL    0 * * * *   …                                          …                        P1, P2
daily-forecast-dk1_lear   DK1 / LEAR   0 6 * * *   schedules.forecast.daily_forecast_flow   Daily refit + day-ahead forecast   P6
daily-forecast-de_lear    DE  / LEAR   0 6 * * *   schedules.forecast.daily_forecast_flow   Daily refit + day-ahead forecast   P6
reconcile-predictions     all          0 18 * * *  schedules.reconciliation.reconcile_predictions_flow   Day-after reconciliation against published actuals   P7, P8
drift-detection-dk1       DK1          0 19 * * *  schedules.drift.drift_detection_flow   90-day reference vs 7-day current, KS test   P8, P9
drift-detection-de        DE           0 19 * * *  schedules.drift.drift_detection_flow   90-day reference vs 7-day current, KS test   P8, P9
```

If the grep output disagrees with any row, the source files are
authoritative — update the table, do not edit the source files.

- [ ] **Step 5: Write §2.4 — tech-stack table**

Use `booktabs`. Columns: Tool · Role · Status · Why this choice.

Rows (one per tool):

```
Prefect          Orchestration                       Kept     Sufficient for single-host flows; lighter than Airflow / Dagster
ClickHouse       OLAP store + model artifact blob    Kept     Columnar performance, ReplacingMergeTree dedup, native Polars / Arrow path
Docker Compose   Container runtime + infra-as-code   Kept     Single-host scope; YAML matches the deploy mental model
Loki             Log aggregation                     Added    Direct python-logging-loki push, no Promtail sidecar
Grafana          Dashboards and file-based alerts    Added    File-provisioned configs survive container restarts
Evidently AI     In-process drift detection          Added    Mode 1 reports; no separate Evidently service
W\&B             Research + production tracking       Added    Two projects (algo-research, algo-prod); WANDB_MODE=disabled in CI
GitHub Actions   CI/CD                               Kept     Native to the GitHub-hosted repo, no self-hosted runner
Tailscale        Deploy host network access          Added    SSH to deploy host without exposing it to the public internet
Optuna           Hyperparameter search (TPE)         Added    Persisted to ClickHouse; revisited per-config rather than per-run
MLflow           Experiment registry                 Deferred Until experiment-config count exceeds ten
Kubernetes       Container orchestration             Deferred Until multi-host deployment is justified
DVC              Data versioning                     Deferred ENTSO-E data is replayable from source; ClickHouse + GIT_SHA suffice
```

- [ ] **Step 6: Re-compile via wrapper**

Expected: compiles without errors, §2 figures and tables render.

- [ ] **Step 7: Commit**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): write section 2 system at a glance"
```

---

### Task 8: Section 3.1 — P1 Version Control

**Files:**
- Modify: `Report/chapters/system_implementation.tex` (§3.1)

- [ ] **Step 1: Draft the P-section following the fixed shape**

Subsections, in order, with the labels from spec §7.1:

1. *Zarour's framing* — paraphrase Zarour P1 in 2–3 sentences. Cite
   `\cite{zarour2025}` once.
2. *Our implementation* — Git + GitHub. Config files in `configs/`
   tracked in version control. Migrations as numbered SQL files in
   `src/infrastructure_clickhouse/migrations/` — auto-discovered by
   sorted glob, never modified retroactively. Grafana dashboards and
   alert rules file-provisioned from `grafana/provisioning/`, *not*
   UI-edited.
3. *Technology choice* — Git over Mercurial / Perforce: no
   justification beyond "industry standard". GitHub as host:
   integration with Tailscale-mediated deploy. Reject DVC for data
   versioning — ENTSO-E is replayable from source and ClickHouse +
   `GIT_SHA` provide reproducibility.
4. *Design rationale* — versioning everything that affects model
   output (configs, migrations, dashboards, alert rules) means a
   single `git log` covers the experiment, the infrastructure, and
   the alerting policy together.

No diagram for §3.1.

- [ ] **Step 2: Re-compile via wrapper. Commit.**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): write P1 version control"
```

---

### Task 9: Section 3.2 — P2 Continuous Integration

**Files:**
- Modify: `Report/chapters/system_implementation.tex` (§3.2)

- [ ] **Step 1: Draft following the fixed shape**

1. *Zarour's framing* — P2 framing + `\cite{zarour2025}`.
2. *Our implementation* — `.github/workflows/pr_test.yml` (pytest),
   `pr_ruff-lint.yaml` (ruff), `pr_smoke.yml` (LEAR end-to-end smoke
   test). PR gate runs all three; the recently-merged
   `ci/smoke-skip-docs-only-pushes` branch skips the smoke step on
   docs-only changes.
3. *Technology choice* — GitHub Actions over Jenkins or CircleCI:
   colocated with the repo, no separate runner host.
4. *Design rationale* — three workflows instead of one keeps the
   smoke test (the slow step) isolated so docs PRs are not held back
   by a 5-minute build.

No diagram for §3.2.

- [ ] **Step 2: Re-compile via wrapper. Commit.**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): write P2 continuous integration"
```

---

### Task 10: Section 3.3 — P3 Reproducibility

**Files:**
- Modify: `Report/chapters/system_implementation.tex` (§3.3)

- [ ] **Step 1: Draft following the fixed shape**

1. *Zarour's framing* — P3 framing + `\cite{zarour2025}`.
2. *Our implementation* — deterministic seeds in the DNN ensemble
   (one seed per replicate, averaged at serve time). Paper-correct
   calibration windows in `configs/dk1_lear.py` and `de_lear.py`. The
   `AsinhScaler` variance-stabilising target transform
   (cite `\cite{lago2021}`). Diebold-Mariano and Giacomini-White
   tests as fidelity evidence (cite `\cite{lago2021}`). The
   `GIT_SHA` environment variable, baked into the production image
   at build time via `--build-arg GIT_SHA=$(git rev-parse HEAD)` in
   `cd_deploy.yml`, lands on every row of `algo.experiment_runs`.
3. *Technology choice* — image-baked `GIT_SHA` over runtime
   `git rev-parse`: the deploy host has no source tree, only the
   built image. Local runs emit `""` so dirty trees never produce
   misleading SHAs.
4. *Design rationale* — reproducibility means recovering both the
   code and the data window; `GIT_SHA` + `data_start_utc` +
   `data_end_utc` on every run row is the minimal sufficient
   provenance.

No diagram for §3.3.

- [ ] **Step 2: Re-compile via wrapper. Commit.**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): write P3 reproducibility"
```

---

### Task 11: Section 3.4 — P4 Containerization

**Files:**
- Modify: `Report/chapters/system_implementation.tex` (§3.4)

- [ ] **Step 1: Draft following the fixed shape**

1. *Zarour's framing* — P4 framing + `\cite{zarour2025}`.
2. *Our implementation* — `Dockerfile` (application image),
   `Dockerfile.worker` (Prefect worker image), `docker-compose.yml`
   (single-host stack). Grafana and Loki configurations live in
   `grafana/provisioning/`. Grafana alert rules in
   `grafana/provisioning/alerting/rules.yaml` are file-based and
   never UI-edited.
3. *Technology choice* — Docker Compose over Kubernetes: single-host
   scope. Reject Helm / k3s — overhead unjustified at MVP scale.
4. *Design rationale* — file-provisioning makes the alerting policy a
   reviewable artifact in Git rather than runtime state, which
   closes the loop with P1.

No diagram for §3.4.

- [ ] **Step 2: Re-compile via wrapper. Commit.**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): write P4 containerization"
```

---

### Task 12: Section 3.5 — P5 Collaboration

**Files:**
- Modify: `Report/chapters/system_implementation.tex` (§3.5)

- [ ] **Step 1: Draft following the fixed shape**

1. *Zarour's framing* — P5 framing + `\cite{zarour2025}`.
2. *Our implementation* — `CLAUDE.md` (project conventions),
   `docs/REPO_OVERVIEW.md` (LLM context primer),
   `docs/RUNBOOK.md` (manual operations),
   `docs/CONTRIBUTING.md` (branching, PR policy, area onboarding).
   Slack alerts as a collaboration surface: drift and
   accuracy-degradation events post to a webhook so the team is
   notified even when nobody is on Grafana.
3. *Technology choice* — Slack webhooks over PagerDuty / Opsgenie:
   single-team scope, no on-call rotation yet.
4. *Design rationale* — documentation is for two distinct readers
   (humans and LLM agents). Splitting human-oriented docs from the
   conventions file lets both stay short and load-bearing.

No diagram for §3.5.

- [ ] **Step 2: Re-compile via wrapper. Commit.**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): write P5 collaboration"
```

---

### Task 13: Section 3.6 — P6 Continuous Training

**Files:**
- Modify: `Report/chapters/system_implementation.tex` (§3.6)

- [ ] **Step 1: Draft following the fixed shape**

1. *Zarour's framing* — P6 framing + `\cite{zarour2025}`.
2. *Our implementation* — the `daily-forecast-<config>` deployments
   refit the model every morning at 06:00 UTC against the latest
   ClickHouse data window. `LiveRunner` is a train-then-predict
   wrapper; for DNN configs it averages `n_dnn_ensemble` replicates
   (cite `\cite{lago2021}`).
3. *Technology choice* — refit-from-scratch per day over incremental
   learning: a daily window of new data is well below the cost
   threshold where incremental learning would matter; clean refit is
   simpler and removes drift-of-the-learner as a confound.
4. *Design rationale* — keeping training inside the same flow as
   prediction means the trained model never sits idle between
   `daily-forecast` and a separate "predict" deployment, and a
   single retry covers both phases.

No diagram for §3.6.

- [ ] **Step 2: Re-compile via wrapper. Commit.**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): write P6 continuous training"
```

---

### Task 14: Section 3.7 — P7 Experiment Tracking and Model Registry

**Files:**
- Modify: `Report/chapters/system_implementation.tex` (§3.7)

- [ ] **Step 1: Draft following the fixed shape**

1. *Zarour's framing* — P7 framing + `\cite{zarour2025}`.
2. *Our implementation* — ClickHouse-backed experiment tracking:
   `algo.experiment_runs` (one row per run, columns include
   `training_duration_seconds`, `data_start_utc`, `data_end_utc`,
   `model_artifact_id`, `git_sha`), `algo.experiment_predictions`
   (one row per period per day), `algo.hyperparam_trials` (Optuna
   trials), `algo.model_artifacts` (base64-encoded joblib blobs).
   W\&B serves the research surface: `algo-research` project for
   ablations and sweeps, `algo-prod` project for production
   reconciliation sync. `WANDB_MODE=disabled` no-ops the tracker in
   CI and local dev.
3. *Technology choice* — MLflow deferred until config count exceeds
   ten; ClickHouse + W\&B together cover both the audit-log role and
   the research-surface role MLflow would fill. Reject filesystem
   model store — ClickHouse blob keeps artifacts attached to the
   experiment row.
4. *Design rationale* — using one OLAP store for both predictions
   and artifacts makes day-after reconciliation a single SQL query
   instead of a join across systems.

No diagram for §3.7.

- [ ] **Step 2: Re-compile via wrapper. Commit.**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): write P7 experiment tracking"
```

---

### Task 15: Section 3.8 — P8 Continuous Monitoring

**Files:**
- Modify: `Report/chapters/system_implementation.tex` (§3.8)

- [ ] **Step 1: Draft following the fixed shape**

1. *Zarour's framing* — P8 framing + `\cite{zarour2025}`.
2. *Our implementation* — structured logging via `python-logging-loki`
   pushed directly to Loki (no Promtail sidecar). Three Grafana
   dashboards auto-provision from `grafana/dashboards/`: Data
   Quality, Model Performance, Operational (Loki log stream).
   File-based alert rules in `grafana/provisioning/alerting/rules.yaml`:
   data-staleness, drift-detected-today, reconciliation-missed.
   Accuracy-degradation alert in
   `schedules.reconciliation._maybe_alert_accuracy_degradation`
   fires when today's MAE exceeds 1.5\,$\times$ the 30-day median.
3. *Technology choice* — Loki over ELK: single-binary, lower
   operational cost. Reject Promtail — direct Python push removes a
   moving part.
4. *Design rationale* — three axes of monitoring (data, model,
   system) match Zarour's P8 decomposition. File-based alert rules
   close the loop with P4: alerting policy is reviewed in Git, never
   edited at runtime.

No diagram for §3.8.

- [ ] **Step 2: Re-compile via wrapper. Commit.**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): write P8 continuous monitoring"
```

---

### Task 16: Section 3.9 — P9 Feedback Loop / Drift-Triggered Retraining

**Files:**
- Modify: `Report/chapters/system_implementation.tex` (§3.9)

- [ ] **Step 1: Draft following the fixed shape**

1. *Zarour's framing* — P9 framing + `\cite{zarour2025}`.
2. *Our implementation* — Evidently runs in-process inside the
   `drift-detection-<area>` Prefect flow (no Evidently service).
   Reference window 90 days, current window 7 days, KS test. Drift
   events land in `algo.drift_reports`. When the config has
   `retrain_on_drift=True`, a `triggered_retrain_flow` writes to
   `algo.retrain_events` and posts a Slack notification.
3. *Technology choice* — in-process Evidently over Evidently
   service: keeps the drift check inside the same Prefect retry
   envelope as the flow itself. Reject Arize / WhyLabs — cloud
   dependency unjustified at single-host MVP scope.
4. *Design rationale* — making the retrain trigger explicit
   (config flag) rather than always-on means the loop is auditable:
   every retrain has a row in `algo.retrain_events` with the
   triggering drift report ID.
5. *Diagram* — include F4 here:

```latex
\begin{figure}[h]
  \centering
  \includegraphics[width=0.75\linewidth]{../figures/system_implementation/f4-drift-feedback}
  \caption{Drift-triggered retraining loop.}
  \label{fig:f4-drift-feedback}
\end{figure}
```

- [ ] **Step 2: Re-compile via wrapper. Commit.**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): write P9 feedback loop"
```

---

### Task 17: Section 4 — Cross-cutting CI/CD

**Files:**
- Modify: `Report/chapters/system_implementation.tex` (§4)

- [ ] **Step 1: Draft §4.1, §4.2, §4.3, §4.4**

- §4.1 *PR gate vs deploy gate* — one paragraph contrasting the
  three PR workflows with `cd_deploy.yml`. The PR gate enforces
  correctness; the deploy gate enforces *delivery*: rebuild image,
  rerun deploys, smoke-trigger `daily-forecast-dk1_lear` and poll
  until it completes.
- §4.2 *Tailscale-mediated deploy without exposing the host* — one
  paragraph + a reference to figure F3. Why Tailscale rather than a
  bastion host or an SSH key on the public internet.
- §4.3 *GIT\_SHA propagation as the reproducibility-monitoring link*
  — one paragraph tying P3 to P8: the same SHA that stamps an
  experiment run is the SHA visible in the Grafana operational
  dashboard log stream.
- §4.4 *Why a single-host deploy is the right MVP scope* — one
  paragraph. Single host means single failure domain, single
  blast-radius for rollback, no service mesh; deferred Kubernetes
  becomes justified only when a second deploy host is needed.

Include F3 via:

```latex
\begin{figure}[h]
  \centering
  \includegraphics[width=\linewidth]{../figures/system_implementation/f3-cicd}
  \caption{CI/CD pipeline: GitHub Actions and the deploy host across
           the Tailscale link.}
  \label{fig:f3-cicd}
\end{figure}
```

- [ ] **Step 2: Re-compile via wrapper. Commit.**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): write section 4 cross-cutting ci/cd"
```

---

### Task 18: Section 5 — Maturity Assessment and Limitations

**Files:**
- Modify: `Report/chapters/system_implementation.tex` (§5)

- [ ] **Step 1: Write §5.1 — maturity table**

`booktabs` table. Columns: Practice · Status · One-line evidence.

Rows (one per P, exactly nine):

```
P1 Version control                      Realised   Git, GitHub, configs, migrations, dashboards all in Git
P2 Continuous integration               Realised   pr_test, pr_ruff-lint, pr_smoke gates on every PR
P3 Reproducibility                      Realised   GIT_SHA + data window stamped on every experiment run
P4 Containerization                     Realised   docker-compose.yml + file-provisioned Grafana / alerts
P5 Collaboration                        Realised   CLAUDE.md, REPO_OVERVIEW.md, RUNBOOK.md, CONTRIBUTING.md + Slack
P6 Continuous training                  Realised   daily-forecast deployments refit at 06:00 UTC
P7 Experiment tracking                  Realised   algo.experiment_runs + W\&B research surface
P8 Continuous monitoring                Realised   Loki + three Grafana dashboards + file-based alert rules
P9 Feedback loop / retraining           Minimal    Drift-triggered retrain behind a config flag, two areas only
```

- [ ] **Step 2: Write §5.2 — known gaps**

One paragraph each:

- Only DK1 and DE have forecast + drift deployments; the other five
  ingestion areas (DK2, NL, BE, FR, PL) are ingestion-only.
- ClickHouse blob storage for model artifacts is practical for LEAR
  (~100 KB) but will not scale to large DNN weights.
- Optuna search persists across runs but only one search space (DNN
  architecture) is currently encoded; preprocessing and
  feature-selection HPs from Lago §4.3.3 remain manual.

- [ ] **Step 3: Write §5.3 — deferred tooling with conditions**

One bulleted list. Each bullet: tool, trigger condition.

- MLflow — when the production config count exceeds ten.
- Kubernetes — when a second deploy host is justified.
- Cloud-managed model store — when DNN weights exceed
  ClickHouse-blob practicality.
- DVC — when ENTSO-E data is no longer replayable at the required
  resolution.

- [ ] **Step 4: Re-compile via wrapper. Commit.**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): write section 5 maturity and limitations"
```

---

### Task 19: Section 6 — Conclusion + Appendices

**Files:**
- Modify: `Report/chapters/system_implementation.tex` (§6, Appendix A,
  Appendix B reference)

- [ ] **Step 1: Write §6 conclusion**

One or two paragraphs. The shape: "Of Zarour's nine practices, eight
are realised end-to-end and one (P9 feedback loop) is minimally
realised, scoped to two areas behind a config flag. The chapter has
mapped every realised practice to a concrete repository artifact —
deployment, migration, workflow, or dashboard. Deferred tooling
(MLflow, Kubernetes, cloud model store, DVC) is held back not by
oversight but by the single-host MVP scope under which the
deferred-cost / current-value trade-off does not yet justify the
adoption."

- [ ] **Step 2: Write Appendix A glossary**

`description` list. Entries: LEAR, DNN, EPF, ENTSO-E, Lasso, TPE,
MLOps, ReplacingMergeTree, Tailscale, Loki, Evidently. One sentence
per term.

- [ ] **Step 3: Re-compile via wrapper. Commit.**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): write section 6 conclusion and glossary"
```

---

### Task 20: Final self-check from spec §11

**Files:**
- No new files. Verifying.

- [ ] **Step 1: Confirm every P-section names a concrete artifact**

Open `Report/chapters/system_implementation.tex`. For each P-section
3.1 through 3.9, confirm the prose names at least one concrete
deployment, module, ClickHouse table, or workflow file. If any
section fails, change it to the literal string *"Minimal — see
§5.1"* and update §5.1 accordingly.

- [ ] **Step 2: Confirm the inventory table is exhaustive**

Run:
```bash
grep -c "entsoe-ingestion-\|daily-forecast-\|reconcile-predictions\|drift-detection-" \
  Report/chapters/system_implementation.tex
```

Expected: at least 13 (7 ingestion + 2 forecast + 1 reconcile + 2 drift = 12,
plus headers).

- [ ] **Step 3: Confirm the maturity table covers all nine practices**

Run:
```bash
grep -c "^P[1-9] " Report/chapters/system_implementation.tex
```

Expected: at least 9.

- [ ] **Step 4: Confirm every `\cite{}` key resolves**

Run:
```bash
grep -oE "\\\\cite\{[^}]+\}" Report/chapters/system_implementation.tex | \
  sort -u
```

Confirm every key listed appears as `@…{<key>,` in
`Report/references.bib`.

- [ ] **Step 5: Full standalone compile**

Recreate the wrapper:

```latex
% Report/figures/system_implementation/.final-check.tex
\documentclass{report}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{tikz}
\begin{document}
\input{../../chapters/system_implementation.tex}
\bibliographystyle{plain}
\bibliography{../../references}
\end{document}
```

Run:
```bash
cd Report/figures/system_implementation && \
  lualatex -interaction=nonstopmode .final-check.tex && \
  bibtex .final-check && \
  lualatex -interaction=nonstopmode .final-check.tex && \
  lualatex -interaction=nonstopmode .final-check.tex
```

Expected: compiles to a PDF with chapter, all sections, all figures,
all tables, and a populated bibliography. No `??` for citations, no
`?` for figure refs.

Delete the wrapper after the check.

If neither `lualatex` nor `pdflatex` is installed, the agent reports
this in the final handoff message and skips the compile check; the
self-check must still pass on steps 1–4.

- [ ] **Step 6: Commit (if any fixes were made in steps 1–4)**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): self-check fixes for system chapter"
```

---

## Out-of-band: dependencies between tasks

- Tasks 1–4 (figures) are independent of each other and can run in
  parallel.
- Tasks 1–4 must precede Task 7 (which `\includegraphics` F1 and F2),
  Task 16 (F4), and Task 17 (F3).
- Tasks 5 (scaffold) must precede every later task that modifies
  `system_implementation.tex`.
- Task 0 must precede all other tasks.
- Task 20 must be last.

## Self-Review

**Spec coverage** — re-checked the spec section by section:

- §3 (deliverables) → Task 0 creates directories + bib; Tasks 5–19
  produce the chapter; Tasks 1–4 produce the figures. Covered.
- §5 (mandatory reading) → restated at the top of this plan. Covered.
- §6 (chapter outline) → Tasks 6–19 follow the outline 1:1. Covered.
- §7.1 (P-section shape) → Tasks 8–16 each follow the four/five
  subsection shape. Covered.
- §7.2 (inventory columns) → Task 7 step 4. Covered.
- §7.3 (tech-stack columns) → Task 7 step 5. Covered.
- §7.4 (maturity labels) → Task 18 step 1. Covered.
- §8 (figures) → Tasks 1–4. Covered.
- §9 (citations) → restated in each section task; Task 20 step 4
  verifies. Covered.
- §10 (forbidden content) → no task introduces code listings, file:line,
  TODOs, or emojis. Covered.
- §11 (self-check) → Task 20. Covered.
- §12 (acceptance criteria) → all four examiner questions are
  answered by sections produced in Tasks 7, 8–16, 17, 18.

**Placeholder scan** — searched the plan for "TBD", "TODO", "implement
later", "fill in details", "similar to Task N", "add error handling".
Only literal mentions are in the No-Placeholders rule and the
scaffold's deliberate `% fill in Task N` comments (which are *removed*
as later tasks land their content). No real placeholders remain.

**Type consistency** — file paths, deployment names, ClickHouse table
names, cron strings are used identically across all tasks and match
`deploy_ingestion.py`, `deploy_forecast.py`, and CLAUDE.md.
