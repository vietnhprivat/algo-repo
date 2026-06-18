# Defense Preparation Plan

Critical review of `Report/main.md` for the bachelor's thesis defense. Written from the
handed-in report alone (first pass), then extended with a code-and-references deep dive
(see "Deep dive: verified findings" at the end).

---

## Where you're exposed: the honest TL;DR

The thesis is strong on protocol honesty (deviations table, common-day paired tests,
conservative self-scoring) and on the provenance/reproducibility chain. Its load-bearing
weaknesses, where a good examiner will spend most of the Q&A:

1. **RQ1 is budget-confounded by design.** The ranking inversion is attributed to the
   reduced tuning budget, which means the comparison cannot separate "Transformer is
   worse" from "my Transformer is worse."
2. **The model evaluated is not the model served.** Backtest = single-seed DNN;
   production = 4-seed ensemble. The headline "LEAR most accurate" rests on one seed draw.
3. **The production evidence base is thin.** 15 live runs total, and no live accuracy
   numbers appear anywhere in the thesis, despite "production platform" being its identity.
4. **"Statistically tied" overstates what p=0.16 shows.** Non-rejection is not equivalence.
5. **The drift detector is admitted to be uninformative (49/49), yet P8 is "Realised, Level 2."**
6. **The abstract/conclusion say "complete audit trail from every forecast" while Ch7
   reports 66.7% coverage.** A quotable internal contradiction.

None of these is fatal; for most, the thesis itself contains the right defense. The job is
to deliver those defenses fluently instead of being walked into them.

---

# REPORT-ONLY DEFENSE (read this first)

**New threat model (2026-06-09):** the examiner reads the *report*, not the repo or the
code. That changes everything. Two consequences:

1. **What can hurt you is now what a careful reader finds in the text itself** — internal
   contradictions, claims stronger than the report's own tables support, and concepts the
   report names that you must be able to explain. Code-level defects they cannot see are
   no longer "they'll catch you" risks (they drop in priority below), but you still must
   not *assert* something you know is false.
2. **Weight by the examiner's expertise.** Finn Årup Nielsen is a DTU Compute ML/stats and
   reproducibility/open-science person, not an energy-markets specialist. So the
   **statistics, ML-methodology, and reproducibility** questions are far more likely than
   EPF-domain ones (market microstructure, tradability of hourly prices). Prepare the
   stats gauntlet hardest. The "hourly mean is not a tradable product" critique is now
   *low* likelihood; the "p=0.16 is not a tie" critique is *high*.

Ranked by likelihood times damage for a report-reading stats examiner:

### R1. The "statistical tie" — power and multiplicity (TOP PRIORITY)
The central RQ1 result is "LEAR and the DNN are statistically tied / indistinguishable"
(abstract, §5.2, §7.1). I grepped the whole report: it contains **no discussion of
statistical power, no equivalence test, and no multiple-comparison correction** anywhere.
A stats examiner will go straight here.

- **Non-rejection is not equality.** Lead with the report's *careful* phrasing, not its
  loose one. The report says both "statistically tied" (strong, lines 68/1550/1764) and
  "neither model can be shown to be the more accurate" (correct, line 1494). Use the
  second. "On this window I cannot reject equal accuracy; that is indistinguishability,
  not proven equivalence."
- **Power.** n is ~187 daily loss differentials (DK1) / 176 (DE). The gap is ~3% relative
  (rMAE 0.469 vs 0.482). With daily L1 differentials and a HAC standard error, power to
  detect a gap that small is low — which is *why* it is reported as a tie rather than a
  LEAR win. If pushed for a number, lean on the seed-variance result (R5): the DNN's own
  run-to-run spread is comparable to the LEAR–DNN gap, so the gap sits inside noise.
- **Equivalence.** Say this unprompted: "To *claim* equality I would run a TOST /
  equivalence test against a pre-set margin; I did not, so I claim indistinguishability,
  not equivalence." That one sentence reads as mastery.
- **Multiplicity.** The GW matrix is all ordered pairs (12 per market, no Bonferroni /
  Holm). Defense: follows Lago's pairwise-heatmap protocol; the load-bearing results
  (Transformer loses at $p\le0.012$, naive at $p\approx0$) survive any correction by
  orders of magnitude; the only borderline cell is LEAR–DNN and it is a *non-rejection*,
  which correction only pushes further from significance. No conclusion rests on an
  uncorrected marginal p-value.

### R2. DM vs GW — what §3.5 actually describes (SHARP, report-readable)
§3.5 describes computing $\bar{d}/\hat{\sigma}$ with a Newey–West HAC standard error on the
daily loss differential. That *is* the multivariate Diebold–Mariano statistic. Calling it
"Giacomini–White" is defensible only one way, and you must know it cold.

- **The answer:** "The GW test (Lago eq. 14) regresses the loss differential on an
  instrument set $X_{d-1}$ = a constant *and lags of the differential*. With $X$ reduced
  to a constant — Lago's eq. 15 — it coincides with the multivariate DM test, which is
  what I compute. I followed Lago's naming and Fig. 5 protocol. The full conditional GW
  adds the lagged differentials as instruments; I did not exercise the conditioning."
- Be able to **write** $\Delta^{A,B}_d = \phi' X_{d-1} + \epsilon_d$ and say what $X$ holds.
- Know *why* GW exists: it tests **conditional** predictive ability and accounts for
  parameter-estimation uncertainty under rolling-window recalibration — exactly your
  setup — which is its advantage over DM. Concede you did not use the conditioning. This
  turns a mislabel into a mastery moment.

### R3. "The inversion is attributable to the tuning budget" — stated, not tested
The conclusion (line 1934) says the ranking inversion "is attributable to the deep models'
reduced tuning budget." You did **not** test this (no DNN at 1500 trials, no per-market
Transformer). Out loud, downgrade "attributable to" to "most consistent with."

- Support for the hypothesis: (a) LEAR re-selects $\lambda$ by cross-validation every day,
  so it sits near its own ceiling with no tuning headroom; (b) the documented 30-vs-1500
  trial gap and the untuned, regime-shifted Transformer; (c) Lago's *own* finding that the
  LEAR–DNN gap is frequently insignificant.
- The confirmatory experiment (run `epftoolbox` on the 2016–2018 data + full tuning to
  separate replication error from regime change) is named future work. Do **not** defend
  "attributable" as proven; frame it as a reasoned, falsifiable hypothesis.

### R4. "Complete audit trail from every forecast" vs 66.7% (clean contradiction)
§1.3, §7.4 ("any forecast can be reconstructed"), and Chapter 8 ("complete audit trail from
every forecast") vs §6.2 Table 6.2 (66.7%, 10/15). The examiner can find this unaided.

- Defense: the mechanism is complete for every continuously-deployed run (100% from the
  first CD run); five early runs predate the `GIT_SHA`-baking step and are *reported* as
  misses. The word "complete ... from every forecast" in the conclusion overreaches; it
  should read "from every continuously-deployed forecast." Concede the wording in one
  sentence, then pivot: measuring and *publishing* your own 66.7% is the methodological
  point, not a flaw to hide.

### R5. Single-seed backtest (report admits it, §3.3.2 + §7.5)
The report says the DNN backtest metrics "carry the seed variance of one draw." Examiner:
"could a different seed flip the LEAR–DNN order?"

- Defense (no experiment needed): production serves a 4-seed ensemble (more stable); the
  backtest is single-seed, which is *conservative* for the tie claim, because seed
  averaging would only tighten the DNN, not widen the LEAR–DNN gap. The gap itself is
  small, about 0.4 EUR/MWh in MAE and ~3% relative — exactly the margin single-MLP seed
  noise can cover. That is the point, not a weakness, the numerical order is not robust,
  which *is* the indistinguishability the GW test reports. If you want a number for the
  defense you can run three seeds in ~10 minutes, but the argument stands without it.

### R6. Self-administered ML Test Score + reproducibility taxonomy (examiner's wheelhouse)
- **MLTS is self-scored.** Point to the per-item Appendix evidence (each line checkable),
  the recomputable script, and the conservative choices (N/A scored 0; features-beneficial
  left at 0 with the raise-to-0.5 argument documented). So 2.5 is a *lower bound*, not a
  flattering self-grade.
- **What kind of reproducibility is the $7\times10^{-6}$ re-run?** The *weakest*
  Gundersen–Kjensmo form: same code, same data, re-executed — repeatability, not
  replicability. It works only for deterministic LEAR; the stochastic DNN/Transformer
  re-run is future work. Say this **before** they corner you; naming the limitation of
  your own headline reproducibility number is exactly what a reproducibility examiner
  rewards.

### R7. "Faithful replication" vs the deviations (report defends this well)
Hold the line the report already sets: faithful **in specification** (model classes, the
Eq. 3 feature set, asinh, rolling recalibration, metrics, GW protocol), bounded **in
budget**, every departure in Table 3.4. Never claim "faithful" without the "in
specification" qualifier.

### R8. Drift 49/49 vs P8 "Realised, Level 2" (report pre-empts it)
§6.3 calls the 49/49 rate "uninformatively high," and §6.4 marks P8 Realised. Reconcile:
P8 is realised as a **pipeline** (detect, store, alert, audit end-to-end); the
**calibration** of the one detector is deficient, and the report says so. Have the fix
ready: seasonally-matched reference window, test forecast *residuals* not raw prices,
require drift to persist over k days, raise the drifted-share threshold.

### R9. "Daylight-saving days are dropped" (Chapter 5 results intro and §3.5) — minor factual slip
The pipeline runs entirely in UTC (so DST creates no missing hours), and the spring-forward
day is present in the data. The dropped days are **data gaps plus lag/sequence warmup**, not
DST. If asked "why drop DST days," do **not** invent a DST mechanism — say "those are data
gaps and lag warmup; the pipeline is UTC, so DST itself drops nothing; that wording is
imprecise." Small, but a Python-literate examiner may know UTC has no DST gaps.

### R10. Concept quick-hits the examiner may spot-check (one-liners)
- **asinh vs log:** asinh is defined for negative prices (which occur under high
  renewables); log is not.
- **rMAE vs MAE as headline:** rMAE normalises by the same-market naive, so it compares
  across periods/markets; absolute MAE does not (different price regimes).
- **MIMO vs per-period:** LEAR fits one Lasso per delivery period (period-independent);
  the DNN/Transformer map the feature vector to all periods in one pass (shared
  representation).
- **Why Google maturity model (not the other four):** three levels match a single-host
  MVP; its top level is plausibly attainable where Microsoft L4 needs multi-environment
  claims the platform does not make; most-cited in Zarour.
- **DNN trains on MAE yet wins on RMSE:** training loss is in asinh space, metrics in price
  space (asinh compresses the spikes RMSE punishes); the multi-window LEAR ensemble dampens
  mean error while the single-window DNN handles extremes differently. "I can't fully
  decompose it, here are the mechanisms" is an acceptable bachelor-level answer.
- **Why 90-day reference / 7-day current for drift:** recent week vs a quarter of context;
  also the over-flagging cause (overpowered, ~2160 vs ~168 samples) — own it.

### R11. Citation readiness (one sentence + why-cited; methodology papers matter most here)
Be able to give one line on each, weighted to the ones a stats/reproducibility examiner
probes: **Lago 2021** (the benchmark anchor: LEAR/DNN, rMAE, GW, asinh, recalibration),
**Llorente & Portela 2025** (the encoder-only Transformer; note their DNN was *not*
recalibrated, see RQ1 ammunition), **Zarour 2025** (the nine practices + maturity-model
survey), **Breck 2017** (ML Test Score rubric), **Google maturity model**, **Runeson &
Höst** (single-case study method, analytic not statistical generalisation), **Gundersen &
Kjensmo** (reproducibility taxonomy), **Mahadevan & Mathioudakis** (cost-aware retraining
— why drift need not trigger retraining), **Diebold–Mariano / Giacomini–White** (see R2),
**Uniejewski 2018** (asinh VST), **Subramanya 2022** (the DevOps-to-MLOps EPF precedent;
your delta is replicated benchmark models + significance tests + quantitative maturity).

### R12. Prose slips to know (so a quoted sentence does not rattle you)
Real typos in the submitted text: "compliment" (should be complement, §1.4 line 271),
"six services that runs" (§4.2.1 line 865), "strutural" (line 1012), "expendsive" (line
1090), "and- enormalise" (line-break mangle of renormalise, §7.1 line 1797), "the largest
outcome towards maturity" (line 1847). None fails a defense. If one is read aloud, "yes,
that is a typo for X" and move on — do not get flustered.

### Recalibration — earlier code findings that now DROP in priority
- **The 06:00 scheduled-forecast defect:** the examiner cannot see it. It is no longer a
  "they'll catch you" risk. **But integrity still binds:** do not present daily production
  forecasting as a flawless live fact. If asked about live operation, the honest line is
  "the recorded live runs are deploy-gate and manual runs, all information-set-correct;
  the always-on 06:00 path has a known data-availability limitation I would fix." The
  report's hard numbers (15 runs, 66.7%) are honest as written.
- **The positional weekly-naive shift:** pure code detail, examiner will not see it,
  effectively irrelevant now (and it moved rMAE only in the third decimal anyway).
- **The GW *implementation* detail:** folds into the conceptual R2 question above; you
  defend the concept, not the code.

---

## Tier 1: questions to assume will be asked

### Q1. "Faithful replication" vs. the reduced budget
> "You call this a *faithful* replication, then explain your own results by the unfaithful
> parts (30 vs ~1500 tuning trials, untuned Transformer, changed Transformer training
> regime). Which is it?"

*Likelihood: near-certain.* The trap is defending "faithful" absolutely. The line:
faithful **in specification** (model classes, Eq. 3 feature set, asinh transform, rolling
recalibration, metrics, GW protocol), explicitly **bounded in budget**, with every
departure tabled (Table 3.4) and the budget-sensitivity stated in the abstract itself.

Follow-up: "Then what does the Transformer's significant loss actually tell us?" Answer:
it is a finding about the **transfer cost** of these architectures. The DNN survives a 50×
tuning cut and a regime change; the Transformer does not survive losing per-market tuning
and its native train-once scheme. That is operationally relevant (robustness under
budget), not an architectural verdict, and §5.4/§7.1 already say so. Don't claim more.

### Q2. Single-seed backtest vs 4-seed production ensemble
> "Your backtest DNN is a single seed, but production serves a 4-seed ensemble. So you
> never evaluated the model you deploy, and your headline ranking rests on one draw."

*Likelihood: high; danger: high if unprepared.* Concede the eval/serving mismatch plainly
(it is stated in §3.3.2 but easy to miss). Then argue direction: seed-ensembling typically
improves or stabilises the DNN, so the single-seed backtest is **conservative for the tie
claim** (the DNN could only close the gap further), but yes, it makes "LEAR numerically
first" seed-fragile. The tie is the claim that survives significance testing anyway.
Before the defense: find any repeated-seed evidence (W&B runs, tuning trials) to quantify
seed variance. One number defuses this whole line.

### Q3. Non-rejection is not equivalence
> "p=0.16 means you failed to reject. That is not evidence of equality. What's the power
> of a GW test on 187 days, and why no equivalence test?"

*Likelihood: high with a stats-minded censor.* Concede the logic; "indistinguishable **on
this window**" is the defensible phrasing. Substance: the observed gap is small (rMAE
0.469 vs 0.482, ~3% relative), consistent across both markets, and consistent with Lago et
al.'s own finding that the LEAR-DNN gap is often insignificant; with ~190 daily
observations, power against a gap this small is limited, which is exactly why it is
reported as a tie rather than a LEAR win. On multiple comparisons (24 ordered pairs across
two markets, no correction): the benchmark's protocol is followed, and the key conclusions
(Transformer loses at p≤0.013, naive loses at p≈0) survive any reasonable correction; the
LEAR-DNN non-rejection is unaffected by multiplicity.

### Q4. DM vs GW, and what the code actually computes
> "Explain the difference between the Diebold-Mariano test and the Giacomini-White test,
> and tell me which one your code actually computes."

*Likelihood: medium-high; danger: high*, because §3.5 describes computing d̄/σ̂ with
Newey-West errors, which reads as a DM-style unconditional test. Must be able to state: DM
tests unconditional equal predictive accuracy of forecast *sequences*; GW tests
conditional predictive ability, uses an instrument set, and is explicitly valid under
rolling-window estimation schemes (why Lago et al. adopt it for this recalibration setup).
Know precisely what the implementation does, including the instruments, and whether it
matches epftoolbox. **Verified in the deep dive below.**

### Q5. The 31-week test window with no summer
> "Your test window is October to May. You never test a summer. For DE, a solar-dominated
> market, isn't that a serious external-validity problem?"

*Likelihood: high.* Own it: yes, June-September is untested, the papers recommend 1-2
years, and Limitations says so. Explain the arithmetic constraint cold: price history
starts 2022-03; the 1092-day calibration window plus the 42-week validation window
(2025-01-01 to 2025-10-23) consume everything before 2025-10-24. The window does contain
real stress (negative-price hours, the late-May volatile week, winter ramps). Forward
fix: the platform keeps ingesting, so the same frozen protocol can be re-run with a longer
window later. That is precisely what the platform is for.

### Q6. How long did production actually run?
> "Fifteen runs across six deployments is two or three days. And where are the live
> accuracy numbers?"

*Likelihood: high; danger: high because it attacks the thesis's identity.* Prepare the
exact operational timeline: when dk1_lear first deployed, when the DNN/Transformer
deployments were added, uptime, incidents. Have the live reconciled MAEs in your pocket
even though they're not in the report, and be ready to explain why they're not: the
evaluated claim is the *backtest* comparison; live operation is evidenced through the
system chapter (provenance, reconciliation, monitoring) rather than a second accuracy
study on a few days of data, which would be statistically meaningless. If the live numbers
are sane, volunteering them turns this attack into a win.

### Q7. Drift fires every day
> "The drift detector flagged 49 of 49 reports. A monitor that fires every day is the same
> as one that never fires. Why is P8 still 'Realised, Level 2'?"

*Likelihood: near-certain (the thesis flags it itself).* Two parts. Why 100% flagging: a
90-day reference vs a 7-day current window on a non-stationary, strongly seasonal price
series means the null of "same distribution" is essentially always false, and with ~2160
vs ~168 hourly samples the test is overpowered, so statistical drift ≠ actionable drift.
Why the label stands: P8 is realised as a **pipeline** (detection, storage, alerting,
audit trail end-to-end); the **calibration** of one detector is deficient and stated as
such (§6.3, Future Work). Recalibration plan, concretely: seasonally matched reference
windows, testing forecast *errors* or deseasonalised residuals instead of raw prices,
requiring drift persistence over k days, raising the drift-share threshold. For the
follow-up "why detect drift at all if you refit daily?": cheap scheduled retraining makes
a *retrain trigger* redundant (Mahadevan & Mathioudakis), but the *signal* still has
monitoring value once calibrated.

### Q8. "Complete audit trail" vs 66.7%
> "Your abstract claims a 'complete audit trail from every forecast back to the exact code
> commit.' Chapter 6 says 66.7%. Which is true?"

*Likelihood: medium; it's a gotcha, so recovery matters more than content.* The mechanism
guarantees completeness for every run produced through the CD pipeline (100% from the
first continuously-deployed run); five runs predate the mechanism and are reported as
misses precisely because the coverage metric is honest rather than curated. Concede the
abstract sentence would have been better scoped, then pivot: measuring and publishing your
own provenance shortfall is the methodological point.

### Q9. Self-administered ML Test Score
> "Why should I believe 2.5? And why does 'not applicable' score zero?"

*Likelihood: high.* The defense is built in: every item carries one line of checkable
evidence (Appendix), the score is recomputable, the contestable item (features-beneficial)
is documented with the argument that would raise it to 3.0 and deliberately left down, so
2.5 is a lower bound. N/A-as-zero (privacy, fairness, meta-requirements) is a deliberate
conservative choice; it costs up to 2 points in the Data section; better to under-claim.
Expect the cross-instrument jab: "8 of 9 practices realised, but 2.5/7 on the industry
rubric, how do both hold?" That is the thesis in one line: Zarour's practices measure
breadth of mechanism, Breck measures depth of test automation; the platform has DevOps
breadth and lacks ML-specific data-testing depth, which is the RQ3 answer. Deliver it as
an insight, not a defense.

### Q10. The AI question
> "Claude Code built much of this. Convince me you understand it."

*Likelihood: high, and the declaration invites it.* It won't come as one question; the
examiner picks an arbitrary artifact and drills. Mitigation: the fluency drills below plus
two rehearsed whiteboard walkthroughs: (a) one production day end-to-end (06:00 refit and
forecast, 18:00 reconciliation, 19:00 drift) with table names and failure modes; (b) the
LEAR feature vector and the Lasso objective, deriving 10n+7 = 247 live. Have a crisp
account of the verification discipline: every change through PR with CI gates, tests,
smoke runs; the framework-first build around Zarour's nine practices was the author's
plan. The declaration's traceability (co-author trailers, docs/ plans) is a strength;
cite it once, don't lean on it.

---

## Tier 2: likely deep-dives by area

### Modelling and data

- **Look-ahead and data-vintage integrity.** "Your exogenous inputs are ENTSO-E
  *forecasts*. Are the backtest feature values the vintages available before the day-ahead
  auction, and what stops a later revision from overwriting them, given the 48-hour
  re-ingest into a ReplacingMergeTree that keeps the newest row?" Also: "at 06:00 UTC, is
  tomorrow's wind/load forecast even published yet, and what does the live runner do if
  not?" And: "is your 'day' a UTC day or a CET market day when you pivot to daily rows?"
  **Answered in the deep dive below.**
- **Naive baseline definition.** The thesis uses the price exactly seven days earlier "as
  recommended by Lago et al. §5.4". If the paper's recommended naive is the hybrid
  (daily persistence midweek, weekly for Mon/Sat/Sun), the weekly-only naive is the easier
  opponent, inflating rMAE. **Checked against the paper below.**
- **"rMAE of 0.38-0.47 means you halve the naive error. Is that plausible, or is your
  naive just terrible in this regime?"** Honest answer: both. Weekly persistence fails
  badly in a volatile renewables-driven regime, so rMAE flatters all models relative to
  the papers' calmer eras, which is exactly why rankings, not rMAE levels, carry the
  cross-paper comparison (§5.4). Don't celebrate the 0.376 unprompted.
- **sMAPE with negative prices.** The denominator |y|+|ŷ| can approach zero near
  zero-crossing hours, making sMAPE unstable; it is reported for completeness, rMAE is the
  headline. Know this cold, since negative prices are in the motivation.
- **Hourly downsampling.** "Both markets trade 15-minute products now; an hourly mean
  price is no longer a tradable price. What did you actually forecast?" Defense:
  comparability with both source papers and across markets; DK1's <1 month of 15-min
  history makes native 96-period modelling infeasible; the 15-min product is future work.
  Sharp version: "so the platform forecasts something nobody can bid on." Answer: hourly
  means remain the standard research object and the pipeline is resolution-aware by
  construction.
- **p >> n in LEAR.** "You fit 247 coefficients on a 56-day window. How?" L1/sparsity
  answer fluently: Lasso as simultaneous shrinkage and selection, small effective degrees
  of freedom, three-window ensemble averaging. Within-window CV: 5-fold TimeSeriesSplit
  inside 56 days means tiny validation folds, so λ selection is noisy; the ensemble
  smooths it.
- **The loss-function inversion.** The DNN is trained on MAE yet wins on RMSE; LEAR
  minimises squared error yet wins on MAE. Story: training losses live in asinh space
  while metrics live in price space (the transform compresses exactly the spikes RMSE
  punishes), and LEAR's multi-window ensemble averaging dampens mean error while the
  single-window DNN handles extremes differently. "I can't fully decompose it, here are
  the mechanisms" is fine at bachelor level.
- **Tied hidden widths.** The DNN shares one tuned width across both hidden layers
  (191/373). If Lago tunes layer widths independently, that is a deviation **not** in
  Table 3.4. **Checked against the paper below.**
- **Why is DE more predictable (rMAE 0.376 vs 0.469)?** One-paragraph hypothesis (larger
  zone, solar's predictable diurnal structure in the exogenous set, DK1's
  wind-forecast-error dominance), clearly labeled as interpretation.
- **Model selection scope.** "Why no gradient boosting, which industry actually uses? Why
  no probabilistic forecasts when traders need quantiles?" Same answer: the study is
  anchored to published, fully specified benchmarks so that replication is meaningful;
  CRPS/pinball extension is named future work (Nowotarski). Note: `results/` contains
  unreported `dk1_rf_*` and `dk1_xgboost_*` runs from early exploration; can honestly say
  tree ensembles were tried early and dropped when the study was anchored to the
  published benchmarks.
- **Ensemble averaging space.** Are window-ensemble predictions averaged before or after
  the inverse asinh transform? **Answered in the deep dive below.**
- **Day-count accounting.** Be able to explain 220 → 204/201 → 187/176 precisely: warmup
  for lags, DST days dropped, data-gap days, the Transformer's 14-day input sequence.

### Statistics

- DM vs GW precisely (see Q4); the daily L1-norm aggregation makes it the "multivariate"
  variant; one-sided p-values; heatmap convention (cell (r,c): p that c is no better
  than r).
- Newey-West lag ⌊T^(1/4)⌋: standard bandwidth rule of thumb; HAC needed because daily
  loss differentials are autocorrelated (weekly seasonality, overlapping information).
- Why daily aggregation instead of 24 per-hour tests: avoids 24 correlated tests; matches
  the MAE focus; Lago's protocol.

### System and MLOps

- **"Walk me through 06:00 UTC."** Worker dispatches, ephemeral `algo-repo:latest`
  container, config load, ClickHouse window load with dedup, pivot and feature
  transformers, per-window refits, average, write to `experiment_runs` /
  `experiment_predictions` / `model_artifacts`, structured logs to Loki. Failure drills:
  ENTSO-E API down (task retries=2, then flow failure, then which alert catches it and
  when); model produces garbage (nothing gates it; accuracy-degradation fires only after
  next-day reconciliation; MLTS infra item 4 = 0, admitted); **host dies** (ENTSO-E data
  replayable, which was the DVC rejection argument, but `experiment_runs`, predictions,
  artifacts, the entire provenance record are a single volume; check the backup story
  before they do).
- **"Why 06:00 when gate closure is 12:00 CET?"** Know the publication-time reasoning or
  admit operational convenience with ~5h of slack for retries; tie to exogenous
  availability.
- **Tool sprawl.** "ClickHouse, Prefect, Loki, Prometheus, Grafana, W&B, for one host and
  one developer?" Defend each with its rejection-of-alternative (Ch5: Prefect over
  Airflow/Dagster, Loki over ELK, Compose over k8s, W&B over MLflow, ClickHouse blobs over
  a model store), and concede the meta-point gracefully: the stack is the pedagogical
  object as much as the means.
- **Two observability surfaces.** Grafana owns platform/data health, W&B owns model
  quality, both over the same ClickHouse tables. One sentence.
- **P5 with one developer.** "Who reviewed your PRs?" Honest: the gate is CI plus
  self-review plus the AI-assisted review record; realised at the level a solo project
  permits, hence Level 1. For P9 "checkbox engineering" phrasing: the **negative result**
  (drift-triggered retraining is redundant given cheap daily refits, cost-aware citation)
  is the contribution, and `algo.retrain_events` proves the loop works rather than just
  existing on a slide.
- **Overall maturity placement.** The table assigns per-practice Google levels but never
  one overall level. One-liner: "solidly Level 1 (automated, continuously-training
  pipeline), with Level 2's CI/CD characteristics on the code path; short of full Level 2
  chiefly for the missing pre-serving model validation gate." Skim Microsoft's five levels
  for cross-mapping.
- **"Rebuilt from the repository alone"** minus secrets (ENTSO-E key, Slack webhook, W&B
  key, Tailscale). Pre-concede if quoted.

### Evaluation methodology

- **Runeson & Höst threats to validity.** The thesis cites the framework but never
  enumerates threats explicitly. Prepare the four: construct (do MLTS/practice labels
  measure "maturity"?), internal (self-assessment bias, mitigated by per-item evidence and
  recomputable scripts), external (single host, single developer, two zones, analytic
  generalisation only), reliability (extract_metrics.py / reproduce_run.py make the
  measurements re-runnable).
- **Gundersen & Kjensmo placement.** "Which *kind* of reproducibility does your 7×10⁻⁶
  re-run demonstrate?" The weakest: same code, same data, re-executed (repeatability).
  Independent reimplementation is the stronger form, which the epftoolbox side-by-side
  future-work item would address. Say this unprompted.
- **"Why 7×10⁻⁶ and not zero, if LEAR is deterministic?"** Concrete answer needed
  (LassoCV coordinate-descent tolerance, BLAS threading / summation order, possibly
  different hardware). **Checked below.**
- **Snapshot freshness.** Ch7 numbers are a frozen 2026-06-04 snapshot. If asked "what
  would the script say today": answer with the snapshot date and that coverage only
  improves as post-CD runs accumulate; offer to re-run it live.
- **"What do you add over Subramanya et al.?"** They demonstrate a DevOps-to-MLOps
  pipeline on an electricity forecasting case qualitatively; this thesis adds
  benchmark-faithful replicated models, formal significance testing, and a quantitative
  system evaluation (MLTS, provenance coverage, reproduction). Skim their paper again the
  week before.

### Big picture and the standard closers

Write down exact answers for:
- **"What is THE contribution in one sentence?"** The significance-tested benchmark
  replication and the quantified maturity evaluation of the platform that serves it,
  joined in one artifact.
- **"What is the weakest point?"** Pick one and own it: the deep models' tuning budget
  contaminating RQ1's external comparison (the thesis already frames it well).
- **"What would you do differently?"** Run the 4-seed ensemble in the backtest; reserve
  compute for ≥100 Transformer tuning trials before adding system breadth.
- **"Who would use this and what's missing?"** Trading desks; missing: probabilistic
  forecasts, the 15-min product, a pre-serving quality gate, backup/DR.
- **"Is 0.4 EUR/MWh MAE difference economically meaningful?"** Trading value was not
  evaluated; say so before they do. Accuracy ≠ P&L.

---

## Facts to drill until automatic

| Item | Value |
|---|---|
| Test window | 2025-10-24 to 2026-05-31, 220 calendar days |
| Common days | DK1 187, DE 176 (LEAR/DNN alone: 204 / 201) |
| rMAE DK1 / DE | LEAR 0.469 / 0.376, DNN 0.482 / 0.388, Transformer 0.543 / 0.420 |
| Key p-values | LEAR vs DNN 0.16 (DK1), 0.19 (DE); vs Transformer 0.001 / 0.012 / 0.006; naive ≈ 0 |
| Calibration windows | LEAR 56/84/1092 d (1456 dropped), DNN 730 d, Transformer 1092 d; refit daily/daily/weekly |
| Features | 10n+7 = 247 hourly (4n price lags d−1,−2,−3,−7; two exog × 3 lags d,−1,−7; 7 dummies) |
| DNN HPs | DK1: 191, tanh, 0.203, 4.8e−4, no BN, L1 6.8e−8; DE: 373, relu, 0.204, 6.9e−4, BN, 7.1e−7; 30 TPE trials, val 2025-01-01 to 2025-10-23 |
| Transformer | 14-day input, embed 128 (paper NP optimum 512), 6 layers, 8 heads, FF 1024, dropout 0.2, Adam 1e−4 |
| Cost s/day | LEAR 50.3 / 41.3 (CPU); DNN 0.9 / 1.6, Transformer 1.6 / 1.9 (GPU) |
| MLTS | 2.5 = min(Data 2.5, Model dev 3.0, Infra 4.0, Monitoring 4.0); band (2,3] |
| Provenance | 10/15 = 66.7% full set; 100% post-CD; re-run diff 7×10⁻⁶ EUR/MWh (dk1_lear, 2026-03-22) |
| Drift | 49/49 flagged; 90 d reference vs 7 d current; Evidently in-process |
| Alerts | staleness 12 h, reconciliation-missed 36 h, MAE > 1.5× 30-day median, clickhouse-down 5 min |
| Cadence | 06:00 forecast, 18:00 reconcile, 19:00 drift (UTC) |
| Nine practices, in order | CI/CD, orchestration, reproducibility, versioning, collaboration, continuous train/evaluate, metadata tracking, monitoring, feedback loops |

---

## Presentation strategy

Put a limitations slide **before** conclusions that names the top four weaknesses
(tuning budget, single-seed backtest, 31-week window, drift calibration); every question
asked from your own slide is a question you control. Rehearse the two whiteboard
walkthroughs (one production day; the LEAR feature vector to 247). When conceding, concede
in one sentence and pivot to the mechanism that bounds the damage; the thesis almost
always has one. Know the typos exist ("compliment", "expendsive", "train once
and-enormalise" in §7.1) so a quoted sentence doesn't rattle you; nobody fails a defense
on typos.

---

## Pre-defense verification checklist

1. GW implementation: statistic and instruments the code computes; epftoolbox match.
2. Exogenous vintage integrity: processType fetched; revision overwrite risk via 48 h
   re-ingest + ReplacingMergeTree.
3. 06:00 UTC availability: are D+1 load/wind forecasts published by then; live-runner
   behavior when missing.
4. Day-boundary timezone: UTC vs CET pivoting; DST-drop mechanics.
5. Lago §5.4 naive definition: weekly vs hybrid.
6. Ensemble averaging space: before or after inverse asinh.
7. Live operations dossier: per-deployment start dates, the 15 runs' dates, live MAEs,
   incidents.
8. DNN seed variance: any repeated-config runs to quote.
9. Lago's DNN layer widths: independently tuned or not (tied-width deviation).
10. Gap-day accounting behind 204/201/187/176.
11. Prod host hardware (is the GPU in the cost table the production GPU?) and the
    backup/DR answer for the ClickHouse volume.
12. Subramanya et al. and Microsoft maturity levels: skim for comparison questions.

---

# Deep dive: verified findings

Code-and-references pass done 2026-06-09. Every claim below was checked against the
repository or the source PDFs in `researh_material/`. Verdicts first, details after.

| # | Checklist item | Verdict |
|---|---|---|
| 1 | GW implementation | **Unconditional variant** — constant-only regression = DM special case (Lago eq. 15). Prepare the exact answer below. |
| 2 | Exogenous vintage | **Bounded risk.** Only `processType=A01` (day-ahead) is ever fetched; intraday/current types never ingested. Re-publication of an A01 doc within the ±24/48 h window can overwrite (engines: `ReplacingMergeTree(updated_utc/created_utc)`). |
| 3 | 06:00 availability | **CRITICAL FINDING** — see below. Scheduled target-tomorrow runs cannot succeed; the 15 live runs are CD smoke runs + manual triggers. |
| 4 | Day boundary / DST | Days are **UTC days** end-to-end. No DST drops (2026-03-29 present in both markets); dropped days are **data-gap clusters** in Apr–May 2026 (+late Oct for DE). |
| 5 | Lago naive | **Vindicated.** Lago explicitly recommends p̂naive,2 = p(d−7,h), the pure weekly naive. Quote ready. |
| 6 | Averaging space | Window forecasts are inverse-asinh'd to price space **before** the ensemble mean (`engine.py:99,132`). |
| 7 | Live ops dossier | 15 runs = 11 dk1_lear (CD smokes, fixed target 2026-03-22) + 1 each dk1_dnn/dk1_transformer/de_dnn/de_transformer + **0 de_lear**. Confirm on host. |
| 8 | DNN seed variance | Not yet measured — but a dk1_dnn backtest takes ~3 min, so **measure it before the defense** (run 3 seeds). |
| 9 | Lago DNN widths | Paper lists "the number of neurons per layer" as ONE of eight HPs (counting (1)–(8)), so tied widths are a defensible reading. Code ties them: `dnn.py:33-35`. |
| 10 | Gap days | DK1 lost 16 days (2026-04-13..17, 04-20/21, 05-06..11, 05-13..15); DE lost 19 (2025-10-25..28, 11-01, plus Apr–May clusters). Each gap day shadows up to 7 (LEAR/DNN) or 14 (Transformer) later days through the lag joins. |
| 11 | Hardware / backups | Benchmark hardware = **dev machine** (RTX 3060, 16 cores; timings logged +02:00 local on Jun 4–5). **No backup/DR mention anywhere** in DEPLOYMENT.md / RUNBOOK.md / compose. |
| 12 | Subramanya / Microsoft | Subramanya = Finnish **FCR-N** market on **Kubeflow/Kubernetes**, 3 case studies. Microsoft maturity levels still to skim (Zarour PDF). |

## A. CRITICAL: the scheduled day-ahead serving path cannot succeed as deployed

This is the one finding that must be resolved on the prod host before the defense.

**The mechanism.** `daily_forecast_flow` defaults `target_date` to tomorrow UTC
(`forecast.py:88`) and the deployments pass only `config_name` with cron `0 6 * * *`
(`deploy_forecast.py:96-98`). But `LiveRunner` reuses `build_dataset`, whose
`valid_mask` requires the **target day's own actual prices** to exist
(`preprocessor.py:118-124` — features∩targets intersection plus all-not-NaN), and
`load_dataset` inner-joins prices with exogenous (`clickhouse_loader.py:123`). Tomorrow's
prices clear at ~12:00 CET today (the repo's own comment: "day-ahead prices are published
(~14:00 UTC)", `deploy_forecast.py:101-102`) — hours after 06:00. Worse, because the
pivot day is the **UTC** day, the last 1–2 UTC hours of any target day belong to the
*next* CET delivery day, auctioned a day later, so "tomorrow UTC" is never fully priced
until tomorrow ~13:00 UTC. A 06:00 run targeting tomorrow therefore always raises
`Target date not found in available data` (`live_runner.py:62-63`).

**The evidence it never worked on schedule.** The frozen metrics
(`Report/metrics/quantitative_results.md`, Jun-4 snapshot) show 15 runs in 90 days:
dk1_lear 11, the four DNN/Transformer configs 1 each, de_lear 0. Eleven matches the
squash-merges to main that pass the smoke path filter, and the CD smoke pins
`target_date: "2026-03-22"` (`cd_deploy.yml:212`) — a fixed past date, which is also the
reproducibility-demo date. If the 06:00 schedule worked, dk1_lear alone would have ~90
runs. The failure is masked everywhere: unit tests mock the runner
(`tests/schedules/test_forecast.py`), pr_smoke uses synthetic data that includes the
target day, and the CD smoke uses the pinned past date.

**Why it is survivable.** Three honest points. (1) Every recorded forecast is
information-set-correct: training slices are strictly pre-target (`engine.py:40`),
features are lags plus A01 day-ahead forecasts, so no leakage; the accuracy numbers are
honest. (2) The thesis itself reports only 15 live runs in Ch7 — it never claims ~540
successful daily runs; the over-claim is limited to the P6 prose ("executes the
daily-forecast flow at 06:00 UTC ... and immediately produces a day-ahead forecast") and
the cadence figure. (3) The fix is small and demonstrable: build a predict-path feature
matrix that does not require the target day's actuals (the union index instead of the
intersection, target row validated on features only), and schedule after the target day's
A01 exogenous forecasts are published.

**Recommended strategy.**
1. On the host, confirm in the Prefect UI what the scheduled 06:00 runs actually did
   (expected: failed), and pull `algo.experiment_runs` target dates vs `created_utc`.
2. Fix it now, post-submission, on a branch: predict-path without target actuals +
   schedule adjustment + a real day-ahead run for an actual tomorrow. Bring the commit.
3. If asked "what did your platform forecast this morning?", answer yourself before the
   examiner digs: "the scheduled path had a defect I found after submission — the live
   runner reused the backtest's dataset builder, which requires the target day's actuals;
   the recorded live runs are deploy-gate and manual runs, information-set-correct but
   not ahead-of-time; here is the fix and a real run." Finding and fixing your own defect
   with a precise mechanism is a strong answer; being shown it is not.
4. Note the alert-design lesson for RQ3 if pressed: there is no "forecast-missed" alert
   (only `reconciliation-missed`, 36 h), which is *why* a failing daily flow could go
   unnoticed — a monitoring-coverage gap worth owning as a finding.

## B. The GW test is the unconditional (DM-equivalent) variant — exact answer ready

`giacomini_white_multivariate` (`statistical_tests.py:77-132`) computes the daily L1
loss differential and a Newey–West HAC t-test on its mean; the docstring itself says
"(unconditional) GW statistic". Lago's paper, §5.5.2: the GW regression (their eq. 14)
uses instruments X(d−1) = a constant **and lags of the loss differential**, and "using
this notation the DM test can be written as Δ = μ + ε, i.e. with X containing just a
constant" (their eq. 15). So the implementation is exactly Lago's eq. 15 — the DM special
case of the GW framework, on the multivariate (daily-aggregated) loss differential, with
HAC errors and one-sided alternatives (`summary.py:126-131`, `alternative="b_better"`,
Lago Fig. 5 convention).

**Defense line:** "The implementation is the unconditional multivariate variant: the GW
regression with the instrument set reduced to a constant, which Lago et al.'s eq. 15
notes is precisely the DM test; I compute it on the daily L1 loss differential with
Newey–West errors. The full conditional GW adds lagged loss differentials to the
instruments — a one-line extension I'd add for conditional predictive ability. The
thesis's figure label 'GW multivariate' follows Lago's protocol naming." Concede that the
conditioning (and with it GW's parameter-estimation-uncertainty advantage) is not
exercised. If pressed on why it matters under rolling windows, that is exactly the
examiner's point — concede, offer the extension.

## C. Naive baseline: vindicated, and robustness quantified

Lago et al. define three naives and explicitly recommend the weekly one: "In the context
of EPF, rMAE using p̂naive,2 = p(d−7,h) is arguably the best choice ... we will use rMAE
to explicitly refer to the rMAE based on p̂naive,2." The thesis's weekly naive is exactly
the paper's recommendation — quote it if challenged with the hybrid (naive,3).

One real wrinkle found: `build_weekly_naive` is `actuals.shift(7)` (`summary.py:17-18`),
a **positional** shift on the gap-containing common-day index, so post-gap rows use a
22–36-day-old price instead of 7 (DK1: 14/180 rows; DE: 7/169). Recomputed with a
calendar-exact naive (2026-06-09):

| | LEAR | DNN | Transformer | naive MAE |
|---|---|---|---|---|
| DK1 as published | 0.469 | 0.482 | 0.543 | 36.899 |
| DK1 calendar-correct | 0.465 | 0.474 | 0.512 | 36.775 |
| DE as published | 0.376 | 0.388 | 0.420 | 35.049 |
| DE calendar-correct | 0.379 | 0.388 | 0.416 | 34.744 |

Third-decimal shifts, ordering unchanged, conclusions intact. If a code-reading examiner
spots the positional shift: "correct — I recomputed with a calendar-exact naive; rMAE
moves in the third decimal and no conclusion changes." Have these numbers with you.

Also useful: `model_comparison.md` already places ours vs the paper (Lago Table 3 NP:
LEAR 0.42, DNN 0.407 vs ours 0.469, 0.482) — our relative-to-naive skill is *slightly
worse* than the paper's, so there is no "implausibly good rMAE" attack surface.

## D. Dropped days: gaps, not DST — corrected accounting

The thesis says "warmup, gap, and daylight saving days are dropped" and attributes the
Transformer's smaller common set to "leading days". The data says otherwise:

- Everything is UTC end-to-end (`load_price_series` parses `utc=True`;
  `resample_hourly`'s docstring: "Operates in UTC ... DST introduces no missing or
  duplicated hours"). The 2026-03-29 spring-forward day is present in both markets.
- The dropped days are **data-gap clusters**: DK1 16 days (2026-04-13..17, 04-20/21,
  05-06..11, 05-13..15), DE 19 days (2025-10-25..28, 11-01, 2026-04-27..05-01,
  05-04/05, 05-10..14, 05-17/18).
- Mechanism: after `resample("1h")`, missing hours are NaN rows; lag joins propagate the
  NaN so each gap day shadows the following lag-depth days (7 for LEAR/DNN, **14** for
  the Transformer's sequence — that, not "leading days", is why it keeps only 187/176).
- Before the defense, root-cause the gaps on the host (which curve was missing — price
  or an exogenous series — in those windows). "What are these gaps?" is an easy and
  likely question once anyone plots the forecasts.
- The UTC-day choice also means the forecast "day" is offset 1–2 h from the CET delivery
  day. Internally consistent across all models and the naive, but be ready: "the
  hour-of-day error plot is UTC hours; converting the serving layer to CET market days is
  a re-pivot, listed as deployment work."

## E. Models and configs: all thesis numbers confirmed, plus ammunition

- LEAR: `LassoCV(cv=TimeSeriesSplit(5), max_iter=5000)` per period, `alpha="auto"`
  (`lear.py:32-36`, config) — matches §3.3.1.
- DNN: tied hidden widths confirmed in code (`hidden_units: int → (h,h)`,
  `dnn.py:33-35`). Lago's own §4.2 lists "(1) the number of neurons per layer" as one of
  exactly eight hyperparameters, so the tie is a defensible reading of the paper; concede
  it is not tabled in Table 3.4 if pushed.
- Backtest DNN is **single-model-per-refit in code** (`BacktestRunner` never touches
  `n_dnn_ensemble`; only `LiveRunner` does, `live_runner.py:66-77`) — the thesis's
  single-seed claim is accurate. Ignore `run_timings.md`'s "Ensemble 4" column for the
  DNN backtest rows; it echoes the config, not the executed path.
- Tuning budget, with wall-clock to quote: 30 TPE trials took **5 h 51 m** (DK1,
  contended) and 5 h 33 m (DE) on the RTX 3060 (`run_timings.md`). Lago's T=1500 (paper
  line: "T is selected as 1500 iterations") would be ~50× ≈ **12 days per market** on
  this hardware. That is the concrete "why 30" answer. Best trial = #26 (val MAE 19.069,
  `configs/dk1_dnn.py`), i.e. the optimum was still moving at the end — concede headroom.
- Transformer distance from the paper's Nord Pool optimum (their Table 6, best row):
  embedding **512 vs our 128**, FF **2048 vs 1024**, lr **1e-5 vs 1e-4**, sequence
  **672 h (28 d) vs 336 h (14 d)**; heads 8 = ours. Four axes, not one — strengthens the
  under-optimisation story, and corrects the thesis's "128 ... below its Nord Pool
  optimum of 512" to a fuller statement if asked.
- **New RQ1 ammunition from Llorente's own text** (§4, results): their DM-tested win over
  the DNN is against a DNN evaluated **without retraining** ("renormalization" only), and
  they themselves note "in some cases, the naive model outperforms the DNN Ensembles.
  This could be due to the fact that the DNN model has to make predictions for a long
  test period without retraining." The thesis restored daily recalibration to the DNN and
  put the Transformer in a non-native rolling mode — the two papers' regimes differ in
  opposite directions, which explains the inversion more sharply than budget alone. Use
  this; it is grounded and it is yours.

## F. System facts confirmed

- ENTSO-E fetches: prices A44; load A65, generation A71, wind/solar A69 — all forecasts
  with `processType=A01` (day-ahead) only (`client.py:54,91-95,117-121,143-148`).
  Intraday/current vintages are different process types and are never ingested, so the
  vintage-overwrite exposure is limited to re-publications of the A01 document within the
  ingest window (`[now−24h, now+24h]`, `ingestion.py:20-21,91-92` — note it is
  24 h back + 24 h ahead, not "48 h back" as the thesis P2 prose says; minor).
- Drift: Evidently `DataDriftPreset` on raw hourly prices, ref [today−97, today−7), cur
  [today−7, today), `MIN_SAMPLE_SIZE=30`, verdict from `DriftedColumnsCount`
  (`drift.py:35-113`). Ref n≈2160 vs cur n≈168 — the overpowered-test explanation holds.
  Pull one `algo.drift_reports.stat_test` value on the host so you can name the test that
  actually ran instead of "K-S or Wasserstein".
- Reconciliation accuracy alert: `threshold_multiplier=1.5` vs 30-day median
  (`reconciliation.py:284-295`). Retrain trigger scans configs for
  `retrain_on_drift=True`, none set (`drift.py:268-307`) — matches P9.
- Breck scoring rule verified in the paper: "half a point is awarded for executing the
  test manually, with the results documented" — the thesis's {0, 0.5, 1} usage is
  faithful.
- Backups: **no backup/restore/DR mention in DEPLOYMENT.md, RUNBOOK.md, or
  docker-compose.yml.** The honest answer stands: raw data replayable from ENTSO-E (the
  DVC-rejection argument), but `experiment_runs`/predictions/artifacts — the provenance
  the thesis is proudest of — live in one unbacked volume on one host. Own it; pair it
  with the single-host-limits paragraph in RQ3.
- Hardware: Table 5.3's GPU is the **dev machine** (RTX 3060, 16 cores; benchmark ran
  locally Jun 4–5, timestamps +02:00). Confirm what the deploy host has before the
  defense; if it is CPU-only, know the production DNN/Transformer refit cost there.
- Subramanya contrast, now precise: they forecast the Finnish **FCR-N**
  (frequency-containment-reserve) market with Kubeflow-on-Kubernetes pipelines across
  three case studies; no benchmark-model replication, no significance testing, no
  quantitative maturity scoring. The thesis's delta is exactly those three things, on a
  deliberately smaller (single-host) operational footprint.

## G. Remaining host-side verifications (cannot be done from this repo clone)

1. Prefect UI: state history of the six `daily-forecast-*` scheduled runs (expect
   Failed; screenshot or counts).
2. `algo.experiment_runs`: `created_utc`, target dates, `git_sha` per run — confirm the
   11-smokes + 4-manual + 0-de_lear reading, and have each run's live MAE from
   reconciliation at hand.
3. `algo.drift_reports.stat_test` — name the test that actually ran.
4. Deploy-host hardware (GPU or not) for the production-cost answer.
5. `ingested_utc` of D+1 exogenous rows across a few days — measures when ENTSO-E A01
   forecasts actually become available, which is the design input for the post-fix
   schedule time.
6. Root-cause the Apr–May gap clusters (which curve went missing).
7. Skim Microsoft's maturity levels in the Zarour PDF for the cross-mapping question.
8. Optional only: measure DNN seed variance (3 × dk1_dnn backtest, ~3 min each) for a
   concrete number on Q2/R5. Not required — R5 defends the point conceptually.

## H. Corrections to the Tier-1 answers above

- **Q2 (single seed):** defend conceptually per R5 (no experiment needed); the
  serving/eval mismatch stands (code-confirmed). A 3-seed measurement is optional ammo,
  not required.
- **Q4 (GW vs DM):** answer upgraded — cite Lago eqs. 14/15 directly (section B above).
- **Q6 (production evidence):** answer rewritten by section A. Do not walk into this one
  unprepared; it is now a known, fixable defect with a prepared narrative.
- **New likely question — "your rMAE vs the paper's":** ours 0.469/0.482 vs Lago NP
  0.42/0.407 — slightly weaker relative skill on a harder regime; rankings, not levels,
  carry the comparison. No inflation story to defend.
- **Naive choice:** fully safe; quote Lago's p̂naive,2 recommendation verbatim if needed.
