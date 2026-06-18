# Defense Presentation Plan (20 minutes)

Companion to `DEFENSE_PREP.md` (question bank) and `DEFENSE_STUDY_PLAN.md` (how to study).
This is the talk itself. Section/table/figure references are the **compiled report's**
numbers (verified against `main.toc` / `main.lot`).

## Design principles for a 20-minute slot

- **20 minutes is a spine, not the report.** Roughly 14 content slides at ~1–2 min each.
  You cannot cover everything; you cover the argument, the headline results, and the
  evaluation. Detail lives in appendix slides.
- **Protect the payoff.** The two results threads (RQ1 forecasting, RQ3 maturity) are why
  you are here. The classic failure is spending 12 minutes on motivation and models and
  rushing the results. Budget the back half generously.
- **One idea per slide. Big, readable numbers.** Do not put the deviations table or the
  feature equation on a main slide; reference that they exist and move on.
- **Rehearse to ~18 minutes.** Leave buffer for a slow start, projector setup, and nerves.
  Going under 20 is fine; going over is penalised in feel.
- **Appendix slides are your prepared answers.** The format explicitly lets you move
  overflow slides after the "last" slide and show them during questioning. Build one
  appendix slide per likely question (list at the end). When asked about the GW test, you
  flip to the GW slide. This is the single biggest reason to over-build the deck.
- **Export to PDF and present from PDF.** No animation/font dependence, no Keynote/PPT
  surprises on the projector. Bring it on a USB stick and email it to yourself and your
  supervisor. Test on an external display beforehand (the format note warns about
  connection problems).

---

## Main deck (target ~18–19 min)

### 1. Title (~20 s)
Title, your name and student number, supervisor (Finn Årup Nielsen), DTU Compute, date.
One line under the title naming the two threads, "benchmark EPF models inside an MLOps
platform." DTU Beamer template is fine but optional.

### 2. Motivation — why day-ahead EPF is hard (~1.5 min)
Day-ahead prices drive scheduling, hedging, and bidding. The series is spike-prone,
heavy-tailed, and increasingly goes **negative** under high renewables (so no log
transform). One visual: a DK1 price stretch showing a spike and a negative hour. Land the
hook in one sentence: accurate forecasts matter and the task has got harder.

### 3. The gap this thesis fills (~1 min)
EPF research produces accurate models but stops at **offline** evaluation. MLOps exists to
close the build-versus-operate gap (scheduling, monitoring, reproducibility, retraining),
but the two fields rarely meet (only Subramanya et al. as a precedent). **This is your
thesis identity:** join them. Say it plainly.

### 4. Aim and the three research questions (~1.5 min)
The platform in one sentence (ingests ENTSO-E, recalibrates and forecasts daily for DK1 and
DE, monitors and reconciles, keeps full provenance). Then the three RQs on screen,
verbatim: RQ1 forecasting comparison, RQ2 engineering trade-offs, RQ3 MLOps maturity. This
slide is the map for everything after it.

### 5. The system at a glance (~2.5 min)
Use the **host-level architecture figure** (`f1-architecture`). One Docker host, six
services (ClickHouse, Prefect server + worker, Prometheus, Grafana, Loki), ephemeral flow
containers. Trace the daily loop once: 06:00 refit-and-forecast, 18:00 reconciliation,
19:00 drift (the cadence figure `f5-daily-cadence` if you have room). This is the "what I
built" slide and it grounds RQ2/RQ3.

### 6. The three models and how they are compared (~2 min)
LEAR (one Lasso per hour), DNN (MLP, MIMO), Transformer (encoder-only) — one line each.
The **rolling-recalibration figure** (`f-recalibration`) to show the walk-forward ensemble.
State the replication framing in one sentence: faithful in specification, on current DK1
and DE data, compared in relative terms (rMAE) because the price regime differs from the
2016–2018 source-paper era. Feature-vector maths and the deviations table go to appendix.

### 7. RQ1 — accuracy and significance (~2.5 min)
The headline rMAE numbers (Tables 5.1 / 5.2) and the **GW heatmap** (`gw_heatmap_dk1/de`).
The finding in three beats, stated carefully:
- LEAR and the DNN are **statistically indistinguishable** on both markets (not "proven
  equal" — say it the careful way).
- Both **significantly beat** the Transformer; all three beat the weekly-naive baseline.
- Use the **calm-vs-renewable forecast-week figure** (`forecast_renew_dk1`) to explain
  *why* the Transformer is third (it smooths over negative-price hours and the scarcity
  peak).

### 8. RQ1 — cost, and ranking versus the papers (~1.5 min)
The cost inversion (Table 5.3): on GPU the DNN recalibrates in ~1 s/day vs LEAR's ~40–50 s,
so equal accuracy for far less compute. Then the ranking inversion: your order (LEAR ≥ DNN
≥ Transformer) inverts both source papers. Frame the cause as a **hypothesis** — most
consistent with the deep models' reduced tuning budget, not proof their architectures are
weaker (LEAR re-tunes itself by CV every day; the DNN got 30 trials vs the paper's 1500).

### 9. RQ3 — does the platform realise MLOps maturity? (~2.5 min)
The payoff of the system thread. The **maturity table** (Table 6.3) as the visual: eight of
Zarour's nine practices realised end-to-end, one (feedback loops) minimal. Then the
quantitative backing in three numbers:
- **ML Test Score 2.5**, bound by data-testing (the honest weak spot).
- **Provenance coverage** 66.7% across the window, 100% from the first continuously-deployed
  run.
- A re-run reproduced a logged forecast to **7×10⁻⁶ EUR/MWh**.
The insight to voice: the DevOps-style practices transferred easily; the ML-specific
data-testing discipline is where a single-developer MVP is weakest.

### 10. RQ2 — engineering trade-offs (~1 min)
One synthesis slide. Building the benchmark models into a scheduled, containerised pipeline
mostly **aligned** the needs of faithful replication and a single-host MVP (both favour
determinism and a single source of truth). Give one genuine tension you resolved: the
Transformer's native train-once scheme versus the daily-refit pipeline, where you chose
production consistency and deviated from the paper.

### 11. Since hand-in (~1 min) — optional but recommended
The format explicitly invites this. Strong, on-thesis content options (pick one or two):
- **A discovered operational finding:** the always-on 06:00 serving path needs the target
  day's prices, which are not published until midday, so the recorded live runs are
  deploy-gate and manual ones; the backtest results are unaffected, and the fix is a
  predict-path that does not require the target day's actuals. Mentioning this *shows the
  exact production-engineering maturity the thesis is about*. Keep it to one calm bullet.
- **Drift recalibration direction:** the detector flagged 49/49, so the next step is
  seasonally-matched reference windows and testing residuals, not raw prices.
See the note below before deciding whether to include the first one.

### 12. Conclusion (~1 min)
Restate the two-thread result in the contribution sentence (below). Eight of nine practices
realised; LEAR and DNN tied at the top, Transformer significantly weaker; the whole thing
reproducible and monitored. Do not introduce anything new here.

### 13. Future work (~1 min)
Four bullets, straight from §8.1: probabilistic forecasts (CRPS/pinball); full tuning plus
an `epftoolbox` side-by-side on the 2016–2018 data to separate replication error from
regime change; drift recalibration and broader market coverage; controlled reproduction of
the stochastic models.

### 14. Thank you / questions (~10 s)
Leave this slide up during questioning. A small "see appendix slides A1–A14" line reminds
you (and signals to the examiners) that you have backup material.

**Contribution sentence to memorise (use on slide 4 and slide 12):** "A reproducible,
monitored day-ahead EPF platform that serves three benchmark-faithful models, together with
a significance-tested comparison of those models and a quantified MLOps-maturity evaluation
of the platform that serves them — joining the EPF and MLOps literatures in one artifact."

---

## Appendix slides (after the "last" slide; shown during Q&A)

Each maps to a likely question (cross-referenced to `DEFENSE_PREP.md`). Build the ones you
can; prioritise A1–A5.

- **A1 — Feature vector → 247.** The 10n+7 derivation. (drills, "how do features work")
- **A2 — GW vs DM.** The regression Δ = φ'X + ε and the constant-instrument reduction to
  DM (Lago eq. 15). (R2 — your sharpest methodological question)
- **A3 — Statistical power / equivalence / multiplicity.** Why p=0.16 is
  indistinguishability not equality; no correction needed for the load-bearing results.
  (R1 — the top stats question)
- **A4 — Full deviations table** (Table 3.4). (R7, faithful-replication question)
- **A5 — DNN tuning budget.** 30 vs 1500 trials, the ~12-days-per-market wall-clock
  arithmetic. (R3)
- **A6 — MAE by hour of day** (`mae_by_hour_dk1/de`). (error-structure questions)
- **A7 — Full maturity table** (Table 6.3) and the Google-level rationale. (RQ3)
- **A8 — ML Test Score worksheet** (Appendix B summary). (R6, "why 2.5, why self-scored")
- **A9 — Reproducibility detail.** Provenance coverage table (Table 6.2) and the re-run.
  (R6, Gundersen–Kjensmo "what kind of reproducibility")
- **A10 — Drift.** 49/49, why over-flagging, the recalibration plan. (R8)
- **A11 — CI/CD pipeline** (`f3-cicd`). (P1, "how does deployment work")
- **A12 — Data plane** (`f2-data-plane`). (architecture deep-dive)
- **A13 — DNN and Transformer architectures** (`f-dnn-architecture`, `f-transformer-flow`).
- **A14 — Single-seed backtest** and seed-variance reasoning. (R5)

---

## On the "since hand-in" slide — a judgement call

The format note lists "discovered error" as welcome, and your supervisor reads with a
reproducibility/rigor eye, so a brief, confidently-framed discovered-issue slide tends to
*help* rather than hurt — it demonstrates the operational maturity that is literally your
RQ3 subject. The risk is that the examiners cannot see the 06:00 issue from the report, so
you would be introducing it. The mitigation is framing and brevity: one bullet, stated as a
post-submission finding with a known fix, with the explicit reassurance that the backtest
results in Chapter 5 are unaffected. If you are not comfortable raising it unprompted, keep
it as appendix slide and only show it if asked about live operation — but have it ready
either way, because answering "what did the platform forecast this morning?" honestly is
better than being vague.

---

## On a demo or video

Tempting but risky in 20 minutes. A live demo can fail on the projector and eats time. If
you want to show liveness, use a **20–30 second screen recording** or static screenshots of
the Grafana dashboards or a W&B run, placed in the appendix, not a live system. The format
note's warning ("be careful that it actually works") applies doubly here. Recommendation:
skip the live demo, keep one dashboard screenshot in appendix.

---

## Rehearsal and logistics checklist

- Rehearse the full talk out loud at least twice; time it; aim for 18 minutes.
- Memorise the opening 60 seconds (slides 1–2) verbatim — it settles the nerves.
- Memorise the contribution sentence and the three RQ one-line answers.
- Practise the two whiteboard-free explainers that double as appendix slides: GW-vs-DM, and
  the feature vector to 247.
- Export the deck to **PDF**. Put it on a USB stick, email it to yourself, and have it on a
  second device. Confirm it opens on a machine that is not yours.
- Arrive early for the projector setup window the format allows; test the external display.
- Have a printed copy of the headline numbers and the nine practices in your hand for Q&A.
