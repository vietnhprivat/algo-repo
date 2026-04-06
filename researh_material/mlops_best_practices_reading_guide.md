# Reading Guide: MLOps Best Practices, Challenges and Maturity Models

**Paper:** Zarour, Alzabut & Al-Sarayreh (2025), Information and Software Technology 183
**Scope:** Systematic literature review of 45 articles on MLOps practices, challenges, maturity models, and lessons learned

---

## How to Read This Paper (Recommended Order)

| Priority | Section | Why it matters for you |
|----------|---------|----------------------|
| 1 | Section 4.2 — RQ2: Best Practices (Table 6) | The 9 practices are a checklist for what you have and what you're missing |
| 2 | Section 4.1 — RQ1: Challenges (Table 5) | Know which pitfalls apply to your project right now |
| 3 | Section 4.3 — RQ3: Maturity Models (Table 7) | Self-assess where your project sits on the maturity scale |
| 4 | Section 4.4 — RQ4: Lessons Learned (Table 8) | Practical do's and don'ts from real implementations |
| 5 | Sections 1-2 — Introduction & Context | Skim for terminology; skip if you already know CI/CD/CT/CM concepts |
| 6 | Section 3 — Research Methodology | Skip unless you're writing your own literature review |

---

## The 9 MLOps Best Practices vs Your Codebase

### Scorecard

| # | Practice | Status | Your Implementation | Gap |
|---|---------|--------|-------------------|-----|
| P1 | **Automating CI/CD** | Partial | Prefect flows automate data ingestion (`ingestion.py`). No CI/CD pipeline for model code (no GitHub Actions, no automated testing on push) | Need: CI pipeline for tests, CD for model deployment |
| P2 | **Orchestrating Workflows** | Partial | Prefect orchestrates data ingestion flows with task-level retries. `BacktestEngine` orchestrates model training/evaluation. No end-to-end pipeline connecting data ingestion → training → evaluation → deployment | Need: Connect ingestion to training pipeline |
| P3 | **Ensuring Reproducibility** | Good | `ExperimentConfig` dataclass captures all experiment parameters. Date-based splitting (`split_by_dates`) ensures reproducible train/test sets. `--track` flag stores results in ClickHouse | Need: Docker containerization, pinned dependency versions |
| P4 | **Versioning** | Partial | Git for code versioning. Config files in `configs/` are git-tracked. No data versioning (ClickHouse data isn't versioned), no model artifact versioning | Need: Data versioning (DVC), model registry |
| P5 | **Collaboration** | Minimal | Single-developer setup. CLI tools (`data_cli`, `forecast_cli`) make workflows accessible. No shared dashboards or collaboration tooling | Need: Shared experiment dashboards, documentation |
| P6 | **Continuous Training & Evaluation** | Partial | `BacktestEngine` supports daily/weekly refit via `refit_interval_days`. Prefect schedules for data ingestion. No automated retraining triggered by new data or drift detection | Need: Scheduled retraining flow, drift detection |
| P7 | **Track & Log ML Metadata** | Good | `algo.experiment_runs` table stores run metadata (config, metrics). `algo.experiment_predictions` stores per-period predictions. `insert_experiment_run()` / `insert_experiment_predictions()` in `ingest.py` | Need: Hyperparameter tracking, training duration, feature importance |
| P8 | **Continuous Monitoring** | Not Started | No model performance monitoring in production. No drift detection. No alerting on prediction quality degradation | Need: Monitoring dashboard, data drift checks, prediction quality alerts |
| P9 | **Feedback Loops** | Not Started | No automated feedback from monitoring to retraining. No mechanism to trigger retraining when model quality drops | Need: Monitor → retrain trigger pipeline |

### Summary: 2 Good, 4 Partial, 1 Minimal, 2 Not Started

---

## The 8 MLOps Challenges — Which Apply to You

| # | Challenge | Relevance | Your Situation |
|---|----------|-----------|---------------|
| C1 | Lack of Necessary Skills and Culture | **Low** | Solo/small team project — no cross-team friction |
| C2 | Lack of Expertise and Resources | **Medium** | Implementing Transformer model requires deep learning expertise beyond current LEAR/Lasso scope. GPU resources needed for training |
| C3 | Difficulties in Data Handling | **Medium** | ClickHouse handles storage well, but no data quality checks, no automated validation of incoming ENTSOE data, `LOOKBACK_HOURS=48` means you rely on recent data being correct |
| C4 | Difficulties in Automation and Workflows | **High** | Manual steps between data ingestion and model training. No automated pipeline from "new data arrives" → "model retrained" → "predictions updated" |
| C5 | Difficulties in Integration and Scaling | **Medium** | Adding new areas (e.g., DE, FR) requires manual config + deployment. No infrastructure for scaling to multiple models/areas simultaneously |
| C6 | Unexpected Performance and Monitoring | **High** | No monitoring of prediction quality in production. If ENTSOE data quality degrades or market dynamics shift, you won't know until you manually check |
| C7 | Poor Collaboration | **Low** | N/A for current team size |
| C8 | Managerial Challenges | **Low** | N/A for current team size |

### Top priorities: C4 (Automation) and C6 (Monitoring)

---

## Maturity Model Assessment: Where Are You?

The paper presents 5 maturity models. Using the **Google model** (most relevant for your scale):

| Level | Description | Your Status |
|-------|------------|-------------|
| **Level 0: Manual Process** | Script-driven, no automation, no monitoring | **Partially past this** — you have CLI tools and Prefect schedules |
| **Level 1: ML Pipeline Automation** | Orchestrated experiments, continuous training, automated retraining | **You are here** — Prefect automates data ingestion, `BacktestEngine` automates training/evaluation, but no automated retraining trigger |
| **Level 2: CI/CD Pipeline Automation** | Automated testing, building, deployment of ML pipelines | **Not yet** — no CI/CD for model code, no automated deployment |

Using the **Microsoft model** (more granular):

| Level | Description | Your Status |
|-------|------------|-------------|
| Level 0: No MLOps | Manual everything | Past this |
| **Level 1: DevOps but no MLOps** | Source control, CI/CD for app code, but ML is manual | **You are between 1 and 2** — you have source control and Prefect, but ML pipeline isn't in CI/CD |
| Level 2: Automated Training | Training pipeline is automated, experiment tracking exists | Partially — `--track` flag stores results, but training isn't triggered automatically |
| Level 3: Automated Deployment | Model deployment is automated | Not yet |
| Level 4: Full MLOps Automated Operations | Everything automated with monitoring and feedback loops | Not yet |

### Your maturity: **Level 1 (Google) / Level 1-2 (Microsoft)**

---

## Mapping Paper Concepts to Your Codebase

| MLOps Concept | Paper Section | Your Implementation | File Path |
|--------------|---------------|-------------------|-----------|
| **Data Ingestion Pipeline** | P2 (Orchestration) | Prefect flow with 4 tasks (prices, load, generation, wind/solar) | `src/schedules/src/schedules/ingestion.py` |
| **Data Storage** | P3 (Reproducibility) | ClickHouse with ReplacingMergeTree (deduplication), numbered migrations | `src/infrastructure_clickhouse/` |
| **Feature Engineering** | P2 (Orchestration) | `FeatureTransformer` pipeline, composable transformers | `src/price_forecasting/.../data/transformers.py` |
| **Model Training** | P6 (Continuous Training) | `BacktestEngine` with calibration windows and refit intervals | `src/price_forecasting/.../backtesting/engine.py` |
| **Model Registry** | P4 (Versioning) | `MODEL_REGISTRY` dict + `get_model()` factory (in-code only, no artifact storage) | `src/price_forecasting/.../models/__init__.py` |
| **Experiment Tracking** | P7 (Track Metadata) | ClickHouse tables `algo.experiment_runs` + `algo.experiment_predictions` | `src/infrastructure_clickhouse/.../ingest.py` |
| **Model Evaluation** | P6 (Continuous Eval) | MAE, RMSE, sMAPE, rMAE metrics + per-hour breakdown | `src/price_forecasting/.../evaluation/` |
| **Deployment** | P1 (CI/CD) | Prefect deployment scripts for ingestion schedules | `src/schedules/src/schedules/deploy_ingestion.py` |
| **Workflow Orchestration** | P2 (Orchestration) | Prefect for ingestion, Typer CLI for backtests | `src/schedules/`, `src/forecast_cli/` |
| **Configuration Management** | P3 (Reproducibility) | Python config files in `configs/`, `ExperimentConfig` dataclass | `src/price_forecasting/.../configs/experiment.py` |
| **Data Quality** | C3 (Data Handling) | Schema enforcement via `enforce_schema()` on domain models | `src/domain/curves.py` |
| **Continuous Monitoring** | P8 (Monitoring) | Not implemented | — |
| **Feedback Loops** | P9 (Feedback Loops) | Not implemented | — |
| **Data Versioning** | P4 (Versioning) | Not implemented (ClickHouse has idempotent upserts but no version history) | — |
| **CI/CD for ML** | P1 (CI/CD) | Not implemented (no GitHub Actions or similar) | — |

---

## Practical Roadmap: Moving Up the Maturity Ladder

### Phase 1: Solidify Level 1 (Low effort, high impact)

These build on what you already have:

1. **Add a scheduled forecast flow** — You have `ingestion.py` for data, but `forecast.py` is empty. Create a Prefect flow that runs backtests or live predictions on a schedule after ingestion completes.
   - Files to modify: `src/schedules/src/schedules/forecast.py`, `deploy_ingestion.py`
   - Pattern: mirror `entsoe_backfill_flow` structure

2. **Add data quality checks to ingestion** — After each ingestion task, verify row counts, check for NaN/null prices, validate date ranges.
   - Add validation tasks in `ingestion.py`
   - Log warnings to Prefect

3. **Pin dependencies** — Create a `requirements.lock` or use `uv lock` to ensure reproducible environments.

### Phase 2: Reach Level 2 (Medium effort)

4. **Add CI pipeline (GitHub Actions)** — Run `python -m pytest tests/ -v` on every push. This is the single highest-impact MLOps practice (P1).
   - Create `.github/workflows/test.yml`

5. **Add basic monitoring** — After live predictions, compare next-day actuals to predictions and log the error to `algo.experiment_predictions`. Alert if MAE exceeds a threshold.
   - Add a "reconciliation" task to the forecast flow

6. **Add model artifact storage** — Save fitted model weights/parameters to a versioned location (could be ClickHouse blob, S3, or local directory with git-LFS).

### Phase 3: Reach Level 3 (Higher effort)

7. **Automated retraining pipeline** — When monitoring detects degraded performance (drift), automatically trigger a retraining run.
   - Feedback loop: Monitor → detect drift → retrain → evaluate → deploy

8. **Docker containerization** — Package the entire pipeline in Docker for reproducibility across environments.

9. **Data versioning** — Use DVC or ClickHouse snapshots to version training datasets.

---

## Key Lessons Learned (from Table 8) Applied to Your Project

### Do's (from successful implementations)

| Lesson | How it applies |
|--------|---------------|
| "Automation of ML pipelines" | Your Prefect + BacktestEngine foundation is right — extend it to cover the full lifecycle |
| "CI/CD solutions are critical for testing and releasing" | Add GitHub Actions for tests first, then for model deployment |
| "Model monitoring and tracking" | Your `algo.experiment_runs` table is a good start — add live monitoring |
| "Open-source tools are more modular and often offer higher quality" | You're already using Prefect, ClickHouse, scikit-learn — good choices |
| "Clear processes and guidelines" | Your `CLAUDE.md` is excellent documentation — keep it updated as you add MLOps practices |
| "Applying architectural principles" | Clean separation of domain/infrastructure/CLI is solid architecture |

### Don'ts (from unsuccessful implementations)

| Anti-pattern | Risk for you |
|-------------|-------------|
| "Unrealistic expectations about data science" | Don't expect the Transformer to beat LEAR without significant tuning effort |
| "Lack of proper testing and deployment processes" | You have tests but no CI — one broken push could go unnoticed |
| "Struggle with data manipulation for retraining" | Your `LOOKBACK_HOURS=48` is small — ensure enough historical data is always available for retraining windows of 56-1456 days |
| "Neglecting overfitting" | Your backtest uses time-series splits (good), but no cross-validation for hyperparameter tuning beyond LEAR's `LassoCV` |
| "No single tool can realize a fully automated MLOps workflow" | Don't try to replace Prefect + ClickHouse + CLI with one monolithic tool |

---

## Section-by-Section Reading Notes

### Sections 1-2 — Introduction & Context (skim)
Defines MLOps as ML + DevOps. Key additions over DevOps: **Continuous Training (CT)** and **Continuous Monitoring (CM)**. You already have CT partially (BacktestEngine refit) but no CM.

### Section 3 — Research Methodology (skip)
Standard SLR methodology. Only relevant if you need to cite this paper or understand how the 45 articles were selected.

### Section 4.1 — RQ1: Challenges (read Table 5)
Eight challenges categorized. **C3 (Data Handling)**, **C4 (Automation)**, and **C6 (Monitoring)** are most cited — they're also your biggest gaps. C4 is cited in 15 out of 45 papers, making it the most common challenge.

### Section 4.2 — RQ2: Best Practices (read Table 6 carefully)
Nine practices. **P1 (CI/CD)** is cited in 28 of 45 papers — it's the single most recommended practice. **P6 (Continuous Training)** is second at 16 citations. Your project is strongest on P3 (Reproducibility) and P7 (Metadata Tracking).

### Section 4.3 — RQ3: Maturity Models (read Table 7)
Five maturity models compared. Google's 3-level model is simplest and most actionable. Microsoft's 5-level model is most granular. Use the Google model for quick self-assessment, Microsoft for detailed roadmapping.

### Section 4.4 — RQ4: Lessons Learned (read Table 8)
Rich table of do's and don'ts from 20+ implementations. Key pattern: **automation and monitoring are the two most common success factors**, while **lack of testing/deployment processes and poor data handling are the top failure causes**.

---

## Glossary: Paper Terms vs Your Code

| Paper Term | Your Codebase Equivalent |
|-----------|------------------------|
| CI/CD Pipeline | Partially: Prefect flows (`ingestion.py`), no GitHub Actions |
| Continuous Training (CT) | `BacktestEngine` with `refit_interval_days` |
| Continuous Monitoring (CM) | Not implemented |
| Workflow Orchestration | Prefect (`ingestion.py`, `deploy_ingestion.py`) |
| Model Registry | `MODEL_REGISTRY` dict in `models/__init__.py` |
| Experiment Tracking | `algo.experiment_runs` + `algo.experiment_predictions` tables |
| Data Versioning | Not implemented (ClickHouse upserts, no version history) |
| Feature Store | `FeatureTransformer` pipeline + ClickHouse tables (`algo.timeseries`, `algo.forecasts`) |
| Model Artifact | Not stored — models are retrained from scratch each run |
| Feedback Loop | Not implemented |
| Data Drift | Not monitored |
| Maturity Level 0 | Manual script-driven ML — you're past this |
| Maturity Level 1 | Automated ML pipeline — you're here |
| Maturity Level 2 | CI/CD pipeline automation — your next target |
