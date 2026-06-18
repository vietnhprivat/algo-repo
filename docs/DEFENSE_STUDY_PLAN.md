# Defense Study Plan

The actionable companion to `DEFENSE_PREP.md`. That document is the *what they will ask*
(the question bank, R1–R12, the deep dive). This one is the *how to prepare* — which report
sections to re-read, which references to refresh and to what depth, and what to drill until
automatic. Cross-references like (R2) or (Tier1 Q4) point back into `DEFENSE_PREP.md`.

> **Section and table numbers below match the compiled report** (`Report/main.toc`,
> `main.lot`), not the markdown export. The markdown's chapter numbers are inflated by one
> (its "Chapter 4 / §4.5" is the real **Chapter 3 / §3.5**). The real chapter order is:
> 1 Introduction, 2 Background, 3 Forecasting Models and Evaluation, 4 System
> Implementation, 5 Forecasting-Model Results, 6 System-Evaluation Results, 7 Discussion,
> 8 Conclusion, A Glossary, B ML Test Score Worksheet.

Guiding principle: you are defending the **report**, in front of a stats / ML /
reproducibility examiner who has not read the code. So re-read for three things at once —
the argument spine, the exact numbers, and every place the prose claims more than the
tables prove.

---

## Time budget (scale to what you have)

A five-session plan. If you have fewer days, do Sessions 1, 2, and 5 and skim the rest.

1. **Session 1 — the spine.** Re-read the MUST sections below; be able to state the three
   RQs, the one-sentence contribution, and the headline result without notes.
2. **Session 2 — the stats gauntlet.** R1 and R2 specifically. This is where the
   likelihood times damage is highest for this examiner.
3. **Session 3 — reference refresh.** Tier A papers, targeted parts only.
4. **Session 4 — drills + a mock.** Active recall from memory, then a spoken run-through.
5. **Session 5 — slides, talk track, one-page cheat.** The night before.

---

## Part 1 — Report re-read map

Priority tags: **MUST** (high-traffic, re-read closely), **SHOULD** (read once),
**SKIM** (know it exists and the one-liner).

### MUST

- **§1.3 Aim & research questions, §1.4 Contributions.** The spine. Walk away able to
  recite the three RQs verbatim-ish and the contribution in one sentence. Opening question
  and all closers. (Tier1 closers)
- **§3.1 Replication framing + §3.7 Deviations (Table 3.4).** The "faithful in
  specification, bounded in budget" line, and every row of the deviations table with its
  reason. (R7, Tier1 Q1)
- **§3.5 Evaluation protocol.** Re-read word for word — this is where the GW description
  lives, and it reads like the DM test. Know the daily loss-differential formula and the
  Newey–West HAC detail. (R1, R2)
- **§5.1 Headline accuracy + §5.2 Statistical significance.** The numbers (Tables 5.1/5.2)
  and the "tie." Note the report uses both "statistically tied" and the safer "neither can
  be shown more accurate" — rehearse leading with the second. (R1, drills)
- **§5.4 Comparison with published benchmarks.** The ranking inversion and its
  explanation. Find the sentence that states the budget cause and note how firmly it is
  worded. (R3)
- **§6.1 ML Test Score (Table 6.1) + §6.2 Reproducibility (Table 6.2).** The 2.5
  (min-of-sections), the 66.7 %, the $7\times10^{-6}$ re-run. (R4, R6)
- **§6.3 Drift + §6.4 Maturity placement (Table 6.3).** The 49/49 admission and the
  "Realised" labels; reconcile them. (R8)
- **§7.1 RQ1 (and §7.3 RQ3).** The synthesized answers; flag every "attributable" /
  "tied" you would soften out loud. (R1, R3, R8)
- **Wording traps to reconcile (read these exact claims and pre-write your concession):**
  the "complete audit trail from every forecast" sentences in §1.3 (Aim), §7.4 (Tying the
  threads, "any forecast can be reconstructed"), and Chapter 8 (Conclusion), against the
  66.7 % in §6.2 (R4); the "daylight saving days are dropped" line in the Chapter 5 results
  intro and §3.5 (R9); "statistically tied" vs "indistinguishable" (R1).

### SHOULD

- **§2.2 Lago benchmark, §2.3 Transformer, §2.4 MLOps practices, §2.5 evaluation methods.**
  The lit-review framing, so you can attribute every method you use to its source paper on
  demand.
- **§3.2 Data and features.** Be able to derive the feature count (see drills). The asinh
  rationale and the hourly-downsampling justification.
- **§3.3 Models (3.3.1 LEAR, 3.3.2 DNN, 3.3.3 Transformer).** Note §3.3.2's admission that
  the backtest DNN is single-seed (R5), and the Transformer's distance from the paper
  optimum in §3.3.3.
- **§3.4 Recalibration and backtesting.** The rolling-window ensemble, refit cadences,
  which windows each model uses.
- **§4.2 System at a glance + the P1–P9 practices (§4.3.1–4.3.9).** Be able to name all
  nine practices in order and the one artefact you map each to (Table 4.1 inventory, Table
  6.3 maturity).
- **§7.2 RQ2, §7.5 Limitations.** The trade-off narrative and your own stated limits.

### SKIM

- **§2.1** (Weron / Nowotarski background), **§4.3 P1–P9 prose** (know the
  rejected-alternative one-liners — Prefect over Airflow/Dagster, Loki over ELK, Compose
  over k8s, W&B over MLflow — but do not memorize the prose), **§4.4 cross-cutting**, the
  **appendices** (know the ML Test Score worksheet, Appendix B, exists and how the section
  sums add up).

---

## Part 2 — The stats gauntlet (give it a whole session)

This is the highest-value hour of prep. For each, practice saying the answer aloud in two
or three sentences.

- **"p=0.16 is not a tie."** Non-rejection vs equivalence; power at n≈187 against a ~3 %
  gap; the TOST/equivalence sentence said unprompted. (R1)
- **DM vs GW.** Write $\Delta^{A,B}_d = \phi' X_{d-1} + \epsilon_d$; explain that with $X$ =
  a constant it reduces to the multivariate DM test (Lago eq. 15), which is what you
  compute; the full conditional GW adds lagged differentials. Know *why* GW exists
  (conditional predictive ability under recalibration). (R2)
- **Multiple comparisons.** No correction; why it does not bite (the load-bearing results
  clear any correction by orders of magnitude, the borderline cell is a non-rejection). (R1)
- **Newey–West.** Why a HAC standard error at all (autocorrelated daily loss
  differentials), and the lag rule $\lfloor T^{1/4}\rfloor$. (Tier2 stats)
- **Seed variance.** The conceptual answer (R5) — no experiment needed.

---

## Part 3 — Reference refresh map

Refresh targeted parts, not whole papers. All PDFs are in `researh_material/`. Section
numbers in this part are the **papers'** own numbers (not the thesis's). For the Tier B/C
papers, the instruction is "re-read to *confirm* the exact terms" — do not walk in quoting
a taxonomy from memory.

### Tier A — must refresh (re-read the named parts)

- **Lago et al. 2021** (the anchor; 32 citations in your report). Re-read:
  - **§5.5.2 The Giacomini–White test** — eqs. 14 and 15. This is the source for the R2
    answer; the constant-instrument reduction to DM is *in this section*. (§5.5.1 is the
    DM test itself.)
  - **§5.4 Evaluation metrics for point forecasts** — the three naive definitions and the
    explicit recommendation of $\hat{p}_{\mathrm{naive},2}$ (price 7 days earlier). This
    vindicates your baseline; be able to quote it.
  - **§5.7 Ex-ante hyperparameter optimization** (the 1500-iteration TPE budget, the
    ex-ante principle) plus their forecasting-methods section for the DNN architecture,
    the eight tuned hyperparameters, and the four-run ensemble (§4.4). Backs R3 and the
    tuning-budget arithmetic.
  - **§5.8 Computation time** — the "more than 30 min / 1 h is unsuitable" rule of thumb,
    your analogue for the cost table.
  - **Table 3** (their rMAE values) — for the cross-paper ranking comparison.
- **Llorente & Portela 2025** (the Transformer; 12 citations). Re-read:
  - **§3.3 Retraining and Renormalization** — the key point that their model and DNN are
    evaluated *without retraining*, with a renormalization step instead. This is your
    sharpest RQ1 argument (their DNN was handicapped; yours recalibrates daily). (R3)
  - **Their Nord Pool validation table** (the HP grid, the n=512 embedding optimum) — for
    the Transformer-deviation answer.
  - **§4 results + their limitations** — they used the DM test only and flagged short test
    periods; context for why your significance-tested comparison adds something.
- **Breck et al. 2017** (ML Test Score). Refresh: the four sections (data, model
  development, ML infrastructure, monitoring), seven items each, the **min-of-sections**
  final score, and the **half-a-point-for-manual** rule. Backs R6 and §6.1.
- **Zarour et al. 2025** (the SLR; 16 citations — your second most-cited). Refresh: the
  **nine practices** (be able to define each in a sentence) and the **five maturity
  models**, especially why Google over Microsoft. Backs RQ3 and R10.

### Tier B — should refresh (confirm the exact terms, then state crisply)

- **Gundersen & Kjensmo** (reproducibility in AI). Confirm their degrees/types of
  reproducibility, so you can correctly place your re-run as the weakest form (same code,
  same data, re-executed). (R6)
- **Runeson & Höst** (case-study method). Confirm the validity-threat categories
  (construct / internal / external / reliability) and the analytic-vs-statistical
  generalization distinction. Backs the case-study-method questions (Tier2 eval).
- **Mahadevan & Mathioudakis** (cost-aware retraining). Confirm the core result —
  triggered retraining pays off mainly when retraining is expensive — which is your
  justification for drift-as-monitoring-not-trigger. (R8, §6.3)
- **Diebold–Mariano 1995 / Giacomini–White 2006.** Do not read the dense econometrics;
  take the concepts from Lago §5.5.1–5.5.2. Be able to say in one line what each tests
  (unconditional vs conditional equal predictive ability). (R2)

### Tier C — one-liner only

- **Weron 2014 / Nowotarski & Weron 2018** — the EPF and probabilistic-EPF reviews; one
  sentence each (background, and the CRPS/pinball direction for future work).
- **Uniejewski et al. 2018** — the asinh variance-stabilising transform; "defined for
  negative prices, unlike log."
- **Subramanya et al. 2022** — the DevOps-to-MLOps electricity-forecasting precedent (the
  Finnish FCR-N market on Kubeflow/Kubernetes); your delta is replicated benchmark models
  + significance tests + a quantitative maturity evaluation.
- **Google MLOps maturity model** — the three levels (manual, ML-pipeline automation,
  CI/CD-pipeline automation).

> Reference list is complete and verified against the report's citations. DORA is **not**
> cited in the final report (despite the PDF sitting in `researh_material/`), so do not
> prepare it.

---

## Part 4 — Active-recall drills (do from memory, on paper)

If you cannot produce these without notes, you are not ready for that question.

- **Feature count.** Derive $10n+7 = 247$ at $n=24$ — name each block (4 price-lag blocks
  d-1/d-2/d-3/d-7, two exogenous at three lags d0/d-1/d-7, seven weekday dummies).
- **GW regression.** Write $\Delta^{A,B}_d = \phi' X_{d-1} + \epsilon_d$ and the
  constant-instrument reduction to DM.
- **Day-count funnel.** 220 calendar days $\to$ 204/201 (LEAR/DNN, DK1/DE) $\to$ 187/176
  common, and why each drop happens (lag warmup, data gaps, the Transformer's 14-day
  sequence). Verified from the result CSVs.
- **rMAE.** The formula and why it is the headline (cross-period / cross-market
  comparability via the same-market naive).
- **The nine practices in order**, each with its one artefact (CI/CD → GitHub Actions;
  orchestration → Prefect; reproducibility → GIT_SHA + Compose; versioning → Git +
  migrations; collaboration → PRs + docs; train/evaluate → daily-forecast + reconciliation;
  metadata → ClickHouse tables + W&B; monitoring → Grafana/Loki/Prometheus + alerts;
  feedback → drift + retrain flag).
- **ML Test Score sums.** Data 2.5, model dev 3.0, infra 4.0, monitoring 4.0, min = 2.5,
  bound by data; why data binds.
- **Headline table.** rMAE per model per market and the key p-values (LEAR–DNN 0.16/0.19,
  vs Transformer $\le 0.013$, vs naive $\approx 0$). The full table is in `DEFENSE_PREP.md`.

---

## Part 5 — Slides and talk track

- **Pre-empt with a limitations slide before the conclusion** that names your own top four
  (the tuning budget behind RQ1 / R3, statistical power / R1, single-seed backtest / R5,
  the over-flagging drift detector / R8). Every question asked off your own slide is one
  you control.
- **Two whiteboard-ready explainers**, rehearsed: the feature vector to 247, and the GW/DM
  relationship.
- **The 60-second contribution statement**, memorized.
- **The standard closers**, written out: weakest point (pick one, own it), what you would
  do differently, who would use this and what is missing.

---

## Part 6 — Night before, one page

Carry only this:

- The headline numbers table (rMAE, key p-values).
- The nine practices in order.
- The GW/DM one-liner and the feature-count derivation.
- The three RQ answers in one sentence each.
- "Weakest point" and "would do differently."
- The three concessions you have pre-written (audit trail → "every continuously-deployed
  forecast"; "attributable" → "most consistent with"; "tie" → "indistinguishable on this
  window").

---

## Appendix — known wrinkle to be aware of

Two examiners, not one. Your supervisor (Finn Årup Nielsen) reads with an ML/stats/
reproducibility eye, which is why R1, R2, R6 are weighted highest. But a Danish defense also
has an **external censor** who also reads only the report and whose background you do not
control. Keep the system/MLOps narrative (RQ2, RQ3, the nine practices, the
rejected-alternative justifications) sharp as well, in case the censor comes from that
angle, rather than betting everything on the statistics questions.
