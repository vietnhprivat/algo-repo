# Report Handoff — Finishing the Thesis After the Final Benchmark

> **Audience.** You (or a future session) finishing the written thesis now that
> the six-model benchmark is done. Everything the modelling chapters need is
> computed, pinned, and committed on branch `final-model-experiments`
> (**PR #87**). This file tells you what shipped, what numbers exist and where,
> what prose remains, and how to compile. Last updated 2026-06-05.

---

## 1. What shipped (done — don't redo)

- **Six benchmark runs**: LEAR / DNN / Transformer × DK1 / DE, one shared hourly
  test window **2025-10-24 → 2026-05-31**, paper-exact features, all `--track`ed
  to `algo.experiment_runs`.
- **Pipeline additions** (all tested, 450 pytest pass, ruff clean):
  - `ExperimentConfig.exogenous_aggregates` — summed exogenous series (DK1 Wind =
    onshore+offshore; DE Renewables = wind+solar) matching the papers' 2-exogenous spec.
  - `ExperimentConfig.resample_to_hourly` — both markets modelled at hourly (24p);
    DE (15-min) and DK1 (15-min since 2025-10-01) downsampled to an hourly mean.
  - Wind/solar history backfilled to 2022-03 for both areas.
  - DNNs re-tuned (30-trial TPE) on the new features.
- **Report artifacts** (committed): `Report/metrics/model_comparison.md` (headline
  metrics, GW p-value matrices, cost, vs-paper — **the source of truth for numbers**),
  `Report/metrics/run_timings.md` (per-run wall-clock).
- **Two new chapters**: `Report/chapters/methods_models_draft.tex` (`ch:methods-models`)
  and `results_models_draft.tex` (`ch:results-models`), both wired into `main.tex`
  and compiling. 4 new bib entries added.
- **Lago 13-point checklist: 13/13 PASS** (#2 closed) in
  `researh_material/reading_guides/lago_epf_benchmark_reading_guide.md`.

## 2. The results (source of truth: `Report/metrics/model_comparison.md`)

rMAE on common test days (DK1: 187, DE: 176):

| Market | LEAR | DNN | Transformer | Naive |
|---|---|---|---|---|
| DK1 | **0.469** | 0.482 | 0.543 | 1.000 |
| DE  | **0.376** | 0.388 | 0.420 | 1.000 |

**GW significance (the defensible reading — frame the prose around this):**
- **LEAR ≈ DNN** — LEAR numerically best, but the difference is **not significant**
  (DK1 p=0.16, DE p=0.19). Mirrors Lago's own "DNN edge often insignificant."
- **Both significantly beat the Transformer** (DK1 p≤0.0005, DE p≤0.012).
- **All significantly beat weekly-naive** (p=0).
- **Cost (GPU):** DNN ~1 s/recalibration-day vs LEAR ~40–50 s — statistically tied
  accuracy at ~1/40th the cost (hardware-driven inversion of Lago Table 4).
- **Ranking inverts both papers** (Lago: DNN≥LEAR; Llorente: Transformer≥DNN). The
  honest cause is that the deep models are **under-optimised relative to LEAR here**,
  not inherently weaker — see caveats §6.

## 3. Report chapter inventory (`Report/main.tex` assembly order)

| Chapter | Label | State |
|---|---|---|
| frontmatter | — | **title/author TODO** + abstract headline pending (§4) |
| introduction | — | prose exists |
| background | — | prose exists |
| methods_models_draft | `ch:methods-models` | **scaffold (tables+bullets)** — expand bullets to prose |
| system_implementation | `ch:system-implementation` | prose exists |
| evaluation_framework_draft | `ch:eval-framework` | scaffold (tables+bullets) |
| results_models_draft | `ch:results-models` | **scaffold with FINAL numbers** — expand bullets to prose |
| results_system_draft | `ch:results-system` | scaffold (tables+bullets) |
| discussion | — | prose exists + **RQ1 numbers pending (§4)** |
| conclusion | — | prose exists + **headline pending (§4)** |
| appendices | — | — |

## 4. Pending placeholders — exact locations + ready-to-paste facts

These were left waiting on the benchmark. I did **not** auto-write them (they're
your thesis voice), but here is the factual content to drop in and reword:

- **`Report/chapters/discussion.tex:20-23`** (RQ1 headline). Facts: "On both DK1 and
  DE, LEAR achieved the lowest rMAE (0.469 / 0.376), but the Giacomini–White test
  finds it statistically indistinguishable from the DNN (p=0.16 / 0.19); both
  significantly outperform the Transformer (p≤0.012) and all three beat the weekly
  naïve. The Lago ranking (DNN≥LEAR) is reproduced only as a statistical tie; the
  Llorente Transformer advantage does not replicate under our un-retuned, refit-based
  setup."
- **`Report/chapters/conclusion.tex:22-23`** (one-sentence headline). Facts: "LEAR
  remained the most accurate and the DNN its statistical equal, while the Transformer
  trailed — inverting the source papers' rankings, attributable to the deep models'
  reduced tuning budget rather than architecture."
- **`Report/chapters/frontmatter.tex:30`** (abstract forecasting headline). One
  sentence: "LEAR and a tuned DNN ensemble are statistically tied for best, both
  beating a pure Transformer and a naïve baseline across two European markets."
- **`Report/chapters/frontmatter.tex:2`** (title/author/degree) — genuinely yours to set.

## 5. What remains to finish (writing, no compute)

1. Fill the four placeholders in §4.
2. **Expand the two modelling scaffolds to prose.** `methods_models_draft.tex` and
   `results_models_draft.tex` are deliberately structure-first (tables + bullets);
   each bullet is a topic sentence to expand. The tables and numbers are final —
   don't change them; the LaTeX table blocks also live in `model_comparison.md` if
   you need to regenerate.
3. (Optional) the other scaffolds (`evaluation_framework_draft`, `results_system_draft`)
   are system-side and were already drafted before this work.

## 6. Caveats / threats to weave in (honest limitations)

- **Deep models under-tuned vs LEAR**: DNN used 30 TPE trials (Lago: 1500); the
  Transformer reused the paper's Nord-Pool hyperparameters un-retuned and was adapted
  into a calibration-window + weekly-refit pipeline rather than its native
  train-once+renormalise. This is the most likely cause of the ranking inversion —
  state it plainly. (Also in `methods_models_draft.tex` Table `tab:mm-deviations`.)
- **Single seed** for the Transformer (DNN has a 4-seed ensemble); seed variance unquantified.
- **31-week test window** (papers use 1–2 years), data-constrained (price history starts 2022-03).
- **Hourly downsampling** of 15-min markets (arithmetic mean) — comparability choice, not native.
- **DK1 has ~2 ENTSOE wind gap days** in the test window; dropped from all DK1 models
  identically, so paired tests stay valid (see methods chapter data-gap note).
- The **cost inversion is hardware-driven** (GPU nets vs CPU LassoCV) — don't claim it
  as a property of the markets.

## 7. Provenance / reproducibility

- Per-run metadata: `algo.experiment_runs` (`training_duration_seconds`, git_sha,
  data window, model_artifact_id). Tuning trials: `algo.hyperparam_trials`
  (studies `dk1_dnn_tune_v5_paperexog`, `de_dnn_tune_v5_paperexog`).
- Wall-clock: `Report/metrics/run_timings.md`. Raw per-run CSVs in `results/`
  (gitignored — regenerate with `forecast-cli backtest <config> --track`).
- Regenerate comparison tables: `uv run python -m scripts.report.extract_model_comparison`
  and `... extract_run_timings`.
- Deterministic re-run demo: `scripts/report/reproduce_run.py` (LEAR).

## 8. How to compile

```bash
cd Report
latexmk -pdf main.tex      # run twice — cross-refs to tables need a second pass
```
Full thesis = 54 pages, compiles with 0 errors / 0 undefined refs after the second
pass. Per-chapter proofs: `latexmk -pdf <chapter>_standalone.tex` (cross-chapter
refs show as `??` in standalone — expected).

## 9. Future work (already listed in `results_models_draft.tex` §future)

Full-budget DNN tuning; per-market Transformer search; native Transformer
train-once+renormalise path; 1456-day LEAR window when data depth allows;
LARS+AIC λ-selection; probabilistic extension (pinball/CRPS); per-hour DM profiles.
