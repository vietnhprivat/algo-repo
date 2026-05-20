# Research Brief — Literature Backing for algo-repo Design Choices

> **Audience.** A future LLM session (or human assistant) acting as a
> research librarian. **Read this file in full before doing anything.** It
> contains everything you need to (a) understand the project, (b) understand
> what literature has already been digested, (c) hunt down literature for
> the weakly-supported areas, and (d) write up findings in the format the
> project expects.
>
> **You are not asked to modify code.** This is a **research-only**
> engagement. Your deliverables are annotated bibliographies, reading
> guides, and gap analyses — all under `researh_material/` (note the
> repo's existing typo; keep it). The human reviews your findings and
> decides what to apply.
>
> **The bar.** Every design choice in this project should ultimately be
> backed by peer-reviewed literature or a clearly documented engineering
> rationale. Today, several choices are *load-bearing* but only
> tradition-backed (e.g., "the paper used these calibration windows").
> Your job is to either find the science that justifies them or surface
> the fact that no science exists — both are valuable outcomes.

---

## 0. How to use this file

1. **Read sections 1–3** to understand the project and the user's goals.
2. **Read section 4** to learn what literature is already in the repo —
   do not duplicate it.
3. **Read section 5** — the gap inventory. Each gap has a priority, a
   precise research question, an acceptance criterion, and a deliverable
   location. Pick the highest-priority open gap and work on it.
4. **Follow section 6** for output format and citation style.
5. **Honor section 7** — quality bar. No hallucinated DOIs, no padding,
   no opinion-as-fact.

> **One gap at a time.** Do not try to tackle the whole inventory in one
> pass. Pick the top-priority **open** gap, produce a complete deliverable
> (annotated bibliography + reading guide + a one-page synthesis), then
> stop and let the human review.

---

## 1. What this project is

`algo-repo` is an **electricity price forecasting (EPF) platform for
European day-ahead markets**. Concretely it:

1. **Ingests** ENTSO-E Transparency Platform data (energy prices, total
   load forecasts, generation forecasts, wind/solar forecasts) for ~7
   bidding zones (DK1, DK2, NL, BE, DE, FR, PL) into a ClickHouse
   `algo` database.
2. **Trains** forecasting models against a rolling multi-window
   ensemble. The baseline is **LEAR** (Lasso Estimated AutoRegressive
   — Lago et al., 2021). A model registry also exposes DNN
   (PyTorch/Lightning), Random Forest, XGBoost, LightGBM and CatBoost,
   but **LEAR is the only one in production today**.
3. **Predicts** tomorrow's 24-hour price vector daily at 06:00 UTC,
   stores the prediction + the serialized ensemble (base64 joblib in
   ClickHouse), then **reconciles** against published actuals the next
   evening to compute MAE/RMSE/sMAPE.
4. **Detects drift** daily using Evidently's `DataDriftPreset` on a
   rolling 7-day current vs. 90-day reference price distribution.

Full architectural detail lives in [`docs/REPO_OVERVIEW.md`](REPO_OVERVIEW.md).
Hard project rules and conventions live in [`../CLAUDE.md`](../CLAUDE.md).
Deployment specifics in [`../DEPLOYMENT.md`](../DEPLOYMENT.md). Read at
least `REPO_OVERVIEW.md` before doing serious work.

### Status snapshot (as of 2026-05-20)

- **Production area:** DK1 only.
- **Production model:** LEAR with `calibration_windows=[56, 84, 730, 1092]`,
  daily refit, exogenous = `["TotalLoad"]`, `alpha=0.01`.
- **DNN / GBT bases exist but are not deployed** — they recently landed
  (commit `b741ab2`) and need empirical validation.
- **Drift detection is in production** but its hyperparameters
  (reference window length, current window length, sample-size threshold,
  test choice) are engineering defaults — *not* literature-backed for EPF.

---

## 2. The user's goals (in order of priority)

1. **Defensibility.** Every non-trivial design choice in the codebase
   should be backed by a citation to peer-reviewed work, a benchmark
   result, or — if neither exists — an explicit engineering rationale
   acknowledging the missing science. The user is preparing this work
   for thesis / publication and cannot ship hand-wavy "we picked these
   numbers because the paper did" justifications.
2. **Identify what to research next.** Surface high-value gaps where
   literature could materially change a design decision (e.g., which
   loss function for DNN; what reference window for drift; whether
   to add Variance Stabilizing Transformation).
3. **Avoid reinventing the wheel.** Where literature already settles a
   question, point to it concisely so the user doesn't redo the work.
4. **Keep the bar high.** It is better to report "I searched X databases
   with Y queries and found no usable result" than to cite a marginal
   paper.

---

## 3. Glossary (for the research librarian, not the user)

| Term | Meaning in this project |
|---|---|
| **EPF** | Electricity Price Forecasting |
| **LEAR** | Lasso Estimated AutoRegressive — paper's name for parameter-rich ARX models estimated by LASSO; one independent Lasso per period (24 or 96) |
| **DNN** | Deep neural net — here a feedforward MLP with one shared output head of size `n_periods` (MIMO) |
| **MIMO / Direct / Recursive** | Multi-step forecasting strategies (Ben Taieb et al., 2012) — see §4 reading guide |
| **rMAE** | Relative MAE: `MAE(y, ŷ) / MAE(y, y_naive)`, naive = `y.shift(7)` (same weekday last week) |
| **DM test / GW test** | Diebold-Mariano / Giacomini-White tests for forecast accuracy equivalence |
| **VST** | Variance Stabilizing Transformation (e.g. asinh, area hyperbolic sine — Uniejewski et al. 2018) |
| **Calibration window** | Length-in-days of the training slice ending the day before the forecast target |
| **Refit interval** | How often the model is retrained vs. reused with stale weights |
| **Drift (data / concept)** | Change in input distribution vs. change in `P(y|x)` |
| **ReplacingMergeTree** | ClickHouse engine that deduplicates lazily by sort key; reads need `FINAL` or post-dedup |
| **SDAC** | Single Day-Ahead Coupling — the European pan-zonal day-ahead market mechanism |

---

## 4. Prior art already in the repo — DO NOT RE-RESEARCH

Everything below is already digested in `researh_material/` and
`researh_material/reading_guides/`. Read the reading guides before
starting; they contain page-level references and direct mappings to
codebase locations.

### 4.1 PDFs already in the repo

Located in `researh_material/`:

| File | Citation | What's covered |
|---|---|---|
| `Weron (2014).pdf` | Weron, R. (2014). *Electricity price forecasting: A review of the state-of-the-art with a look into the future*. International Journal of Forecasting, 30(4), 1030–1081. | 52-page foundational EPF review; metrics, ARX, ensembling, fundamentals |
| `Forecasting day-ahead electricity prices ... benchmark.pdf` | Lago, J., Marcjasz, G., De Schutter, B., & Weron, R. (2021). *Forecasting day-ahead electricity prices: A review of state-of-the-art algorithms, best practices and an open-access benchmark*. Applied Energy, 293. | THE foundational paper for this project. LEAR spec, ensemble, 13-point rigour checklist, rMAE definition, recalibration guidance |
| `A Transformer approach for Electricity Price Forecasting.pdf` | Llorente, J. & Portela, J. (2025). *A Transformer Approach for Electricity Price Forecasting*. arXiv:2403.16108v3. | Transformer encoder architecture, dual-input embedding, retrain-vs-renormalize tradeoff |
| `Recent advances in electricity price forecasting A review of probabilistic.pdf` | Nowotarski, J. & Weron, R. (2018). *Recent advances in electricity price forecasting: A review of probabilistic forecasting*. Renewable and Sustainable Energy Reviews, 81. | Probabilistic EPF — CRPS, pinball loss, quantile regression. Not yet used in the codebase but cited for future direction |
| `MLOps best practices, challenges and maturity models A systematic literature review.pdf` | Zarour, M., Alzabut, J. & Al-Sarayreh, K. (2025). *MLOps best practices, challenges and maturity models: A systematic literature review*. Information and Software Technology, 183. | The P1–P9 best-practice checklist that drove the schedules/observability work |
| `Navigating MLOps Insights into Maturity, Lifecycle, Tools, and Careers.pdf` | Companion paper to the SLR. | MLOps maturity models, lifecycle stages |
| `Toward_an_Open_Source_MLOps_Architecture.pdf` | Background MLOps architecture paper. | Open-source MLOps reference architectures |
| `Probabilistic Intraday DA Forecasting using GenAI.pdf` | Background — GenAI for intraday. | Not central; mentioned for future probabilistic direction |
| `Reinforcement Learning for Bidding Strategy Optimization in Day-Ahead Energy Market.pdf` | Background — RL for bidding. | Adjacent problem, not directly applied |
| `23727999.pdf` | Background — short paper. | Mentioned for completeness, not central |

### 4.2 Reading guides

Located in `researh_material/reading_guides/` — these are **the canonical
synthesis of each paper for this codebase**. Read these before the PDFs.

| File | What it covers |
|---|---|
| `weron_2014_reading_guide.md` | Section-by-section map of the 2014 review with citations to codebase modules. Establishes the 5 model families and points the project to family 4 (statistical, LEAR) and family 5 (CI, DNN/Transformer). |
| `lago_epf_benchmark_reading_guide.md` | The 13-point checklist self-audit. **Current score: 8 PASS, 2 PARTIAL, 3 FAIL.** FAILs are: (3) computational cost untracked, (5) only DK1, (7) no DM/GW statistical tests. PARTIALs: state-of-the-art comparison incomplete; no explicit validation split. |
| `transformer_epf_reading_guide.md` | Architecture summary + the retraining-vs-renormalization design decision the project has not yet resolved for the DNN/Transformer path. |
| `mlops_best_practices_reading_guide.md` | The 9-practice scorecard (P1–P9). |
| `mlops_implementation_plan.md` | The 4-phase execution plan driven by the MLOps SLR. Phases 0–4 done as of 2026-04-21 (forecast flow, reconciliation, drift detection, structured logging). |
| `forecasting_strategy_and_bottlenecks.md` | Internal analysis comparing Direct (LEAR) vs MIMO (DNN) vs Recursive strategies, citing Ben Taieb et al. (2012). Confirms LEAR's Direct strategy is defensible because cross-hour information enters via lag features. |

### 4.3 What the repo can *already* point to with confidence

If asked "what backs this design choice?", the repo already has a citation
for the following — **do not re-research**:

- **LEAR architecture and feature set** (Lasso per hour, lags `[1, 2, 3, 7]`,
  exogenous `[d0, d-1, d-7]` lags, calendar dummies) — Lago et al. 2021 §4.1–4.2.
- **Calibration window ensemble (mean across windows)** — Lago et al. 2021 §4.4.
- **rMAE with weekly-naive baseline** — Lago et al. 2021 §5.4–5.5.
- **Daily recalibration as the default** — Lago et al. 2021 §5.6.
- **Direct vs MIMO multi-step strategy choice** — Ben Taieb et al. 2012,
  *Expert Systems with Applications* (already cited in
  `forecasting_strategy_and_bottlenecks.md`).
- **MLOps best-practice scaffolding (P1–P9)** — Zarour et al. 2025.
- **The 13-point rigour checklist for EPF research** — Lago et al. 2021 §7.

---

## 5. The literature gap inventory

This is **the meat of this brief**. Each entry is a weakly-supported
design choice in the current codebase. Priority is the user's call —
P0 = blocking thesis/publication defensibility; P1 = important for next
quarter; P2 = nice-to-have.

For each gap you work, deliver in the order described in section 6.
Update the `Status` line of the relevant entry below when you finish
(e.g. `Status: COMPLETE → researh_material/reading_guides/...`).

---

### Gap 1 — Statistical significance testing for forecast comparison
- **Priority:** **P0**.
- **Status:** COMPLETE → researh_material/reading_guides/statistical_tests_for_epf_reading_guide.md
- **What the code does today.** Reports point estimates of MAE / RMSE /
  sMAPE / rMAE only. No paired-forecast test, no Model Confidence Set.
- **Why it's a problem.** Lago et al. 2021 §5.5 and §7 explicitly require
  Diebold-Mariano (multivariate) or Giacomini-White for any EPF result
  to be defensible. This is one of the **3 FAILs** on the Lago checklist
  (`lago_epf_benchmark_reading_guide.md`).
- **Research questions.**
  1. **DM vs GW for daily EPF**: which is canonical for 24-period vector
     forecasts evaluated over a multi-month test horizon? What loss
     differential should be used (absolute, squared, multivariate norm)?
  2. **Multivariate DM** (Diebold-Mariano on a vector of hourly errors)
     vs. **pointwise DM per hour**: when is each appropriate?
  3. **Model Confidence Set** (Hansen, Lunde & Nason 2011) — is it the
     correct extension when comparing >2 models?
  4. Are there EPF-specific corrections (e.g. for serial correlation in
     daily forecast errors with overlapping calibration windows)?
- **Acceptance criterion.** A reading guide that (a) recommends a single
  primary test for this codebase with citation, (b) gives the exact
  null/alternative formulation, (c) cites the canonical implementation
  (R `forecast::dm.test`, Python `arch.bootstrap.IIDBootstrap`, or
  `epftoolbox`'s implementation), (d) explains the data-snooping
  correction needed when comparing >2 models.
- **Deliverable.** `researh_material/reading_guides/statistical_tests_for_epf_reading_guide.md`.

---

### Gap 2 — Variance Stabilizing Transformation (VST) for EPF
- **Priority:** **P0**.
- **Status:** OPEN.
- **What the code does today.** Feeds raw EUR/MWh prices through
  `StandardScaler` (`DataPreprocessor.transform_data`). Negative and
  spike prices flow through unchanged.
- **Why it's a problem.** Day-ahead prices are heavily skewed, have
  negative tails, and exhibit spikes. Log/Box-Cox don't accommodate
  negatives; asinh (Uniejewski, Weron & Ziel 2018) is the EPF-standard
  VST and is reported to improve LEAR by 5–10 % on Nord Pool. The
  project is leaving accuracy on the table without a deliberate
  decision.
- **Research questions.**
  1. What is the canonical VST for EPF (asinh? mid-mean scaling? z-score
     of asinh? Uniejewski-Weron-Ziel 2018)?
  2. Does VST belong inside `DataPreprocessor` (model-agnostic), inside
     `LearModel.fit` (per-model), or both?
  3. Does it interact with `StandardScaler` — does the project need to
     drop the scaler when VST is on?
  4. What's the empirical effect on rMAE for Nord Pool / EPEX / DK1 in
     reported results?
  5. Does it apply equally to GBT / DNN / Transformer models, or is it
     LEAR-specific because of Lasso's linearity assumption?
- **Acceptance criterion.** A reading guide naming the recommended VST
  with formula, citing primary source(s), summarizing reported gains,
  and stating where in the pipeline it belongs.
- **Deliverable.** `researh_material/reading_guides/variance_stabilizing_transformation_reading_guide.md`.

---

### Gap 3 — Drift detection windows and test choice for EPF prices
- **Priority:** **P0**.
- **Status:** OPEN.
- **What the code does today.** `schedules/drift.py` runs Evidently's
  `DataDriftPreset` daily with `REFERENCE_DAYS=90`, `CURRENT_DAYS=7`,
  `MIN_SAMPLE_SIZE=30`. Evidently auto-selects the test (KS for small
  samples, Wasserstein for larger). The verdict comes from
  `DriftedColumnsCount > 0`.
- **Why it's a problem.** The window sizes are engineering defaults.
  There is no citation. EPF price distributions are non-stationary in
  ways that may bias KS toward false positives (regime changes within
  90 days). Conversely, 7 days is one weekly cycle — possibly too short
  to detect a regime shift.
- **Research questions.**
  1. Is KS the right test for univariate price drift in EPF? How does
     it compare to Wasserstein distance, PSI (Population Stability
     Index), or Jensen-Shannon for non-Gaussian price series?
  2. What window sizes do EPF drift-detection papers actually use?
     Cite at least three.
  3. Should the reference window be **rolling** (always last 90 days),
     **fixed** (training-set distribution), or **adaptive**? Which is
     the field consensus?
  4. Is there published guidance on the **lead time** between drift
     detection and forecast quality degradation (i.e., how many days
     of drift do you tolerate before retraining)?
  5. Are concept-drift methods (e.g. ADWIN, Page-Hinkley) more
     appropriate than data-drift methods for EPF given that the
     conditional distribution `P(price | load, wind)` is what actually
     matters?
- **Acceptance criterion.** A reading guide that recommends concrete
  values for `REFERENCE_DAYS`, `CURRENT_DAYS`, and a primary test, each
  citation-backed. State explicitly when the recommendation is
  "default; no strong literature; document the engineering choice".
- **Deliverable.** `researh_material/reading_guides/drift_detection_for_epf_reading_guide.md`.

---

### Gap 4 — Calibration window sizes
- **Priority:** **P1**.
- **Status:** OPEN.
- **What the code does today.** Production config uses
  `calibration_windows=[56, 84, 730, 1092]`. The Lago default is
  `[56, 84, 1092, 1456]`. The project replaces 1456 with 730 without
  a documented reason.
- **Why it's a problem.** Window choice is a primary determinant of
  bias-variance trade-off. Lago et al. 2021 §4.4 give defaults but do
  not derive them. The user needs to know whether their swap is sound
  or a regression.
- **Research questions.**
  1. What is the empirical basis for `[56, 84, 1092, 1456]` in Lago
     2021 — is it just "the original LEAR paper" (Uniejewski et al.
     2018) or was an ablation performed?
  2. Is there published work on **optimal calibration window selection**
     for EPF (Marcjasz, Uniejewski, & Weron papers between 2018–2023)?
  3. Does the optimal window vary by **market maturity** (Nord Pool
     vs. EPEX vs. PJM)? Most relevantly: is DK1 close enough to Nord
     Pool that 1456 should be preserved?
  4. Does using **fewer than 4 windows** lose statistically significant
     accuracy (DM-tested)?
- **Acceptance criterion.** A short guide (2–4 pages) citing the
  original LEAR paper's ablation (if any) plus follow-ups, with a
  recommendation for DK1 specifically.
- **Deliverable.** `researh_material/reading_guides/calibration_window_selection_reading_guide.md`.

---

### Gap 5 — Loss function for DNN / deep models on EPF
- **Priority:** **P1**.
- **Status:** OPEN.
- **What the code does today.** `LightningModel.training_step` uses
  `F.l1_loss` (MAE) unconditionally for all deep models.
  `validation_step` ditto.
- **Why it's a problem.** Several EPF papers argue for Huber, MAE+spike
  penalty, or asymmetric losses (because under-prediction of price
  spikes costs more than over-prediction). Some recent work (2022–
  2024) explores quantile / pinball losses to enable probabilistic
  output. The current choice is the Lago paper default but not
  examined.
- **Research questions.**
  1. Which loss does the Lago 2021 DNN actually use, and why?
  2. Has any post-2022 EPF paper benchmarked MAE vs Huber vs
     asymmetric losses for day-ahead price MLPs?
  3. For Transformer/sequence models on EPF, is there a different
     consensus?
  4. If the goal is probabilistic forecasting (future direction —
     see Nowotarski & Weron 2018), what loss enables that (CRPS,
     pinball, multi-quantile)?
- **Acceptance criterion.** A reading guide with a 1-paragraph
  recommendation per model family (MLP / Transformer / GBT) plus
  citations.
- **Deliverable.** `researh_material/reading_guides/loss_functions_for_epf_reading_guide.md`.

---

### Gap 6 — Exogenous feature selection methodology
- **Priority:** **P1**.
- **Status:** OPEN.
- **What the code does today.** `ExperimentConfig.exogenous_curve_types`
  is a manual list. Current production uses only `["TotalLoad"]`.
  `ExogenousLagTransformer` adds `(d0, d-1, d-7)` lags per curve.
- **Why it's a problem.** The choice of **which** exogenous curves to
  include (load, generation, wind onshore, wind offshore, solar,
  cross-border flows, gas / coal prices, weather) is fundamental and
  uncited. Lago 2021 uses load + (renewable) generation but does not
  derive it. There is broader EPF literature on fuel-price coupling
  (Weron 2014 §4.1) and renewable-induced merit-order shifts.
- **Research questions.**
  1. For each major European bidding zone (Nord Pool / EPEX-DE / DK1
     specifically), what exogenous variables have the strongest
     reported marginal effect on day-ahead MAE / rMAE?
  2. Is there literature on the value of including **upstream gas /
     coal / CO2** prices? Of cross-border interconnector flow
     forecasts?
  3. Do papers distinguish features that help LEAR (linear) from
     those that help DNN/Transformer (non-linear)?
  4. How are **wind onshore vs offshore vs solar** typically encoded
     — sum to "renewable forecast" or kept separate?
- **Acceptance criterion.** A short guide listing exogenous variables
  with reported marginal contribution and primary citations.
- **Deliverable.** `researh_material/reading_guides/exogenous_features_for_epf_reading_guide.md`.

---

### Gap 7 — Cross-market generalization (only DK1 today)
- **Priority:** **P1**.
- **Status:** OPEN — flagged as FAIL on Lago checklist item 5.
- **What the code does today.** Production runs DK1 only. Infrastructure
  supports DK2, NL, BE, DE, FR, PL but no configs exist.
- **Research questions.**
  1. Does the LEAR model with paper-default hyperparameters transfer
     across European zones, or does each zone need retuning?
  2. Which zones are most studied in the EPF benchmark literature?
     (Nord Pool / EPEX / PJM are well-covered; DK1 specifically?)
  3. Is there evidence that **bidding-zone size** (small DK1 vs large
     DE) affects model choice?
- **Acceptance criterion.** A short guide outlining the cross-market
  evidence base and recommending which additional zones to onboard
  next for the strongest publication contribution.
- **Deliverable.** `researh_material/reading_guides/cross_market_generalization_reading_guide.md`.

---

### Gap 8 — Refit interval (daily vs weekly vs adaptive)
- **Priority:** **P2**.
- **Status:** OPEN.
- **What the code does today.** `refit_interval_days=1` for LEAR
  (daily), with a comment in `ExperimentConfig` suggesting `7` for
  DNN.
- **Research questions.**
  1. What's the empirical cost (rMAE delta) of weekly vs daily refit
     for LEAR on DK1-like markets?
  2. For DNN/Transformer, is weekly refit standard? Does the
     Llorente-Portela "train once + renormalize" path beat any
     fixed-interval refit?
  3. Is there work on **drift-triggered** retraining as an alternative
     to fixed intervals?
- **Acceptance criterion.** A short guide with a recommended interval
  per model family.
- **Deliverable.** `researh_material/reading_guides/refit_interval_reading_guide.md`.

---

### Gap 9 — Computational cost reporting
- **Priority:** **P2**.
- **Status:** OPEN — flagged as FAIL on Lago checklist item 3.
- **What the code does today.** `LiveResult.training_duration_seconds`
  is captured but per-backtest-day timing is not reported.
- **Research questions.** (Lighter-weight; mostly engineering.)
  1. What's the established reporting format for compute cost in EPF
     papers (Lago §5.9)?
  2. Are wall-clock seconds sufficient, or is a hardware-normalized
     metric expected?
- **Acceptance criterion.** A 1-page note recommending what to report
  and citing 2–3 EPF papers that did it well.
- **Deliverable.** `researh_material/reading_guides/computational_cost_reporting_reading_guide.md`.

---

### Gap 10 — Spike & negative-price handling
- **Priority:** **P2**.
- **Status:** OPEN.
- **What the code does today.** Nothing. Spikes flow through Lasso;
  negative prices flow through `StandardScaler` and the model.
- **Research questions.**
  1. Is explicit spike modeling (regime-switching, jump-diffusion —
     Weron 2014 §3.5–3.6) still considered necessary in modern
     LEAR/DNN approaches, or do dense lag features absorb spikes?
  2. How does the literature handle **negative prices** specifically?
     Are they treated as a separate regime?
  3. Does VST (Gap 2) substantively close this gap by itself?
- **Acceptance criterion.** A short reading guide that either
  (a) recommends a spike-handling addition with citations, or
  (b) documents the literature consensus that "modern features +
  VST sufficient".
- **Deliverable.** `researh_material/reading_guides/spike_and_negative_price_handling_reading_guide.md`.

---

### Gap 11 — Probabilistic forecasting (future direction)
- **Priority:** **P2** (research, not blocking).
- **Status:** OPEN. `Nowotarski & Weron 2018` is in the repo as a
  primer but no synthesis exists.
- **Research questions.**
  1. What's the cheapest path from a point-forecast LEAR to a
     probabilistic one (quantile regression LASSO? bootstrap of
     ensemble residuals? conformal prediction?).
  2. Which metric should the project track (CRPS, pinball loss,
     interval coverage)?
  3. What's the SOTA for probabilistic EPF as of 2024–2025?
- **Acceptance criterion.** A reading guide synthesizing
  Nowotarski & Weron 2018 plus recent extensions, plus a concrete
  recommended next step.
- **Deliverable.** `researh_material/reading_guides/probabilistic_epf_reading_guide.md`.

---

### Gap 12 — Hyperparameter tuning protocol for non-Lasso models
- **Priority:** **P2**.
- **Status:** OPEN.
- **What the code does today.** LEAR uses `LassoCV(cv=TimeSeriesSplit)`
  (defensible — Lago §5.7). Other models have no protocol.
- **Research questions.**
  1. For GBT models on EPF, is there published guidance on the
     tuning grid (depth, learning rate, n_estimators)?
  2. For DNN, what early-stopping patience / validation-fraction
     is standard?
  3. Should hyperparameters be tuned **once per market** or
     **per refit window**?
- **Acceptance criterion.** Short per-family guide with recommended
  search spaces and primary citations.
- **Deliverable.** `researh_material/reading_guides/hyperparameter_tuning_for_epf_reading_guide.md`.

---

## 6. Output format

For each gap you work, produce **all four** of the following:

### 6.1 Annotated bibliography
- Inline at the top of the deliverable `.md`, before the synthesis.
- One entry per paper. Entry format:
    ```
    ### [Author Year]: Title
    - **Citation.** Full citation (authors, year, journal/conference, volume/issue/pages, DOI).
    - **Relevance.** 1 sentence explaining why it answers the gap.
    - **Key result for this project.** 2–4 sentences with the *specific* numbers, formulas, or recommendations.
    - **Quotes.** Direct quotes (verbatim, with page numbers) for the most load-bearing claims.
    - **Open access.** Yes / No + link (preprint, journal, repository).
    ```
- Cite **at least 3 primary sources** per gap. Two is acceptable when
  the field is narrow; one is insufficient.

### 6.2 Synthesis section
- 1–3 pages summarizing the current consensus, disagreements, and
  recommendation for this codebase.
- Always include the recommendation in a callout block:
    ```
    > **Recommendation for algo-repo.** [Concrete change | engineering
    > rationale | "no recommendation; existing default is acceptable"].
    > Citation: [Author Year].
    ```
- If the literature is genuinely silent, **say so explicitly** in a
  callout. Don't pad.

### 6.3 Codebase pointer section
- A table mapping cited concepts → the exact codebase locations they
  apply to (`file.py:line` where possible — but you can read the code
  for accuracy; you have read access).

### 6.4 Update this brief
- When you finish a gap, set its `Status:` line to
  `COMPLETE → researh_material/reading_guides/<your_file>.md`.
- If you discover a **new** gap while researching, add it to section 5
  with `Status: OPEN — discovered <YYYY-MM-DD>`.

### Naming and location
- All deliverables go to `researh_material/reading_guides/`.
- Filename: `<topic>_reading_guide.md` (lowercase, snake_case). Use the
  filename suggested in each gap's "Deliverable" line; don't invent new
  ones.

### Citation style
- Either **APA 7** or **Chicago author-date**; pick one and stay
  consistent within a single deliverable. The existing guides use a
  loose APA — match them.

---

## 7. Quality bar — read this before searching

- **No hallucinated citations.** Every paper you cite must have a
  verifiable DOI / arXiv ID / journal URL. If you cannot verify a
  paper exists, do not cite it.
- **Primary sources first.** Cite the paper that *originated* a
  technique, not a textbook summary or a Medium post.
- **Recency matters but is not everything.** A 2008 paper that
  remains the canonical reference (e.g. Diebold-Mariano 1995) is
  fine. A 2024 preprint with 0 citations is not.
- **Negative results are valuable.** "We searched A, B, and C with
  queries X, Y, Z; found no EPF-specific work on this question" is
  a complete deliverable when true.
- **Page numbers.** When you quote a paper, cite the page. The
  existing reading guides do this.
- **No vendor blogs as primary citations.** Evidently / W&B / MLflow
  blog posts can be cited as engineering context, never as primary
  research.
- **Be explicit about confidence.** Distinguish "the literature
  unambiguously recommends X" from "two papers suggest X; one
  suggests Y; the project should pick on engineering grounds."
- **Engineering rationale is acceptable when literature is silent.**
  But it must be *labeled* as such — never disguised as research
  consensus.
- **Don't expand scope.** If a gap implicates another design choice
  the project hasn't asked about, mention it briefly and add it to
  §5 as a new OPEN gap; don't research it inline.

---

## 8. Suggested first move

If you have no other instruction, start with **Gap 1 (statistical
significance testing)**. It's the highest-priority open gap, has the
cleanest literature, and unlocks every other gap (you can't show that
Gap 2's VST helps until you can test for significance).

After Gap 1, work in priority order: 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9
→ 10 → 11 → 12. Within the same priority, pick the one whose
deliverable would most change current production behavior.

---

## 9. Out of scope

You are **not** asked to:

- Modify any code under `src/`.
- Modify any config in `configs/`.
- Open pull requests.
- Run the model, the backtest, or any experiment.
- Curate datasets.
- Make architectural recommendations beyond the reading guides.

You **are** asked to:

- Write `researh_material/reading_guides/*.md`.
- Update §5 of this brief with `Status:` lines.
- Optionally add new PDFs to `researh_material/` if you have the
  rights to redistribute them and they're directly cited in your
  guides.

---

## 10. Update protocol for this brief

The human owner updates §1–§3 (project state, goals, glossary) and the
priority assignments in §5. Research-LLM sessions update only the
`Status:` lines in §5 and add new OPEN gaps when discovered. If your
research surfaces a finding that changes a project goal (e.g. evidence
that LEAR is dominated by a newer architecture), **note it in the
gap's synthesis section and flag it explicitly** — do not edit §2.
