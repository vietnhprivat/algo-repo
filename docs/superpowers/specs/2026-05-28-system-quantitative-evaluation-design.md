# System Quantitative Evaluation — Design Spec

> **Status:** design, awaiting implementation plan.
> **Supersedes:** the operational portions of `docs/superpowers/plans/2026-05-23-quantitative-system-metrics.md` (that plan over-claimed "90 days of operation" and reported indefensible metrics — see Cleanup below).

## Goal

Give the thesis results a defensible **quantitative** evaluation of the *system* (not the
forecasting models). The existing chapter rates the system qualitatively against Zarour's
nine MLOps practices; this adds measured numbers without claiming production history the
system does not have.

## Framing decisions (settled during brainstorming)

- **Two results parts.** Part 1 = forecasting-model accuracy (MAE/RMSE/sMAPE/rMAE) — a
  separate concern, **out of scope here**, produced by a backtest over the leakage-free
  out-of-sample window (`2026-01-01 → 2026-03-22`, the window where all three model
  families are simultaneously past their tuning data). Part 2 = **system evaluation** —
  this spec.
- **No simulation.** We do **not** fabricate or replay a year/90 days of operation. Every
  Part-2 number comes from the source code, the git/CI history, or a short targeted
  experiment. The original plan's "the system ran for 90 days" framing is dropped.
- **Methodology: single-case study**, cited to Runeson & Höst (2009). One sentence carries
  the honesty boundary: *the system is evaluated from its source code, git/CI history, and
  short experiments; measurements are indicative over the study window, not long-run
  production claims.* No Design Science Research / FEDS framing (not used elsewhere in the
  thesis).
- **Scope is deliberately trimmed.** Three measured instruments + one discussion + cleanup.
  Cut from earlier drafts: a full ISO/IEC 25010 sweep, a second practice catalogue
  (SE4ML/Kreuzberger) on top of Zarour, fault-injection experiments, and the passive
  availability/CFR tables.

## What the chapter contains (trimmed)

The chapter is **§5.2 Quantitative evaluation** (rewritten), structured as:

1. **Evaluation methodology** — one short paragraph: single-case study (Runeson & Höst
   2009); data sources = code, git, CI, experiment tracker; explicit statement that numbers
   are indicative over the study window.

2. **Instrument 1 — ML Test Score** *(headline result)*
   - Source: Breck et al. (2017), *The ML Test Score* (IEEE Big Data). *(Optional second
     cite if wanted: Sculley et al. 2015, Hidden Technical Debt in ML Systems, as the
     conceptual basis — not in the gathered seven.)*
   - Method: self-audit each of the 28 tests across the four sections (Data, Model,
     Infrastructure, Monitoring), scoring **0 / 0.5 / 1**. Final score = **min of the four
     section sums**; report the scalar plus a per-section table and per-item evidence.
   - Output: a worksheet (`Report/metrics/ml_test_score.md`) where items are scored with
     one-line evidence, transcribed into a LaTeX table.
   - Honesty: the min-of-four rule will expose the weakest section (likely Monitoring or
     Model) — report it as a gap, not hide it. Drift detection scores here as a
     *Monitoring* capability.
   - No new code; it is an audit of the existing system.

3. **Instrument 2 — Reproducibility** *(strongest honest result)*
   - Source: Gundersen & Kjensmo (2018), *State of the Art: Reproducibility in AI* (AAAI).
     *(The ACM Artifact Review and Badging policy is a standard, not one of the gathered
     seven — cite only if you want the badge mapping.)*
   - Two outputs:
     - **A provenance-coverage number**: % of live `experiment_runs` carrying the full
       triple (`git_sha`, data window, `model_artifact_id`) — already computed by
       `extract_metrics.py`.
     - **A live re-run demonstration**: pick one logged run, reload *only* its
       `model_artifact_id` + `git_sha` + (`data_start_utc`, `data_end_utc`), re-run the
       forecast, and report the max absolute difference vs. the stored prediction. This is
       a worked instance of ML Test Score "Model test 7" and the chapter's centrepiece
       reproducibility evidence.
   - Map the artefact to ACM badges (Available / Functional / Reusable claimable by
     self-review; "Reproduced" needs an independent reviewer — do not claim).

4. **Instrument 3 — DORA delivery throughput** *(external grounding)*
   - Source: Forsgren, Humble & Kim (2018), *Accelerate*.
   - Report **only the two throughput metrics**: Deployment Frequency and Lead Time for
     Changes, mined from git + GitHub Actions `cd_deploy.yml` history.
   - **Do not** report Change Failure Rate or MTTR (need an incident corpus the days-window
     does not provide), and **do not** claim a DORA tier/Elite-High-Med-Low placement
     (thresholds are re-clustered yearly; unsafe on a short window). State this exclusion
     explicitly as a methodological choice.

5. **Drift detection as monitoring, not a retrain trigger** *(discussion subsection)*
   - Source: Mahadevan & Mathioudakis (2024), *Cost-aware retraining for machine learning*
     (Knowledge-Based Systems) — empirically supports that fewer retrain decisions lower
     total cost.
   - Argument: the system fully refits every model daily on a rolling window at seconds of
     cost, so drift-*triggered* retraining adds no model-freshness benefit over the
     scheduled daily refit; its residual value is monitoring/alerting. State the boundary
     condition explicitly: **this holds only while retraining stays cheap** — it would flip
     for expensive transformer retrains over multi-year windows.
   - Note honestly that the current detector fired `drift_detected = 1` on 25/25 reports
     (100% rate ⇒ uninformative as tuned) and flag recalibration as future work.
   - *(Optional, if desired later: engage the opposing view that detection is a
     prerequisite for adaptation. Not required for the trimmed scope.)*

6. **Maturity (existing, kept)** — the current Zarour nine-practice table stays. Optionally
   add the Google MLOps maturity-level column already drafted in the 2026-05-23 plan
   (one ordinal column, `\cite{google_mlops_maturity}`).

7. **Domain precedent** — cite Subramanya, Sierla & Vyatkin (2022), *From DevOps to MLOps:
   ... Electricity Market Forecasting* (Applied Sciences) as evidence that this is how
   MLOps forecasting systems are evaluated in the literature.

## Cleanup (removals from the current §5.2)

The current chapter (lines ~703–868) over-claims. Remove:

- The **System availability** table (Prometheus `up{}` over "90 days") — Prometheus has
  data only since 2026-05-24; not honestly a 90-day/1-year figure. Delete the subsection.
- The **Change failure rate (30%)** figure and any DORA-tier language in the Delivery
  cadence subsection — restructure that subsection to throughput-only per Instrument 3.
- Any prose asserting "the system's behaviour over the last ninety days of operation" —
  replace with the single-case-study framing.

## Files touched

- `Report/chapters/system_implementation.tex` — rewrite §5.2 per the structure above;
  delete availability + CFR tables.
- `Report/references.bib` — add bib entries for the seven sources (six new + the
  already-present Zarour). New keys: `runeson2009casestudy`, `breck2017mltestscore`,
  `gundersen2018reproducibility`, `forsgren2018accelerate`, `mahadevan2024costaware`,
  `subramanya2022devops2mlops`. (Optional, only if cited: `sculley2015techdebt`,
  `acm2020badging`.)
- `scripts/report/extract_metrics.py` — trim: DORA collector → throughput only (drop CFR
  and any MTTR); remove the availability/Prometheus collector; keep operational
  (training-duration, reconciliation) and reproducibility-coverage collectors (they feed
  Instruments 1–3 as supporting numbers).
- `scripts/report/reproduce_run.py` *(new)* — the reproducibility re-run demo: load a run's
  artifact + git_sha + data window, re-run, print max abs diff vs. stored prediction.
- `Report/metrics/ml_test_score.md` *(new)* — the 28-item scoring worksheet.
- `Report/metrics/quantitative_results.md` — regenerated by the trimmed script.

## Sources (one per topic, gathered and confirmed by the author)

| Topic | Citation |
|---|---|
| Case-study methodology | Runeson & Höst (2009), *Empirical Software Engineering* 14(2):131–164 |
| ML Test Score | Breck, Cai, Nielsen, Salib & Sculley (2017), IEEE Big Data, pp. 1123–1132 |
| Reproducibility | Gundersen & Kjensmo (2018), AAAI |
| DORA delivery | Forsgren, Humble & Kim (2018), *Accelerate*, IT Revolution |
| Drift cost/monitoring | Mahadevan & Mathioudakis (2024), *Knowledge-Based Systems* 293:111610 |
| Domain precedent | Subramanya, Sierla & Vyatkin (2022), *Applied Sciences* 12(19):9851 |
| Maturity (existing) | Zarour et al. (2025), *Information & Software Technology* 183:107733 |

## Explicitly NOT claimed

- No long-horizon reliability/availability/MTTR.
- No DORA tier placement; no Change Failure Rate.
- No comparative superiority over other MLOps platforms (single case, no controlled
  experiment — analytic generalisation only).
- No model-accuracy numbers in this chapter (Part 1's concern).
- No simulated/replayed operational history.

## Risks / open items

- **ML Test Score subjectivity** — a self-administered 0/0.5/1 rubric. Mitigate by
  recording one-line evidence per item in the worksheet so scores are checkable.
- **Reproducibility demo determinism** — DNN/Transformer training has stochasticity
  (seeds, ensemble). The re-run may not be bit-identical; report max abs diff and discuss,
  or run the demo on the deterministic LEAR config first.
- **Small DORA sample** — few deploys in the window; report the raw throughput numbers and
  the window length, and decline tier placement.
