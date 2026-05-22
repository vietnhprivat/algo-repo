---
name: mlops-system-chapter-design
description: Spec for a thesis chapter that documents the algo-repo platform's MLOps implementation, structured around Zarour (2025) P1–P9.
status: draft
date: 2026-05-22
---

# MLOps System Chapter — Design Spec

## 1. Purpose

Produce a self-contained thesis chapter that lets an examiner with no
prior knowledge of `algo-repo` understand (a) what the platform does
end-to-end, (b) every scheduled job and the markets/areas it covers,
(c) how each subsystem maps to Zarour et al. (2025)'s nine MLOps
practices, and (d) the CI/CD pipeline that binds it together. The
chapter argues *fit to literature*: every practice referenced must
cite Zarour; every modeling-fidelity claim must cite Lago et al.
(2021).

## 2. Audience and Tone

- **Reader:** thesis examiner — technical, but no project context.
- **Voice:** past or simple-present tense (*"The platform ingests…"*,
  *"We chose Prefect because…"*). No future tense — the system is
  built. No first-person plural in section headings.
- **Length target:** 15–25 pages of typeset output.
- **"We deferred X" is always followed by an "until …" clause** so the
  examiner sees the trigger condition. Example: *"MLflow was deferred
  until the experiment-config count exceeds ten."*

## 3. Deliverables

| Artifact                                                      | Path                                                       |
| ------------------------------------------------------------- | ---------------------------------------------------------- |
| Chapter LaTeX source                                          | `Report/chapters/system_implementation.tex`                |
| Figures (TikZ `.tex` per figure)                              | `Report/figures/system_implementation/*.tex`               |
| Figure fallbacks (compiled standalone)                        | `Report/figures/system_implementation/*.pdf`               |
| BibTeX entries (appended, never replaced)                     | `Report/references.bib` (create if absent)                 |

The writing agent **must create** `Report/chapters/` and
`Report/figures/system_implementation/` if they do not yet exist; today
only `Report/ProjectPlan.pdf` lives there.

## 4. Out of Scope

- Modeling research (LEAR, DNN, asinh, DM/GW, Optuna) — referenced
  only where it supports a Zarour P-practice. The modeling chapter is
  a separate artifact.
- Implementation prose ("how to add a new area"). That belongs in
  `docs/RUNBOOK.md` and `docs/CONTRIBUTING.md`.

## 5. Mandatory Reading (in this order)

Before drafting any prose, the writing agent reads:

1. `docs/REPO_OVERVIEW.md` — architecture and data-plane diagrams are
   already prose-described here. Reuse, do not reinvent.
2. `CLAUDE.md` — the design rationale paragraphs (CI/CD, observability,
   alerting, model lifecycle) are the **primary source** for the
   "Design rationale" subsection of each P-section. Quote intent, not
   implementation.
3. `docs/superpowers/plans/2026-05-20-mlops-and-epf-fidelity.md` lines
   ~2746–2753 — Zarour P1–P9 to-task mapping. This is the
   authoritative claim of which P is satisfied by which subsystem.
4. `src/schedules/src/schedules/deploy_ingestion.py` and
   `src/schedules/src/schedules/deploy_forecast.py` — for the
   inventory table. Numbers must match `AREAS`, `FORECAST_CONFIGS`,
   `DRIFT_AREAS`, and the cron strings **as they are at write-time**.
5. `.github/workflows/{pr_test,pr_ruff-lint,pr_smoke,cd_deploy,main_cache_warm}.yml`
   — for §3.2 (P2) and §4.

## 6. Chapter Outline

The chapter follows the structure below. Section numbering is fixed —
the writing agent does not renumber.

```
1. Introduction
   1.1  Problem framing — production EPF requires more than a model
   1.2  Scope of this chapter (system, not modeling)
   1.3  Methodology — Zarour (2025) as the structuring lens

2. System at a Glance
   2.1  Architecture figure (F1)
   2.2  Data plane figure (F2)
   2.3  Operational inventory table (see §7 for required columns)
   2.4  Tech-stack table (see §7 for required columns)

3. Zarour's Nine MLOps Practices — Implementation
   3.1  P1  Version control
   3.2  P2  Continuous integration
   3.3  P3  Reproducibility
   3.4  P4  Containerization and infrastructure-as-code
   3.5  P5  Collaboration and documentation
   3.6  P6  Continuous training
   3.7  P7  Experiment tracking and model registry
   3.8  P8  Continuous monitoring
   3.9  P9  Feedback loop / drift-triggered retraining

4. Cross-cutting: CI/CD as the binding fabric
   4.1  PR gate vs deploy gate
   4.2  Tailscale-mediated deploy without exposing the host
   4.3  GIT_SHA propagation as the reproducibility–monitoring link
   4.4  Why a single-host deploy is the right MVP scope

5. Maturity Assessment and Limitations
   5.1  Practice-by-practice status — Realised / Minimal / Deferred
   5.2  Known gaps
   5.3  Deferred tooling and the conditions under which we would adopt
        each (MLflow at ≥10 configs; Kubernetes at multi-host scale;
        cloud-managed model store when DNN weights exceed ClickHouse
        blob practicality)

6. Conclusion
   A concise statement on which practices are realised end-to-end,
   which are minimally realised, and which were deliberately deferred,
   with reasoning grounded in single-host MVP scope.

Appendix A: Glossary (LEAR, DNN, EPF, ENTSO-E, Lasso, TPE, MLOps,
            ReplacingMergeTree)
Appendix B: Bibliography
```

## 7. Fixed Section Shapes

### 7.1 Each P-section in §3 follows the same shape

1. **Zarour's framing** — 2–3 sentences paraphrasing the practice as
   defined in the SLR, ending with `\cite{zarour2025}`.
2. **Our implementation** — what was built, named modules and
   deployments. No code.
3. **Technology choice** — the specific tool used (Prefect,
   ClickHouse, Loki, Evidently, W&B, …) and why this one; what was
   rejected and why.
4. **Design rationale** — the trade-off the choice resolves, scoped to
   a single-host MVP.
5. **Diagram (optional)** — a TikZ figure local to the section, only
   if it materially clarifies the practice.

### 7.2 Operational inventory table (§2.3) — required columns

| Deployment name | Area / scope | Cron (UTC) | Flow module | Purpose | Closes Zarour P*x* |

Required rows (verify against source files at write-time):

- `entsoe-ingestion-DK1` through `entsoe-ingestion-PL` — hourly
  (`0 * * * *`) — `schedules.ingestion.entsoe_backfill_flow` — covers
  the seven areas in `AREAS = ["DK1", "DK2", "NL", "BE", "DE", "FR",
  "PL"]` — closes P1, P2 (data versioning + automated ingestion).
- `daily-forecast-dk1_lear`, `daily-forecast-de_lear` — `0 6 * * *` —
  `schedules.forecast.daily_forecast_flow` — closes P6.
- `reconcile-predictions` — `0 18 * * *` —
  `schedules.reconciliation.reconcile_predictions_flow` — closes P7, P8.
- `drift-detection-dk1`, `drift-detection-de` — `0 19 * * *` —
  `schedules.drift.drift_detection_flow` — closes P8, P9.

### 7.3 Tech-stack table (§2.4) — required columns

| Tool | Role | Status (kept / added / deferred) | Why this choice |

The four-column form keeps the choice rationale on the same line as
the tool, so the examiner can read the table without flipping between
sections.

### 7.4 Maturity assessment (§5.1) labels

Three labels only — **Realised**, **Minimal**, **Deferred** — no
half-grades.

## 8. Figures Required

| ID | Section | Subject | Source to adapt |
| -- | ------- | ------- | --------------- |
| F1 | §2.1    | Host-level architecture: docker-compose with ClickHouse, Prefect server+worker, Loki, Grafana, ephemeral algo-repo:latest containers | ASCII figure in `docs/REPO_OVERVIEW.md` §2 |
| F2 | §2.2    | Data plane: ENTSO-E → mappers → ClickHouse → preprocessor → BacktestEngine / LiveRunner → experiment tracking + model_artifacts → reconciliation → drift | ASCII data-plane figure in `docs/REPO_OVERVIEW.md` §2 |
| F3 | §4      | CI/CD pipeline: two swimlanes — GitHub Actions and the deploy host — across the Tailscale link | `.github/workflows/cd_deploy.yml` flow |
| F4 | §3.9    | Drift → retrain feedback loop: drift detection → `algo.drift_reports` + Slack → `algo.retrain_events` | `schedules.drift` + `schedules.retrain` modules |

Each figure: standalone TikZ `.tex` plus a compiled `.pdf` fallback.

## 9. Citation Rules

- Every P-section opens with `\cite{zarour2025}` on the framing sentence.
- Modeling-fidelity claims (asinh, DM/GW, calibration window, ensemble
  averaging) cite `\cite{lago2021}`.
- "Technology choice" claims that name a rejected tool (Kubeflow,
  MLflow, Airflow, Dagster, DVC, Promtail, ELK, …) cite Zarour where
  the SLR discusses the trade-off; otherwise no citation — design
  choices grounded in single-host MVP scope need no external
  authority.
- No URL-only citations. If a tool has no canonical paper, name it
  inline without a `\cite{}`.

BibTeX entries for Zarour 2025 and Lago 2021 must exist in
`Report/references.bib`. If absent, the writing agent constructs them
from the DOIs already cited in the MLOps plan
(`docs/superpowers/plans/2026-05-20-mlops-and-epf-fidelity.md`).

## 10. Forbidden in the Chapter Body

- Code listings (`\verbatim`, `\lstlisting`).
- File-path: line-number references.
- TODO / TBD markers — the chapter must be self-contained on first
  draft.
- Emojis.
- "Best practice" without a Zarour citation — the entire chapter's
  claim is *which* practices, *as defined by Zarour*.

## 11. Self-Check the Writing Agent Runs Before Claiming Done

The writing agent verifies, by reading the file it just wrote:

1. Every P*n* section in §3 names at least one concrete deployment,
   module, ClickHouse table, or workflow file from the repo.
2. The inventory table in §2.3 lists every deployment created by
   `deploy_ingestion.py` and `deploy_forecast.py` — counted, not
   sampled.
3. The §5.1 maturity table covers all nine practices, each with
   exactly one of {Realised, Minimal, Deferred}.
4. Every `\cite{}` key resolves to an entry in `Report/references.bib`.
5. The LaTeX compiles via `lualatex` or `pdflatex` to a PDF without
   errors. If neither toolchain is installed in the agent's
   environment, the agent reports this explicitly in its handoff
   message instead of claiming compilation success.

If any P-section cannot be tied to a concrete artifact in the repo,
the section must explicitly say *"Minimal — see §5.1"* and §5.1 must
explain why.

## 12. Acceptance Criteria

The chapter is accepted when:

- It compiles to a PDF.
- Every check in §11 passes.
- An examiner reading only this chapter can answer:
  - "What are the scheduled jobs and which areas does each cover?"
  - "Which technology choices were made, and why those?"
  - "Which of Zarour's nine practices are realised, minimally
    realised, or deferred — and on what grounds?"
  - "How does CI/CD bind everything together?"
