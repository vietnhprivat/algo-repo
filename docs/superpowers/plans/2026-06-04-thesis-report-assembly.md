# Thesis Report Assembly Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Assemble the existing chapter drafts and new chapters into one integrated, compiling thesis (`Report/main.tex`) following the approved structure spec, writing every part that does not depend on the six final `--track` runs.

**Architecture:** A master LaTeX document (`report` class, 11pt, a4, 2.5cm margins) `\input`s nine chapters + front matter + appendices and owns a single bibliography. Work proceeds: build harness + stubs → relocate content out of the oversized System Implementation chapter → write/expand each chapter → wire forecasting figures and the data-blocked slots last. Each task keeps the master compiling and ends in a commit.

**Tech Stack:** LaTeX (`latexmk` + `pdflatex` + `bibtex`), TikZ (existing system figures), Python + matplotlib (new forecasting figures), the metrics artifacts under `Report/metrics/`.

**Source of truth for content:** `docs/superpowers/specs/2026-06-04-thesis-report-structure-design.md` (the structure spec). Each writing task names the exact spec section to follow and embeds the concrete values/citations needed so it is actionable without re-deriving anything.

**Bibliography keys already available** (`Report/references.bib`): `zarour2025`, `lago2021`, `google_mlops_maturity`, `runeson2009casestudy`, `breck2017mltestscore`, `gundersen2018reproducibility`, `forsgren2018accelerate`, `mahadevan2024costaware`, `subramanya2022devops2mlops`, `llorente2025transformer`, `uniejewski2018vst`, `diebold1995dm`, `giacomini2006gw`.

**Convention reminders:** commit only the files each task names (do not `git add -A` — the working tree has unrelated untracked files: `Report/methods_models_draft_standalone.pdf`, `Report/metrics/run_timings.md`). End commit messages with the `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>` trailer. Branch is `final-model-experiments`.

---

## File structure

**New files:**
- `Report/main.tex` — master document; shared preamble; `\input`s all chapters + front/back matter; single `\bibliography`.
- `Report/chapters/frontmatter.tex` — title block, abstract, acronym list.
- `Report/chapters/introduction.tex` — Ch 1.
- `Report/chapters/background.tex` — Ch 2.
- `Report/chapters/results_models_draft.tex` — Ch 6 (skeleton + data-blocked slots).
- `Report/chapters/discussion.tex` — Ch 8.
- `Report/chapters/conclusion.tex` — Ch 9.
- `Report/chapters/appendices.tex` — Appendix A (glossary), B (ML Test Score worksheet).
- `scripts/report/plot_forecast_figures.py` — renders the three Ch 6 figures from run outputs.

**Modified files:**
- `Report/chapters/system_implementation.tex` — Ch 4; slimmed (eval, maturity table, problem-framing intro, conclusion, glossary removed).
- `Report/chapters/methods_models_draft.tex` — Ch 3; scaffold expanded to prose + architecture detail.
- `Report/chapters/evaluation_framework_draft.tex` — Ch 5; scaffold expanded + modelling-eval bridge.
- `Report/chapters/results_system_draft.tex` — Ch 7; scaffold expanded; absorbs the relocated quant-eval section + maturity table.
- `Report/references.bib` — add `weron2014`, `nowotarski2018` (+ optionally an MLOps adoption-gap source).

**Mapping (chapter → file):** Ch1 `introduction.tex` · Ch2 `background.tex` · Ch3 `methods_models_draft.tex` · Ch4 `system_implementation.tex` · Ch5 `evaluation_framework_draft.tex` · Ch6 `results_models_draft.tex` · Ch7 `results_system_draft.tex` · Ch8 `discussion.tex` · Ch9 `conclusion.tex`.

---

## Task 0: Build harness + master document + chapter stubs

**Files:**
- Create: `Report/main.tex`, `Report/chapters/frontmatter.tex`, `Report/chapters/introduction.tex`, `Report/chapters/background.tex`, `Report/chapters/results_models_draft.tex`, `Report/chapters/discussion.tex`, `Report/chapters/conclusion.tex`, `Report/chapters/appendices.tex`

- [ ] **Step 1: Verify the LaTeX toolchain exists**

Run: `which latexmk pdflatex bibtex && latexmk --version`
Expected: paths printed and a version line. If `latexmk` is missing, stop and report — the rest of the plan depends on it.

- [ ] **Step 2: Create the six new chapter stubs**

Each stub is a real `\chapter` with the `\label` the other chapters already `\ref`, plus a one-line note. This makes cross-references resolve from the first build. Exact contents:

`Report/chapters/introduction.tex`:
```latex
\chapter{Introduction}
\label{ch:introduction}
% Written in Task 3.
```
`Report/chapters/background.tex`:
```latex
\chapter{Background and Related Work}
\label{ch:background}
% Written in Task 4.
```
`Report/chapters/results_models_draft.tex`:
```latex
\chapter{Results --- Forecasting}
\label{ch:results-models}
% Skeleton in Task 9; numeric cells filled once the six --track runs complete.
```
`Report/chapters/discussion.tex`:
```latex
\chapter{Discussion}
\label{ch:discussion}
% Written in Task 10.
```
`Report/chapters/conclusion.tex`:
```latex
\chapter{Conclusion and Future Work}
\label{ch:conclusion}
% Written in Task 11.
```
`Report/chapters/appendices.tex`:
```latex
% Appendices. Bodies written in Task 12.
\chapter{Glossary}
\label{app:glossary}

\chapter{ML Test Score Worksheet}
\label{app:mlts-worksheet}
```

`Report/chapters/frontmatter.tex`:
```latex
% Title block, abstract, acronyms. Bodies written in Task 13.
```

- [ ] **Step 3: Create `Report/main.tex`**

```latex
% Master thesis document. Build: latexmk -pdf main.tex
\documentclass[11pt,a4paper]{report}

\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[margin=2.5cm]{geometry}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{array}
\usepackage{tabularx}
\usepackage{tikz}
\usetikzlibrary{positioning, arrows.meta, shapes.geometric, shapes.symbols, backgrounds, fit, calc}
\usepackage{hyperref}
\usepackage{microtype}

\setlength{\emergencystretch}{3em}
\hyphenpenalty=1000
\tolerance=1000

\graphicspath{{figures/}{figures/system_implementation/}{figures/results_models/}}

\begin{document}

\input{chapters/frontmatter}

\tableofcontents
\listoffigures
\listoftables
\clearpage

\input{chapters/introduction}
\input{chapters/background}
\input{chapters/methods_models_draft}
\input{chapters/system_implementation}
\input{chapters/evaluation_framework_draft}
\input{chapters/results_models_draft}
\input{chapters/results_system_draft}
\input{chapters/discussion}
\input{chapters/conclusion}

\appendix
\input{chapters/appendices}

\bibliographystyle{plain}
\bibliography{references}

\end{document}
```

Note: `system_implementation.tex` currently ends with its own `\appendix\section{Glossary}` and an `\iffalse...\fi` preamble comment. Those are removed in Task 2; until then the master may show the glossary mid-document — acceptable for this intermediate build.

- [ ] **Step 4: Build the master and confirm it compiles**

Run: `cd Report && latexmk -pdf -interaction=nonstopmode main.tex`
Expected: `main.pdf` is produced. Undefined-reference warnings and `??` marks are expected at this stage (chapters are stubs); there must be **no fatal errors** (no "Emergency stop", no missing `\begin{document}`). Confirm with: `pdfinfo main.pdf | grep Pages`.

- [ ] **Step 5: Commit**

```bash
cd /home/vietnh/Projects/algo-repo
git add Report/main.tex Report/chapters/frontmatter.tex Report/chapters/introduction.tex Report/chapters/background.tex Report/chapters/results_models_draft.tex Report/chapters/discussion.tex Report/chapters/conclusion.tex Report/chapters/appendices.tex
git commit -m "feat(report): master document + chapter stubs (compiling skeleton)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 1: Relocate content out of System Implementation (Ch 4 slim-down)

Per spec §5, five blocks leave `system_implementation.tex`. This task moves them into their destination files so nothing is lost, then deletes them from Ch 4. Use section *names* to locate blocks (line numbers below are indicative from the 2026-06-04 read and may have shifted).

**Files:**
- Modify: `Report/chapters/system_implementation.tex`
- Modify: `Report/chapters/results_system_draft.tex` (receives quant-eval + maturity table)
- Modify: `Report/chapters/introduction.tex` (receives problem-framing raw material)
- Modify: `Report/chapters/conclusion.tex` (receives conclusion raw material)
- Modify: `Report/chapters/appendices.tex` (receives glossary)

- [ ] **Step 1: Copy the "Quantitative evaluation" block into Ch 7**

In `system_implementation.tex`, find `\subsection{Quantitative evaluation}` (≈ line 703) through the end of its `\subsubsection{Summary}` (≈ line 805). Copy that whole block verbatim into `results_system_draft.tex`, appended after the existing scaffold, wrapped in a marker comment:
```latex
% === Relocated from system_implementation.tex (Task 1). Integrated/expanded in Task 8. ===
```
This block contains the ML Test Score table (`tab:ml-test-score`), the reproducibility prose (incl. the `7\times10^{-6}` figure), the DORA paragraph (19 deployments, 1.48/week, 0.1 min), and the drift-as-monitoring paragraph (35/35). Keep its labels for now.

- [ ] **Step 2: Copy the maturity table + practice-by-practice prose into Ch 7**

In `system_implementation.tex`, find `\subsection{Practice-by-practice status}` and its `\begin{table}...\label{tab:maturity}...\end{table}` (≈ lines 672–701). Copy that subsection (intro paragraph + the `tab:maturity` table) into `results_system_draft.tex`, after the relocated block from Step 1, under the same marker comment. **Preserve `\label{tab:maturity}` exactly** — both Ch 5 (`evaluation_framework_draft.tex`) and Ch 7 `\ref` it.

- [ ] **Step 3: Copy the Glossary into Appendix A**

In `system_implementation.tex`, find `\appendix \section{Glossary}` … `\end{description}` (≈ lines 890–928). Move the `description` list into `appendices.tex` under the existing `\chapter{Glossary}\label{app:glossary}` stub (drop the old `\appendix` and `\section{Glossary}` lines — the master issues `\appendix` once and the appendix is now a `\chapter`).

- [ ] **Step 4: Copy the Conclusion into Ch 9 as raw material**

In `system_implementation.tex`, find `\section{Conclusion}` (≈ lines 869–887). Copy its prose into `conclusion.tex` under the stub, wrapped in:
```latex
% === Relocated from system_implementation.tex (Task 1). Rewritten thesis-wide in Task 11. ===
```

- [ ] **Step 5: Copy the problem-framing into Ch 1 as raw material**

In `system_implementation.tex` `\section{Introduction}`, find `\subsection{Problem framing}` (≈ lines 13–27). Copy its two paragraphs into `introduction.tex` under the stub, wrapped in:
```latex
% === Relocated from system_implementation.tex (Task 1). Rewritten as thesis intro in Task 3. ===
```

- [ ] **Step 6: Delete the moved blocks from Ch 4 and leave it implementation-only**

In `system_implementation.tex`:
- Ensure the chapter line reads `\chapter{System Implementation}\label{ch:system-implementation}` — other chapters `\ref{ch:system-implementation}`; add the label if it is absent.
- Delete the `\iffalse ... \fi` comment header (lines 1–6).
- Delete `\subsection{Problem framing}` (moved in Step 5).
- Keep `\subsection{Scope of this chapter}` and `\subsection{Methodology --- Zarour (2025) as structuring lens}`, but promote them so the chapter opens with `\section{Introduction}` → rename that section to `\section{Scope and approach}`.
- Delete `\section{Maturity Assessment and Limitations}` **except** its `\subsection{Deferred tooling and adoption triggers}` block: keep that and re-home it as `\section{Deferred tooling and adoption triggers}` (spec §4.5). Delete `Practice-by-practice status` (Step 2), `Quantitative evaluation` (Step 1). For the `Known gaps` subsection: copy its three paragraphs (Data-tests/multi-area, artifact scaling, Optuna space) into `discussion.tex` wrapped in a `% relocated, integrated in Task 10` marker, then delete from Ch 4.
- Delete `\section{Conclusion}` (Step 4) and the `\appendix\section{Glossary}` (Step 3).

- [ ] **Step 7: Build and confirm Ch 4 is coherent and the master still compiles**

Run: `cd Report && latexmk -pdf -interaction=nonstopmode main.tex && pdfinfo main.pdf | grep Pages`
Expected: compiles; no fatal errors. Visually confirm `system_implementation.tex` now runs Scope → System at a Glance → Nine Practices → Cross-cutting CI/CD → Deferred tooling, and contains no ML Test Score / maturity / glossary / conclusion content.

- [ ] **Step 8: Commit**

```bash
cd /home/vietnh/Projects/algo-repo
git add Report/chapters/system_implementation.tex Report/chapters/results_system_draft.tex Report/chapters/introduction.tex Report/chapters/conclusion.tex Report/chapters/appendices.tex Report/chapters/discussion.tex
git commit -m "refactor(report): relocate evaluation/maturity/glossary out of system chapter

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Expand Methods — Forecasting Models (Ch 3)

Turn the `methods_models_draft.tex` scaffold (bullets + tables) into prose and add the as-implemented model architecture detail. Follow **spec §4 → "Ch 3"** for the section list. Keep the existing tables (`tab:mm-datasets`, `tab:mm-models`, `tab:mm-deviations`).

**Files:**
- Modify: `Report/chapters/methods_models_draft.tex`

- [ ] **Step 1: Write §3.1 Replication framing + §3.2 Data and features (prose)**

Expand the existing bullets into prose. Concrete facts to state (all verified from code):
- Feature dimensionality formula `4n + 2·3n + 7`; n=24 ⇒ 247 columns; lags: price d-1,d-2,d-3,d-7; exogenous d0,d-1,d-7; 7 day-of-week dummies. Cite `lago2021` (Eq. 3) and `uniejewski2018vst` (asinh).
- `resample_to_hourly`: both markets clear in 15-min (DE throughout; DK1 since 2025-10-01); downsample to hourly arithmetic mean for cross-market + cross-paper comparability; DK1 has <1 month 15-min history pre-test.
- `exogenous_aggregates`: DK1 = TotalLoad + Wind(on+offshore); DE = TotalLoad + Renewables(wind+solar); members inner-joined before summing; all exogenous inner-joined (coarsest series anchors grid).
- Data-gap note (missing DK1 wind days drop identically across DK1 models → paired tests valid).

- [ ] **Step 2: Write §3.3 Models as implemented**

Three subsections, drawn from the code:
- **LEAR** (`models/lear.py`): one `Lasso`/`LassoCV` per delivery period (24); λ via `LassoCV(cv=TimeSeriesSplit(5), max_iter=5000)`; multi-window ensemble averaged across windows 56/84/1092 d; daily refit.
- **DNN** (`models/dnn.py`, `base/lightning.py`): MLP, two hidden layers, MIMO (one network → all 24 periods); L1 (MAE) training loss; Adam; early stopping (patience 25) with in-memory best-weight restore; 4-seed ensemble averaged at serving; architecture HPs from Optuna; report the tuned values — DK1: `hidden_units=198, activation=tanh, dropout=0.027, lr=6.28e-4, batch_norm=False, l1_reg=6.73e-4`; DE: `hidden_units=58, activation=elu, dropout=0.132, lr=4.86e-3, batch_norm=False, l1_reg=5.71e-4`; window 730 d; daily refit. (Note in text these were tuned on the ex-ante validation window; if re-tuned for paper-exact exogenous, update the numbers from the configs at write time.)
- **Transformer** (`models/transformer.py`): dual-input encoder — past-price sequence (`seq_length_days=14`) embedded + learnable positional encoding (N(0,0.02)) → 6-layer, 8-head `TransformerEncoder` (ff_dim 1024) → last token; day-ahead exogenous embedded; concatenated → MLP head (hidden 128) → 24 outputs; `embedding_dim=128, dropout=0.2`; calibration window 1092 d; weekly refit; `n_exog=2`; paper NP hyperparameters reused. Cite `llorente2025transformer`.
- Keep `tab:mm-models`.

- [ ] **Step 3: Write §3.4 Recalibration & backtesting + §3.5 Evaluation protocol**

- §3.4 (`backtesting/engine.py`): walk-forward; per-window `WindowState` caching; refit when `days_since_last_fit >= refit_interval_days`; ensemble = mean across calibration windows; date-based split (`split_by_dates`: train = all rows before `test_start_date`).
- §3.5 metrics (`evaluation/metrics.py`, `summary.py`, `statistical_tests.py`): give the exact formulas — MAE `mean(|y-ŷ|)`; RMSE `sqrt(mean((y-ŷ)²))`; sMAPE `mean(2|y-ŷ|/(|y|+|ŷ|))·100`; rMAE `MAE_model / MAE_weekly-naive` (naive = `shift(7)`). GW: multivariate, daily L1 loss differential, Newey–West HAC with lag `floor(n^0.25)`; cite `giacomini2006gw`, `lago2021`. DM pairwise univariate complement; cite `diebold1995dm`. State the common-surviving-days rule (models compared on days all of them produced).

- [ ] **Step 4: Write §3.6 Tuning protocol + §3.7 keep the deviations table**

- §3.6 (`tuning/`): Optuna TPE; 6-HP architecture space (`n_neurons` 16–512 log, `activation` ∈ {relu,tanh,elu,softplus,sigmoid}, `dropout` 0–0.5, `learning_rate` 1e-5–1e-1 log, `batch_norm`, `l1_reg` 1e-8–1e-2 log); objective = mean validation MAE over the ex-ante window 2025-01-01→2025-10-23; trials persisted to `algo.hyperparam_trials`; Lago's 10 binary feature/selector HPs + `preprocessing`/`init_method` omitted (no constructor toggles → inert dimensions).
- §3.7: keep the existing `tab:mm-deviations` (already complete); convert its surrounding bullets, if any, to a lead-in sentence.

- [ ] **Step 5: Build and content-check**

Run: `cd Report && latexmk -pdf -interaction=nonstopmode main.tex`
Expected: compiles. Checklist: every spec §"Ch 3" bullet (3.1–3.7) has a paragraph; all three model subsections present; metric formulas present; tables intact.

- [ ] **Step 6: Commit**

```bash
cd /home/vietnh/Projects/algo-repo
git add Report/chapters/methods_models_draft.tex
git commit -m "feat(report): Ch3 Methods (forecasting models) — scaffold to prose

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Write the Introduction (Ch 1)

Follow **spec §4 → "Ch 1"**. Use the relocated problem-framing (from Task 1 Step 5) and `ProjectPlan.pdf` §1 as raw material; then remove the relocation marker.

**Files:**
- Modify: `Report/chapters/introduction.tex`

- [ ] **Step 1: Write the problem + gap + this-work narrative**

Paragraphs: (a) DA-EPF and why it is hard (renewables volatility, negative prices/spikes, cross-zone coupling) — cite `weron2014`; (b) the gap: EPF literature evaluates offline and stops at "predictions done" (`lago2021`, `nowotarski2018`), MLOps emerged to close the build→run gap (`zarour2025`), the two literatures do not meet — domain precedent `subramanya2022devops2mlops`; (c) this work: embed faithful EPF benchmarks (LEAR/DNN/Transformer) in an end-to-end MLOps platform; evaluate forecast quality and operational maturity.

- [ ] **Step 2: Write the research questions, contributions, outline, scope**

- RQs verbatim from **spec §3** (RQ1 forecasting comparison; RQ2 engineering trade-offs; RQ3 maturity).
- Contributions list (spec §4 Ch1): the platform; the faithful 3-model × 2-market replication; the composed quantitative MLOps evaluation (ML Test Score + reproducibility + DORA); the practice-by-practice maturity assessment.
- One-line-per-chapter outline; scope & non-goals paragraph.
- Delete the relocation marker comment.

- [ ] **Step 3: Build, content-check, commit**

Run: `cd Report && latexmk -pdf -interaction=nonstopmode main.tex`
Expected: compiles; `\ref` to other chapters resolve (stubs exist). Then:
```bash
cd /home/vietnh/Projects/algo-repo
git add Report/chapters/introduction.tex
git commit -m "feat(report): Ch1 Introduction

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Write Background & Related Work (Ch 2)

Follow **spec §4 → "Ch 2"** (subsections 2.1–2.5). This chapter is the single home for the literature landscape.

**Files:**
- Modify: `Report/chapters/background.tex`
- Modify: `Report/references.bib`

- [ ] **Step 1: Add the missing bibliography entries**

Append to `references.bib`:
```bibtex
@article{weron2014,
  author  = {Weron, Rafa{\l}},
  title   = {Electricity price forecasting: A review of the state-of-the-art with a look into the future},
  journal = {International Journal of Forecasting},
  volume  = {30},
  number  = {4},
  pages   = {1030--1081},
  year    = {2014},
  doi     = {10.1016/j.ijforecast.2014.08.008}
}

@article{nowotarski2018,
  author  = {Nowotarski, Jakub and Weron, Rafa{\l}},
  title   = {Recent advances in electricity price forecasting: A review of probabilistic forecasting},
  journal = {Renewable and Sustainable Energy Reviews},
  volume  = {81},
  pages   = {1548--1568},
  year    = {2018},
  doi     = {10.1016/j.rser.2017.05.234}
}
```
(Optional adoption-gap statistic: if §2.4 cites the "organisations have not deployed a model" figure, locate the source PDF under `researh_material/` and add a verified entry; otherwise omit the statistic rather than guess a citation.)

- [ ] **Step 2: Write §2.1–§2.3 (EPF landscape)**

- 2.1 DA market mechanics + statistical properties (`weron2014`, `nowotarski2018`).
- 2.2 The Lago et al. (2021) benchmark: LEAR & DNN, epftoolbox, recalibration methodology, rMAE + DM/GW, asinh VST (`lago2021`, `uniejewski2018vst`, `diebold1995dm`, `giacomini2006gw`).
- 2.3 Transformer EPF (`llorente2025transformer`).

- [ ] **Step 3: Write §2.4–§2.5 (MLOps + evaluation methodology)**

- 2.4 MLOps definition; Zarour's nine practices + maturity models; Google 3-level model; domain precedent (`zarour2025`, `google_mlops_maturity`, `subramanya2022devops2mlops`).
- 2.5 Evaluation methodology: single-case study (`runeson2009casestudy`); ML Test Score (`breck2017mltestscore`); reproducibility + ACM badging (`gundersen2018reproducibility`); DORA (`forsgren2018accelerate`); cost-aware retraining (`mahadevan2024costaware`).

- [ ] **Step 4: Build, content-check, commit**

Run: `cd Report && latexmk -pdf -interaction=nonstopmode main.tex`
Expected: compiles; bibliography resolves the two new keys (no `[?]` citations for `weron2014`/`nowotarski2018`).
```bash
cd /home/vietnh/Projects/algo-repo
git add Report/chapters/background.tex Report/references.bib
git commit -m "feat(report): Ch2 Background and Related Work

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Expand the Evaluation Framework (Ch 5)

Expand `evaluation_framework_draft.tex` bullets → prose per **spec §4 → "Ch 5"**. Keep all existing tables (`tab:ef-test-types`, `tab:ef-inventory`, `tab:ef-mapping`, `tab:ef-mlts-rules`, `tab:ef-mlts-sections`, `tab:ef-repro-tests`, `tab:ef-dora-scope`, `tab:ef-maturity-candidates`, `tab:ef-validity`, `tab:ef-non-claims`).

**Files:**
- Modify: `Report/chapters/evaluation_framework_draft.tex`

- [ ] **Step 1: Expand §Approach through §Reproducibility tests into prose**

Convert the bullets under Approach, Test inventory, Why-these-five, ML Test Score, Reproducibility tests into 2–4 sentence paragraphs each. Keep the citations already in the scaffold.

- [ ] **Step 2: Expand §DORA through §What-is-not-tested into prose**

Convert Delivery throughput, Drift monitoring counts, Maturity-model positioning, Threats-to-validity preview, and What-is-not-tested bullets into prose.

- [ ] **Step 3: Add the modelling-evaluation bridge paragraph**

After §Approach, add one paragraph stating that this chapter frames the *system-side* evaluation, and that the *modelling-side* protocol (MAE/RMSE/sMAPE/rMAE + DM/GW) is defined in Ch~\ref{ch:methods-models} §Evaluation protocol — so the reader sees both threads' evaluation are accounted for.

- [ ] **Step 4: Build, content-check, commit**

Run: `cd Report && latexmk -pdf -interaction=nonstopmode main.tex`
Expected: compiles. Checklist: no bullet lists remain except where a list is genuinely the right form; bridge paragraph present.
```bash
cd /home/vietnh/Projects/algo-repo
git add Report/chapters/evaluation_framework_draft.tex
git commit -m "feat(report): Ch5 Evaluation Framework — scaffold to prose + modelling bridge

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Expand Results — System Evaluation (Ch 7) and integrate relocated content

Merge the relocated quant-eval + maturity table (parked by Task 1) with the existing `results_system_draft.tex` scaffold into one coherent results chapter per **spec §4 → "Ch 7"**. Numbers are real and already known (from `Report/metrics/quantitative_results.md` and `ml_test_score.md`).

**Files:**
- Modify: `Report/chapters/results_system_draft.tex`

- [ ] **Step 1: Reconcile duplicated tables**

The scaffold and the relocated block both contain an ML Test Score table (`tab:res-mlts` and `tab:ml-test-score`). Keep one (`tab:res-mlts`), delete the duplicate, and update any `\ref` to the survivor. Same for the reproducibility tables (`tab:res-repro-coverage`, `tab:res-repro-rerun`) — keep the scaffold's, fold in any prose from the relocated block.

- [ ] **Step 2: Write the results prose with the real numbers**

Per section, embed the verified values:
- ML Test Score: headline **2.5**; sections Data 2.5 / Model 3.0 / Infra 4.0 / Monitoring 4.0; binding section = Data; mention the optional S1-2/S1-4 rescore note.
- Reproducibility: provenance triple **66.7% (10/15)**; shortfall entirely `git_sha` (5 pre-CD runs); re-run max abs diff **7×10⁻⁶ EUR/MWh** on `dk1_lear` 2026-03-22; ACM Available/Functional/Reusable, not Reproduced.
- DORA: **19** deployments, **1.48/week**, lead time **0.1 min** (p50 and p95); change-failure-rate / MTTR / tier deliberately not reported.
- Drift as monitoring: **35/35** reports flagged; reframing via `mahadevan2024costaware`; calibration limitation noted.

- [ ] **Step 3: Place the maturity table and finish threats/gaps**

Position the relocated `tab:maturity` under the Maturity-placement section; write the threats-to-validity (full) and system-side known-gaps prose (the latter informed by the gaps relocated to `discussion.tex` — cross-reference, do not duplicate). Remove all Task 1 relocation marker comments.

- [ ] **Step 4: Populate Appendix B (ML Test Score worksheet)**

In `appendices.tex`, under the `\chapter{ML Test Score Worksheet}\label{app:mlts-worksheet}` stub, reproduce the 28-item worksheet from `Report/metrics/ml_test_score.md` as four `tabularx` tables (one per section: Data / Model development / ML infrastructure / Monitoring) with columns `# | Test | Score | Evidence`, plus a closing line giving the per-section sums (2.5 / 3.0 / 4.0 / 4.0) and `\textbf{ML Test Score} = \min = 2.5`. Cite `breck2017mltestscore` in the lead sentence and cross-reference it from the Ch 7 ML Test Score section (`\ref{app:mlts-worksheet}`).

- [ ] **Step 5: Build, content-check, commit**

Run: `cd Report && latexmk -pdf -interaction=nonstopmode main.tex`
Expected: compiles; no duplicate-label errors (LaTeX errors on duplicate `\label` — fix any that surface here).
```bash
cd /home/vietnh/Projects/algo-repo
git add Report/chapters/results_system_draft.tex Report/chapters/appendices.tex
git commit -m "feat(report): Ch7 Results (system) + Appendix B worksheet

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Write the Discussion (Ch 8)

Follow **spec §4 → "Ch 8"**. Integrate the gaps relocated into `discussion.tex` by Task 1. RQ1's numeric answer is filled in Task 11 (data-blocked); write its structure now with a clearly-marked slot.

**Files:**
- Modify: `Report/chapters/discussion.tex`

- [ ] **Step 1: Write RQ2, RQ3, thread-tying, and limitations**

- RQ2 (engineering trade-offs): synthesise from Ch 4 — full-refit-over-warm-start, co-located train+predict flow, single-host blast radius, ClickHouse-as-everything, base64 artifact ceiling.
- RQ3 (critical practices & limits): from the maturity table + ML Test Score binding section (Data, 2.5); P9 minimal; name where the single-host MVP reaches its limit.
- Thread-tying paragraph: resample-to-hourly for comparability; cheap daily refit makes drift-triggered retraining redundant (the cost-aware argument, `mahadevan2024costaware`); the platform makes the replication reproducible.
- Consolidated limitations (absorb the relocated known-gaps paragraphs; then delete the relocation marker).

- [ ] **Step 2: Write the RQ1 slot (structure only)**

Add §8.1 "RQ1 — model comparison" with the framing sentences and an explicit slot:
```latex
% NUMBERS PENDING THE SIX --track RUNS (filled in Task 11).
The comparison of LEAR, DNN, and Transformer on DK1 and DE is reported in
Chapter~\ref{ch:results-models}; \textbf{[pending: headline ranking and rMAE summary]}.
```

- [ ] **Step 3: Build, content-check, commit**

Run: `cd Report && latexmk -pdf -interaction=nonstopmode main.tex`
```bash
cd /home/vietnh/Projects/algo-repo
git add Report/chapters/discussion.tex
git commit -m "feat(report): Ch8 Discussion (RQ2/RQ3 + thread-tying; RQ1 slot pending data)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Write the Conclusion (Ch 9)

Follow **spec §4 → "Ch 9"**. Rewrite the relocated system-chapter conclusion (Task 1 Step 4) into a thesis-wide conclusion.

**Files:**
- Modify: `Report/chapters/conclusion.tex`

- [ ] **Step 1: Write contributions recap + future work**

- Recap: 8/9 Zarour practices realised, P9 minimal; the platform ingests live data, refits daily, monitors, and keeps a full audit trail; forecasting headline left as a one-line slot `\textbf{[pending]}` cross-referencing Ch 6.
- Future work (spec §9 / Ch 9): 1456-day window & LARS+AIC λ; probabilistic forecasting (pinball/CRPS); Transformer per-market tuning; epftoolbox side-by-side on 2016–18 data; DNN/Transformer reproducibility under controlled seeds; Data-tests investment; drift-detector calibration; multi-area expansion; calibration-window sensitivity ablation; MLflow/K8s/cloud-store adoption triggers.
- Delete the relocation marker.

- [ ] **Step 2: Build, content-check, commit**

Run: `cd Report && latexmk -pdf -interaction=nonstopmode main.tex`
```bash
cd /home/vietnh/Projects/algo-repo
git add Report/chapters/conclusion.tex
git commit -m "feat(report): Ch9 Conclusion and Future Work

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Write the Results — Forecasting skeleton (Ch 6)

Build the chapter structure, table skeletons, and figure includes per **spec §4 → "Ch 6"**, with every numeric cell as an explicit pending marker. Numbers/figures are filled in Task 11. Computation-cost values DO exist now (`Report/metrics/run_timings.md`) — fill those.

**Files:**
- Modify: `Report/chapters/results_models_draft.tex`

- [ ] **Step 1: Write section headings and prose framing**

Sections 6.1 headline accuracy, 6.2 significance, 6.3 vs published benchmarks, 6.4 computation cost, 6.5 qualitative figures, 6.6 forecasting discussion. Write the framing sentences that do not depend on results.

- [ ] **Step 2: Add the headline accuracy table skeleton (per market)**

For DK1 and DE, a `tabularx` with rows {LEAR, DNN, Transformer, Weekly-naive} and columns {MAE, RMSE, sMAPE, rMAE}; every cell `\textbf{[pending]}`. Caption notes the source: `Report/metrics/model_comparison.md`.

- [ ] **Step 3: Add the GW p-value matrix skeleton + figure includes**

A 3×3 (+naive) matrix table per market with `[pending]` cells, and `\includegraphics` stubs for `figures/results_models/gw_heatmap_dk1`, `gw_heatmap_de`, `forecast_week_dk1`, `forecast_week_de`, `mae_by_hour_dk1`, `mae_by_hour_de` wrapped so a missing file does not break the build — guard each with `\IfFileExists{<path>.pdf}{\includegraphics...}{\fbox{Figure pending experiment runs}}`.

- [ ] **Step 4: Fill the computation-cost table (real numbers now)**

From `run_timings.md`, the Lago-Table-4 analogue (wall-clock / seconds per backtest): dk1_lear 9082 s; dk1_dnn 6 s (×4 ensemble); de_dnn 4 s; dk1_transformer 11 s; de_transformer 9 s; de_lear pending. Add the note about LEAR's per-period fits vs MIMO GPU models.

- [ ] **Step 5: Build, content-check, commit**

Run: `cd Report && latexmk -pdf -interaction=nonstopmode main.tex`
Expected: compiles; the `\IfFileExists` guards render "Figure pending" boxes, not errors.
```bash
cd /home/vietnh/Projects/algo-repo
git add Report/chapters/results_models_draft.tex
git commit -m "feat(report): Ch6 Results (forecasting) skeleton + computation-cost table

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Front matter + forecasting-figure script

**Files:**
- Modify: `Report/chapters/frontmatter.tex`
- Create: `scripts/report/plot_forecast_figures.py`

- [ ] **Step 1: Write the front matter**

In `frontmatter.tex`: a `titlepage` (title, author = repo git user, institution/date), then an `\begin{abstract}`-style section (the `report` class has `\abstract`; or a centered "Abstract" heading) with the dual-contribution summary and a `\textbf{[pending headline result]}` slot, then an acronyms `description` list (EPF, MLOps, LEAR, DNN, DM, GW, ENTSO-E, rMAE, VST, TPE).

- [ ] **Step 2: Verify matplotlib is available**

Run: `cd /home/vietnh/Projects/algo-repo && uv run python -c "import matplotlib; print(matplotlib.__version__)"`
Expected: a version string. If absent, the figure script step records the dependency to add; do not block the rest.

- [ ] **Step 3: Write the figure-generation script**

`scripts/report/plot_forecast_figures.py`: a CLI that reads the per-run forecast/actual CSVs (the `--track` outputs / `results/`) and `Report/metrics/model_comparison.md`, and writes three PDFs per market into `Report/figures/results_models/`: GW p-value heatmap, a sample forecast week (predicted vs actual), and a per-hour MAE profile. Mirror the structure of `scripts/report/extract_model_comparison.py` (argument parsing, path conventions, the `__init__.py` package layout). Guard the `__main__` so importing it is side-effect-free. It is runnable now but produces final figures only once the runs exist.

- [ ] **Step 4: Build, smoke-run the script's `--help`, commit**

Run: `cd Report && latexmk -pdf -interaction=nonstopmode main.tex` (front matter renders)
Run: `cd /home/vietnh/Projects/algo-repo && uv run python -m scripts.report.plot_forecast_figures --help`
Expected: usage prints, no import error.
```bash
cd /home/vietnh/Projects/algo-repo
git add Report/chapters/frontmatter.tex scripts/report/plot_forecast_figures.py
git commit -m "feat(report): front matter + forecasting-figure generation script

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Fill data-blocked slots (BLOCKED ON THE SIX `--track` RUNS)

**Do not start until** all six backtests have completed with `--track` and `scripts/report/extract_model_comparison.py` has produced `Report/metrics/model_comparison.md`. Verify first:

- [ ] **Step 1: Confirm the inputs exist**

Run: `ls -la /home/vietnh/Projects/algo-repo/Report/metrics/model_comparison.md`
Expected: present and recently modified. If absent, stop — the runs are not finished.

- [ ] **Step 2: Render the forecasting figures**

Run: `cd /home/vietnh/Projects/algo-repo && uv run python -m scripts.report.plot_forecast_figures`
Expected: six PDFs in `Report/figures/results_models/`.

- [ ] **Step 3: Fill Ch 6 numeric cells**

Replace every `\textbf{[pending]}` in `results_models_draft.tex` with the values from `model_comparison.md` (headline accuracy, GW matrices), and add the vs-published-benchmark table (Lago Table 3 / Llorente Table 5 rows + the different-period caveat) and the §6.6 discussion.

- [ ] **Step 4: Fill the cross-cutting slots**

Replace the `\textbf{[pending]}` slots in `discussion.tex` §8.1, `conclusion.tex`, and `frontmatter.tex` abstract with the headline ranking/rMAE.

- [ ] **Step 5: Build, content-check, commit**

Run: `cd Report && latexmk -pdf -interaction=nonstopmode main.tex`
Expected: no remaining `[pending]` markers (`grep -rn "\[pending" Report/chapters` returns nothing); figures render.
```bash
cd /home/vietnh/Projects/algo-repo
git add Report/chapters/results_models_draft.tex Report/chapters/discussion.tex Report/chapters/conclusion.tex Report/chapters/frontmatter.tex Report/figures/results_models/
git commit -m "feat(report): fill forecasting results, figures, and headline slots

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: Final integration — references, page count, trim-pass triage

**Files:**
- Modify: any chapter (trim only)

- [ ] **Step 1: Full clean build with bibliography**

Run: `cd Report && latexmk -C && latexmk -pdf -interaction=nonstopmode main.tex`
Expected: `main.pdf`; then check the log for unresolved references and undefined citations:
Run: `grep -E "undefined|multiply defined|There were undefined references" Report/main.log || echo "clean"`
Expected: `clean` (or only the known data-pending refs if Task 11 not yet run).

- [ ] **Step 2: Page count + trim triage**

Run: `pdfinfo Report/main.pdf | grep Pages`
If body exceeds ~48pp, apply the spec §8 trim order: compress the lighter Zarour practices (P1, P5) in Ch 4, then de-duplicate any Ch 5 ↔ Ch 7 overlap. Do not cut Ch 3 or Ch 6. Re-build after trimming.

- [ ] **Step 3: Commit**

```bash
cd /home/vietnh/Projects/algo-repo
git add Report/chapters/ Report/main.tex
git commit -m "chore(report): final integration build + trim pass

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Notes on adaptation

This is a prose/LaTeX assembly, so the usual test-first loop is replaced by **compile-and-content-check** after each writing unit: every task ends by building `main.tex` with `latexmk` (the analogue of "tests pass") and verifying the spec bullets are covered (the analogue of the assertion). Tasks 0–10 and 12 are writable now; **Task 11 is the only data-blocked task** and is gated on the six `--track` runs. The `[pending]` markers are the single sanctioned exception to "no placeholders" — they are deliberate, greppable slots whose fill instructions are fully specified in Task 11.
