# Thesis Report — Full Structure & Assembly Design

**Date:** 2026-06-04
**Status:** Approved structure (brainstorming session 2026-06-04); spec under owner review
**Goal:** Define the complete chapter/section structure for the thesis — a detailed
heading-and-bullet blueprint covering every part *except* the modelling results
(which await the six final `--track` runs) — so the report can be written against a
fixed plan. Write to completeness first (estimated ~45–50pp), then trim to a coherent
~40–45pp in a later pass (D3). The report integrates two threads:
a paper-faithful EPF model comparison embedded in a production MLOps platform.

This spec is the **plan**; LaTeX assembly and prose are the **implementation step**
(deferred to writing-plans). No `.tex` files are created by this spec.

---

## 1. Framing

The thesis makes one integrated argument with two threads:

- **Primary thread — MLOps system.** An end-to-end production platform (ingestion →
  storage → rolling recalibration → serving → reconciliation → monitoring → drift)
  built and assessed against the nine MLOps practices of Zarour et al. (2025). This is
  the principal contribution (RQ2, RQ3).
- **Embedded thread — EPF model comparison.** A faithful replication of LEAR and DNN
  (Lago et al. 2021) and a Transformer (Llorente & Portela 2025), compared on recent
  ENTSO-E data for DK1 and DE with paired DM/GW significance testing. This is the
  forecasting payload the system delivers (RQ1).

The valid comparison against the source papers is **methodology replication +
relative metrics (rMAE) + model rankings**, not absolute errors (different price
regime, 2025–26 vs 2016–18).

## 2. Decisions made this session

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| D1 | Chapter architecture | **Linear, MLOps-led (Approach B)** | Maps ~1:1 onto existing drafts; gives the model comparison a proper Results chapter; MLOps is the larger/detailed thread. Rejected: formal two-`\part` split (awkward eval/results split); single forecasting case-study chapter (under-serves the DM/GW experiments). |
| D2 | Assembly scope now | **Structure/outline only** | Build `Report/main.tex` + write prose in the implementation step, not now. |
| D3 | Page budget | **Write to completeness, cut later** | Owner: "easier to write it then cut down." Do not pre-condense; land mid-40s, trim in a later pass. |
| D4 | Evaluation placement | **Dedicated Evaluation Framework + Results chapters; system chapter becomes implementation-only** | Removes the duplication between `system_implementation.tex`'s "Quantitative evaluation" section and the framework/results scaffolds. |
| D5 | Thread emphasis | **MLOps primary, forecasting embedded** | Two of three RQs are MLOps; reflected in chapter sizing (System Implementation is the largest chapter). |
| D6 | Research questions | **Redefine freely** | `ProjectPlan.pdf` RQs (LEAR-only, DE-only, calibration-window sensitivity) are a rough draft and are superseded — scope is now 3 models × 2 markets. Calibration-window sensitivity drops to future work (matrix uses fixed windows). |

## 3. Research questions (final)

- **RQ1 (forecasting).** How do faithfully-replicated LEAR, DNN, and Transformer
  day-ahead EPF models compare on recent ENTSO-E data for the DK1 and DE bidding
  zones — against one another, a weekly-naive baseline, and the rankings reported by
  Lago et al. (2021) and Llorente & Portela (2025)?
- **RQ2 (engineering).** What engineering trade-offs and operational constraints
  emerge when embedding these benchmark models into a scheduled, containerized,
  continuously-monitored production pipeline?
- **RQ3 (maturity).** Assessed against Zarour et al.'s nine MLOps practices and the
  Google maturity model, which practices does the platform realise, which prove most
  critical, and where does a single-host MVP reach its limit?

## 4. Chapter-by-chapter structure (Approach B)

Legend: **[now]** writable immediately · **[awaits]** needs the six `--track` runs ·
`→` maps to existing/new draft file under `Report/chapters/`.

### Front matter [now] (~2pp)
Title page; abstract (~250 words stating the dual contribution and headline findings —
leave a numeric slot for the forecasting result); table of contents; list of
figures/tables; acronyms (EPF, MLOps, LEAR, DNN, DM, GW, ENTSO-E, …).

### Ch 1 — Introduction [now] (~3–4pp) `→ new chapters/introduction.tex`
- Problem: day-ahead EPF is hard — renewables-driven supply volatility, negative
  prices/spikes, cross-zone coupling; accurate forecasts matter to generators,
  retailers, grid operators. (Seed from `ProjectPlan` §1 intro prose.)
- Gap: the EPF literature evaluates offline and stops at "predictions done" (Lago,
  Weron, Nowotarski & Weron); MLOps emerged to close the build→run gap (Stone, Zarour);
  the two literatures do not meet.
- This work: embed faithful EPF benchmark models in an end-to-end MLOps platform;
  evaluate forecast quality **and** operational maturity.
- Research questions (§3 above).
- Contributions (bulleted): the platform; the faithful 3-model × 2-market replication;
  the composed quantitative evaluation of an MLOps system (ML Test Score + reproducibility
  + DORA); the practice-by-practice maturity assessment.
- Report outline (one line per chapter); scope & non-goals paragraph.

### Ch 2 — Background & Related Work [now] (~5–6pp) `→ new chapters/background.tex`
- 2.1 Day-ahead EPF & market mechanics; statistical properties that make it hard
  (Weron 2014; Nowotarski & Weron 2018).
- 2.2 The Lago et al. (2021) open-access benchmark: LEAR & DNN, epftoolbox,
  recalibration methodology, rMAE and DM/GW testing, asinh VST (Uniejewski et al. 2018).
- 2.3 Transformer approach to EPF (Llorente & Portela 2025) — encoder-only dual-input.
- 2.4 MLOps: definition; Zarour SLR nine practices + maturity models; Google 3-level
  model; the deployment-adoption gap (Stone et al.); domain precedent for MLOps in
  electricity forecasting (Subramanya et al. 2022).
- 2.5 Evaluation methodology: single-case study research (Runeson & Höst 2009); ML Test
  Score (Breck et al. 2017); reproducibility & ACM badging (Gundersen & Kjensmo 2018);
  DORA throughput (Forsgren et al. 2018); cost-aware retraining (Mahadevan & Mathioudakis 2024).

### Ch 3 — Methods: Forecasting Models [now; numbers await] (~8–10pp, large) `→ methods_models_draft.tex` (expand scaffold → prose; add as-implemented architecture detail)
- 3.1 Replication framing — what "faithful replication" means; rMAE + rankings; paired
  DM/GW on one shared test window across all six runs.
- 3.2 Data & features:
  - ENTSO-E sources (price, load, wind on/offshore, solar); markets DK1 & DE.
  - Resolution handling: both markets clear in 15-min; downsample to hourly arithmetic
    mean (`resample_to_hourly`) for cross-market and cross-paper comparability; DK1 has
    <1 month of 15-min history pre-test so native 96-period is infeasible.
  - Paper-exact exogenous via `exogenous_aggregates` (DK1: load + wind; DE: load +
    renewables = wind+solar); inner-join semantics (coarsest series anchors the grid).
  - Feature construction: price lags d-1,d-2,d-3,d-7; exogenous at d0,d-1,d-7; 7
    day-of-week dummies; dimensionality `4n + 2·3n + 7` (n=24 ⇒ 247).
  - asinh variance-stabilising transform.
  - Datasets table + data-gap note (missing DK1 wind days drop identically across DK1
    models → paired tests stay valid).
- 3.3 Models as implemented:
  - LEAR — one Lasso per delivery period; λ via `LassoCV` (TimeSeriesSplit); multi-window
    ensemble averaging.
  - DNN — MLP, MIMO (one network → all periods); 4-seed ensemble averaging; architecture
    HPs from Optuna TPE; report the tuned values per market.
  - Transformer — dual-input encoder (past-price sequence + day-ahead exogenous),
    learnable positional encoding, MLP head; 14-day sequence; paper NP hyperparameters.
  - Model-setups table (spec/calibration/refit per model).
- 3.4 Recalibration & backtesting — walk-forward `BacktestEngine`; per-window state
  caching; calibration-window ensemble; refit intervals (LEAR/DNN daily, Transformer
  weekly); date-based split (train = everything before test start).
- 3.5 Evaluation protocol (modelling-side):
  - MAE, RMSE, sMAPE, rMAE (exact formulas as coded) with weekly-naive baseline.
  - Multivariate Giacomini–White on daily L1 loss differentials with Newey–West HAC SE;
    pairwise Diebold–Mariano as univariate complement; common-surviving-days handling.
  - Computation cost: training seconds per recalibration (Lago Table 4 analogue).
- 3.6 Hyperparameter tuning protocol — Optuna TPE; 6-HP architecture search space
  (`n_neurons`, `activation`, `dropout`, `learning_rate`, `batch_norm`, `l1_reg`);
  ex-ante validation window 2025-01-01→2025-10-23; persistence to
  `algo.hyperparam_trials`; Lago's 10 binary feature/selector HPs intentionally omitted
  (preprocessor exposes no toggles → inert dimensions).
- 3.7 Deviations-from-papers table (test length; tuning budget; search space; LEAR
  windows; DNN window; λ selection; market resolution; Transformer pipeline; Transformer HPs).

### Ch 4 — System Implementation [now] (~13–16pp, large — kept detailed) `→ system_implementation.tex` (REFACTOR: see §5)
- 4.1 Scope (system around the models; modelling deferred to Ch 3) + Zarour-as-lens note.
- 4.2 System at a glance — host architecture (fig f1); data plane (fig f2); Prefect
  deployment inventory table; technology-stack-and-rationale table.
- 4.3 Zarour's nine practices P1–P9, each as four moves: framing / implementation in
  algo-repo / technology chosen + rejected alternatives / single-host MVP rationale.
  Includes drift-feedback loop (fig f4) under P9.
- 4.4 Cross-cutting: CI/CD as binding fabric — PR gate vs deploy gate; Tailscale-mediated
  deploy without exposing the host (fig f3); GIT_SHA propagation as the
  reproducibility↔monitoring link; why single-host is the right MVP scope.
- 4.5 Deferred tooling & adoption triggers (MLflow, Kubernetes, cloud model store, DVC).
- *(Moved OUT of this chapter: the "Quantitative evaluation" section → Ch 7; the
  practice-by-practice maturity table → Ch 7; the Glossary → Appendix A; the
  problem-framing intro → folded into Ch 1.)*

### Ch 5 — Evaluation Framework [now] (~5–6pp) `→ evaluation_framework_draft.tex` (expand scaffold)
- Approach: single-case study; honesty boundary; objective measurement vs structured
  self-assessment.
- Test inventory (5 tests) + why these five (mapping to Zarour's 9 practices).
- ML Test Score rubric (origin; 0/0.5/1 scoring; min-of-sections rule; how conducted).
- Reproducibility tests (provenance coverage + re-run demonstration; ACM badge mapping).
- Delivery throughput (DORA scope — what is measured/excluded and why).
- Drift monitoring counts (definition; monitoring-not-trigger framing preview).
- Maturity-model positioning (the five candidates; justify Google 3-level).
- **Bridge paragraph**: cross-reference the modelling-side evaluation protocol (Ch 3.5)
  so this chapter frames evaluation for *both* threads.
- Threats-to-validity preview + explicit non-claims table.

### Ch 6 — Results: Forecasting [awaits experiments] (~6–8pp) `→ new chapters/results_models_draft.tex` (table skeletons + figure stubs now; numbers on run completion)
- 6.1 Headline accuracy per market: MAE/RMSE/sMAPE/rMAE × {LEAR, DNN, Transformer, naive}.
- 6.2 Statistical significance: per-market GW p-value matrix (heatmap fig) + DM complement.
- 6.3 Comparison vs published benchmarks: our rMAE + rankings vs Lago Table 3 (NP/DE) and
  Llorente Table 5 (NP/DE), with the different-period caveat stated.
- 6.4 Computation cost (Lago Table 4 analogue) from `Report/metrics/run_timings.md`.
- 6.5 Qualitative: sample forecast week per market (fig); per-hour MAE profile (fig;
  optional per-hour DM).
- 6.6 Forecasting discussion: model ranking, market differences, what replicated / what didn't.
- Data source: `Report/metrics/model_comparison.md` (produced by
  `scripts/report/extract_model_comparison.py`).

### Ch 7 — Results: System Evaluation [now — numbers exist] (~4–5pp) `→ results_system_draft.tex` (expand scaffold)
- ML Test Score results (headline 2.5; per-section breakdown; binding section = Data;
  optional rescore note for S1-2/S1-4).
- Reproducibility results (66.7% provenance triple; 7×10⁻⁶ EUR/MWh re-run; ACM badges).
- Delivery throughput results (19 deploys, 1.48/wk, 0.1-min lead; explicit non-claims).
- Drift as monitoring not trigger (35/35 reframing; Mahadevan; calibration limitation).
- Maturity placement (the practice-by-practice Google-level table, **moved from Ch 4**).
- Threats to validity (full) + known gaps (system side).

### Ch 8 — Discussion [now; RQ1 part awaits] (~3–4pp) `→ new chapters/discussion.tex`
- RQ1 answer (forecasting findings — structure now, numbers later).
- RQ2 answer (engineering trade-offs synthesised from Ch 4).
- RQ3 answer (critical practices & limits — from maturity + ML Test Score binding section).
- Tying the threads: how MLOps choices served/constrained the models (resample-to-hourly
  for comparability; daily cheap refit makes drift-triggered retraining redundant — the
  cost-aware argument); the platform as the artefact that makes the replication reproducible.
- Consolidated limitations.

### Ch 9 — Conclusion & Future Work [now] (~2pp) `→ new chapters/conclusion.tex`
- Contributions recap; 8/9 practices realised, P9 minimal.
- Future work: 1456-day window & LARS+AIC λ; probabilistic forecasting (pinball/CRPS);
  Transformer per-market tuning; epftoolbox side-by-side on 2016–18 data;
  DNN/Transformer reproducibility under controlled seeds; Data-tests investment (binding
  ML Test Score section); drift-detector calibration; multi-area forecast/drift expansion;
  calibration-window sensitivity ablation (dropped from RQ scope); MLflow/K8s/cloud-store triggers.

### Appendices [now]
- A. Glossary (moved from `system_implementation.tex`).
- B. ML Test Score 28-item worksheet (from `Report/metrics/ml_test_score.md`).
- C. (optional) Extended tables — full deferred-tooling rationale, config listings.

## 5. File plan & refactor map

**Existing chapter files → integrated chapters:**
- `methods_models_draft.tex` → Ch 3 (expand bullets → prose; add §3.3 architecture detail).
- `system_implementation.tex` → Ch 4, **with extractions:**
  - "Quantitative evaluation" subsection (ML Test Score / reproducibility / DORA / drift /
    summary) → **Ch 7**.
  - Practice-by-practice maturity table (`tab:maturity`) → **Ch 7**.
  - `\section{Introduction}` problem-framing → folded into **Ch 1**; leave a short
    "Scope of this chapter" paragraph.
  - `\section{Conclusion}` → folded into **Ch 9**.
  - Glossary appendix → **Appendix A**.
  - Keep: System at a Glance, the nine practices, cross-cutting CI/CD, deferred tooling.
- `evaluation_framework_draft.tex` → Ch 5 (expand; add the modelling-eval bridge paragraph).
- `results_system_draft.tex` → Ch 7 (expand; absorb the extracted quant-eval + maturity table).

**New files to create (implementation step):**
- `chapters/introduction.tex`, `chapters/background.tex`,
  `chapters/results_models_draft.tex`, `chapters/discussion.tex`,
  `chapters/conclusion.tex`, `chapters/appendices.tex`.
- `Report/main.tex` — master document (`report`, 11pt, a4, 2.5cm margins; shared
  preamble; `\input`s every chapter; single `\bibliography{references}`). Replaces the
  per-chapter standalone wrappers for the integrated build (standalones may stay for
  proofing).

## 6. Figures

- **Existing (system):** f1-architecture, f2-data-plane, f3-cicd, f4-drift-feedback
  (`Report/figures/system_implementation/`).
- **To create (forecasting, Ch 6):** GW p-value heatmap (per market); sample forecast
  week (per market, predicted vs actual); per-hour MAE profile.
- **Optional:** a feature-pipeline schematic (Ch 3); a thesis-level two-thread/system-context
  diagram (Ch 1).

## 7. Writable now vs awaiting experiments

- **Now (the whole skeleton + most prose):** front matter, Ch 1, 2, 3 (all but final
  numbers), 4, 5, 7, 8 (all but RQ1 numbers), 9, appendices.
- **Awaits the six `--track` runs:** Ch 6 numbers/figures; the RQ1 numeric answer in
  Ch 8.1; the abstract's headline figure; Ch 3 can be fully written (it is method, not result).

## 8. Page strategy

Write to completeness (D3). Estimated full body ~45–50pp. Trim in a dedicated later pass
if it exceeds the ceiling; first cuts target the lighter Zarour practices (P1, P5) in
Ch 4 and any duplication between Ch 5 and Ch 7 — never Ch 3 or Ch 6. Glossary + ML Test
Score worksheet already routed to appendices.

## 9. Out of scope

- Re-running experiments / changing the experiment matrix (owned by the separate
  final-model-experiments spec).
- New statistical tests beyond DM/GW.
- Probabilistic forecasting.
- Building `main.tex` / writing prose in this spec (that is the implementation step).

## 10. Next step

On approval of this spec, transition to the writing-plans skill to produce the
implementation plan: ordering of chapter writing, the `system_implementation.tex`
refactor steps, `main.tex` assembly, figure creation, and the points where Ch 6 / the
abstract / Ch 8.1 are filled once the runs complete.
