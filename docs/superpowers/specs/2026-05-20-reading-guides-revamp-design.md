# Reading Guides Revamp — Design

**Date:** 2026-05-20
**Scope:** The four paper-anchored reading guides in `researh_material/reading_guides/`:

- `lago_epf_benchmark_reading_guide.md`
- `weron_2014_reading_guide.md`
- `transformer_epf_reading_guide.md`
- `mlops_best_practices_reading_guide.md`

**Out of scope:** `forecasting_strategy_and_bottlenecks.md` (topic synthesis, not a paper guide) and `mlops_implementation_plan.md` (progress log, not a reading guide). Both stay where they are.

---

## Problem

The current paper guides open with a "How to Read This Paper" priority table and dive straight into dense paper-vs-code mapping tables. They lack the three things the reader actually needs first:

1. **A triage** — should I re-read this paper right now, or skip it?
2. **A synopsis** — what is this paper, in 2–3 sentences?
3. **Headline findings** — what did it actually conclude?
4. **Project relevance** — why does this matter for what I'm building?

The user reaches for these guides as a 5-minute orientation *before re-opening the PDF*. Today's guides force them to skim a 200+ line table to recover information that should be at the top.

The `forecasting_strategy_and_bottlenecks.md` document demonstrates the writing style that works: prose-driven, narrative, weaves literature + code + recommendations together. But it's topic-anchored, not paper-anchored, so it's a different kind of artifact — not a template to copy wholesale.

---

## Goals

- Add a triage block and prose front-matter at the top of each paper guide.
- Preserve all existing content as a reference appendix below the new sections.
- Keep guides paper-anchored (their purpose is to prepare for re-reading the PDF).
- Triage scenarios reference subsystems and topics, not specific file paths — so the guides stay accurate as the codebase evolves.

## Non-goals

- Restructuring the bottlenecks doc or MLOps implementation plan.
- Adding new content beyond what's needed for the four front-matter sections.
- Standardising the appendix sections — each paper has paper-specific structure (Lago's 13-point checklist, Transformer's two-approaches comparison) that should stay as-is.

---

## New Front-Matter Structure

Every paper guide gets four new sections at the top, before the existing content. The existing "How to Read This Paper" priority table moves down to mark the start of the appendix.

### Section 1 — Do I Need This Paper Right Now?

A short triage block. Two elements:

**Importance: X/10** — a single number capturing the paper's standing utility for this project, with a one-line justification. Calibration scale:

- **9–10**: Load-bearing. The codebase would not exist in its current form without it. Re-read whenever stuck.
- **7–8**: High value, scoped. Critical *if* you're working on a topic it covers — otherwise skip.
- **5–6**: Framework or context value. Useful for orienting and vocabulary, but its specific content is largely internalised into other docs.
- **3–4**: Historical / supplementary. Read for lineage, not for day-to-day decisions.
- **0–2**: Cite but don't re-read.

Be honest. The score should reflect what re-reading actually gives the user *today*, not the paper's academic prestige.

Then three prescriptive bullets:

- **Read this if** [list of concrete scenarios — what kind of work triggers a re-read]
- **Skip if** [what kind of work does *not* benefit from this paper]
- **Come back when** [what future project milestone makes this worth re-reading]

Scenarios reference subsystems and topics (e.g. "LEAR", "Transformer model", "Phase 6 MLOps work"), not file paths. The reader who answers "no" closes the file here.

### Section 2 — What This Paper Is

A small metadata header (authors, year, venue, scope/page count) followed by a 2–3 sentence prose synopsis. Replaces the current bare `**Paper:**` line at the top.

Synopsis covers: what problem the paper tackles, what approach it takes, what its place in the literature is (e.g. "foundational review", "answered Weron's call", "next-step model beyond DNN").

### Section 3 — Headline Findings

Three to five numbered findings. Each is one sentence stating the conclusion, followed by one sentence of supporting evidence (a number from a results table, a quote, or a comparison). These are the things the reader would repeat to someone asking "what did this paper find?"

Not section summaries. Actual conclusions with their evidence inline.

### Section 4 — Why You Need This For Your Project

A 150–250 word prose paragraph (or two). Ties the findings to current codebase state: what's already in the repo because of this paper, what's missing, what decisions are still open. Subsystems and concepts can be named freely; specific file paths only where they are unambiguous and load-bearing.

This is the narrative complement to the existing mapping tables — it tells the reader *why* the mappings exist before they scan the tables themselves.

### Then: Appendix

The existing content — "How to Read This Paper" priority table, mapping tables, scorecards, glossary, per-section notes — stays below as a reference appendix. Nothing is deleted.

A short marker line introduces the appendix:

> ---
>
> *The sections below are the reference appendix: detailed mappings, per-section notes, and the glossary. Use them when you have the PDF open.*

---

## Per-Paper Sketches

### Lago 2021 (EPF Benchmark)

- **Importance: 9/10.** The codebase *is* this paper's LEAR. Every modelling-layer design choice — 247 features, four calibration windows, daily refit, rMAE, weekly-naive baseline — traces here. Not a 10 because Weron 2014 is the conceptual ancestor and because most of this paper is already faithfully captured in the existing mapping tables; re-reading the PDF beyond the first time has diminishing returns.
- **Do I Need This?** Read if working on LEAR config tuning, evaluation metrics (especially rMAE / DM test), or comparing your numbers against the published benchmark. Skip if working on ingestion, infrastructure, or the Transformer model directly. Come back when DK1 results are stable and you want to extend to a second market.
- **Headline Findings:** DNN ensemble beats LEAR ensemble in all 5 markets (rMAE 0.407 vs 0.420 on NordPool); LEAR is 50–100× faster per recalibration; ensembles always help; MAPE is misleading near zero prices; statistical testing is essential for any "better than" claim.
- **Project Relevance:** The codebase's LEAR is a bit-identical reproduction of this paper's 247-feature spec. The calibration-window ensemble and `refit_interval_days=1` come straight from §4.4 / §5.6. Open gaps: no DM/GW test, single market only, no asinh transform, no computation-time tracking. The 13-point checklist (appendix) gives a current score of 8 PASS / 2 PARTIAL / 3 FAIL. **Critical note:** the paper's DNN specification (Tree Parzen Estimator + 1500-iteration HP search + 4-DNN ensemble) is substantially heavier than the stubbed `DNNModel` will likely become — treat the DNN spec as reference, not gospel.

### Weron 2014 (EPF State-of-the-Art Review)

- **Importance: 5/10.** Foundational *intellectually* — every modelling decision in this codebase has Weron's fingerprints. But the paper is from 2014, the deep-learning section is dated, and Lago 2021 supersedes its concrete recommendations. Score reflects its standing utility for re-reads, not its historical importance. Read it once carefully; after that, the reading guide's headline findings and glossary are enough for 90% of situations.
- **Do I Need This?** Read if explaining the project's lineage, drafting documentation, picking a metric, or asking whether annual seasonality / reserve margin features are worth adding. Skip if you need implementation-level detail — Lago 2021 and the Transformer paper are tighter. Come back for questions that feel older than 2021 (probabilistic forecasting, regime-switching, multivariate factor models).
- **Headline Findings:** Five model families taxonomy still holds; forecast combination ("a forgotten art") is the highest-leverage technique; seasonality handling is the most neglected modelling problem; MAPE is unreliable for EPF; no industry-standard metric exists — hence the call for a benchmark that Lago 2021 later answered.
- **Project Relevance:** This is the foundational reference — the entire pipeline traces back to it. Family 4 (statistical) → LEAR; Family 5 (CI) → DNN/Transformer; §4.3 (combining forecasts) → the calibration-window ensemble. The paper's evaluation guidelines (§4.5.2) predate Lago 2021's 13-point checklist and the codebase satisfies most of them. The one Weron lever still untouched: explicit annual seasonality via `CyclicalTimeTransformer` (exists but not in LEAR defaults). **Critical note:** the §3.9 (neural networks) chapter is the most dated part of the paper — skip it; the Transformer paper covers the modern state.

### Llorente & Portela 2025 (Transformer for EPF)

- **Importance: 7/10.** High value *conditionally* — critical when Transformer work is active, low when it isn't. Score reflects the conditional ceiling because the paper's design choices (dual-input, renormalisation, no ensemble) are the live design questions for the next model. Drops to 4 once the Transformer is stable and tuned.
- **Do I Need This?** Read if implementing the Transformer model, deciding daily-refit vs. renormalisation, picking sequence length / embedding dim, or writing the DM test. Skip if working on LEAR, ingestion, or any non-modelling layer. Come back once a Transformer prototype is running and you want to tune hyperparameters.
- **Headline Findings:** Pure-encoder Transformer beats DNN ensemble on 4/5 markets (NordPool MAE 2.33 vs 3.40); dual-input architecture (exogenous + raw price matrix) outperforms flattened lag features; train-once + renormalisation is the paper's design choice instead of daily refit; DM test p-values ≈ 0 for 4/5 markets.
- **Project Relevance:** This is the proposed *next* model — sits between the implemented `LearModel` and the stubbed `DNNModel`. Two key design decisions are still open: flat vs. dual-input features (Approach A vs B in the existing appendix), and refit cadence vs. renormalisation. The DM test is a blocking dependency before any claim about Transformer beating LEAR. Existing `CyclicalTimeTransformer` and `MeanWeeklyForecastTransformer` are deliberately positioned for the deep-model path. **Critical note:** the paper is a single arXiv preprint with one author group's results — independent reproduction is thin. Treat the "20–50% MAE reduction vs DNN" claim with appropriate scepticism until the codebase reproduces it.

### Zarour et al. 2025 (MLOps Best Practices SLR)

- **Importance: 5/10.** It's a *secondary* source — an SLR summarising 45 other papers. The P1–P9 framework is genuinely useful and now lives in `mlops_implementation_plan.md`. Once the framework is internalised, re-reading the paper itself gives little marginal value; the implementation plan is closer to the code and is the better daily reference.
- **Do I Need This?** Read if prioritising the next MLOps phase, justifying a maturity-level claim to a stakeholder, or evaluating whether to adopt a new tool (W&B, DVC, MLflow, etc). Skip if working inside a single subsystem — `mlops_implementation_plan.md` is already mapped to P1–P9 and is closer to the code. Come back when Phase 6+ work begins (feedback loops, automated retraining triggers).
- **Headline Findings:** Nine best practices (P1–P9) consolidated from 45 articles; CI/CD (P1) is the most-cited practice (28/45 papers); automation (C4) and monitoring (C6) are the most-cited challenges; Google's 3-level model is the most actionable maturity scale; "no single tool realises a fully automated MLOps workflow" — composition is required.
- **Project Relevance:** The codebase's MLOps roadmap is structured around the P1–P9 framing. Current maturity: Google Level 1 / Microsoft Level 1-2. Strong on P3 (reproducibility) and P7 (metadata tracking via `algo.experiment_runs`). Weak or missing on P5 (collaboration), P8 (monitoring — partial via `drift.py`), and P9 (feedback loops). The `mlops_implementation_plan.md` is the live execution doc; this guide is the framework reference. **Critical note:** the paper's tool recommendations are biased toward big-vendor ecosystems (Kubeflow, SageMaker, TFX) — Prefect + ClickHouse + Loki + Evidently is a perfectly defensible alternative stack that the paper underrepresents.

---

## Editing Plan (mechanical)

For each of the four guides:

1. Insert the four new sections (§1–§4 above) immediately after the current header line.
2. Add the appendix marker line ahead of the existing "How to Read This Paper" table.
3. Leave the existing content otherwise untouched. No deletions, no restructuring of mapping tables or per-section notes.

Each guide grows by roughly 60–120 lines depending on synopsis density. Total net addition across all four guides: ~300–400 lines.

---

## Style Constraints

- **Triage bullets:** prescriptive, present tense, 1–2 lines each. Reference subsystems and concepts ("LEAR", "Transformer model", "Phase 6 MLOps work"), not file paths.
- **Synopsis:** 2–3 sentences. State the paper's question, approach, and place in the literature.
- **Findings:** numbered list, one finding per item. State the conclusion, then the evidence in the same item (parenthetical numbers, quoted phrases, or comparisons).
- **Project relevance:** prose, not bullets. 150–250 words. Cross-link to existing appendix tables rather than restating them.
- **No emojis. No marketing language.** Match the existing terse house style.

---

## Open Questions

None. Triage scenarios are subsystem-level. Existing content is preserved verbatim. Each paper guide can be revised independently.
