# Final Model Experiments & Modelling-Side Report — Design

**Date:** 2026-06-04
**Status:** Approved by owner (brainstorming session 2026-06-04)
**Goal:** Run the paper-faithful final benchmark — LEAR vs DNN vs Transformer on DK1 and DE
over the newest data — and produce the modelling-side thesis chapters that compare the
results against Lago et al. (2021) and Llorente & Portela (2025).

---

## 1. Framing

The papers' absolute errors (2016–2018 test periods) are not comparable to 2026 price
regimes. The valid comparison, and the one the report makes, is:

1. **Methodology replication** — same model specs, features, recalibration scheme,
   metrics, and statistical tests as the papers, run on current data.
2. **Relative comparison** — rMAE (designed by Lago et al. exactly for cross-period /
   cross-market comparison) and **model rankings** vs the papers' reported tables.
3. **Head-to-head significance** — paired DM/GW tests across the three models + the
   weekly-naive baseline, per market, on identical test days.

## 2. Decisions made (with rationale)

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| D1 | Shared test window | **2025-10-24 → 2026-05-31** (~31 weeks) | Longest window keeping existing DNN tuning ex-ante (val ends 2025-10-23); paired DM/GW tests require identical windows across all six runs. Full-year window would contaminate DNN tuning → re-tune on shifted val. |
| D2 | Exogenous features | **Paper-strict.** DK1: TotalLoad + Wind (onshore+offshore). DE: TotalLoad + Renewables (wind on+off + solar) | Verified from Lago §3: NP = load + wind generation forecast; EPEX-DE = load + aggregated wind & solar forecasts. Llorente & Portela reuse the same datasets. |
| D3 | DNN re-tune | **Yes, both markets, 50 trials** | Feature change alters input dimension → existing HPs no longer ex-ante-valid. Lago tunes per dataset. Val window 2025-01-01 → 2025-10-23 (42 weeks) already ex-ante for D1. |
| D4 | Aggregation mechanism | **Config-driven loader aggregate** (`exogenous_aggregates` field, summed in `load_exogenous_series()`) | Raw curves stay source-of-truth; all three model paths see identical features; choice is git-visible in config. Rejected: derived curves in DB (computed data in `algo.forecasts`), separate columns (breaks 247-feature paper spec). |
| D5 | DNN calibration window | **Keep 730** | Cheaper tuning + backtests. Documented deviation from Lago's 4-year window (4y is data-infeasible anyway; dataset starts 2022-03-10). |
| D6 | Results durability | **ClickHouse `--track` only**; commit generated `Report/metrics/model_comparison.md`, not raw CSVs | Owner preference; consistent with existing metrics-artifact pattern. |

## 3. Verified facts the design rests on

- Data complete 2022-03-10 → 2026-06-03 for both markets. DK1 pipeline resolves to
  **hourly** (24 periods, 1,547 complete days — inner join with hourly TotalLoad drops
  the 15-min price points introduced 2025-10-01). DE resolves to **15-min**
  (96 periods, 1,539 complete days).
- Wind/Solar curves exist only since 2026-04-29 → **backfill required** to 2022-03-10.
  `data-cli entsoe backfill wind-solar` exists.
- Generation history starts 2023-01-01 — under paper-strict features it is no longer
  used, removing the truncation it would have caused for early test days' 1092-day windows.
- `val_start_date`/`val_end_date` feed only the `tune` path; the backtest uses
  `split_by_dates` (training = everything before test start). Shifting/keeping val dates
  does not change backtest results.
- DM + GW tests implemented (`evaluation/statistical_tests.py`, `build_dm_matrix`).
- Existing results: DK1 only, stale configs; DE none. All six runs must be (re)run.
- These configs are loaded by production `daily-forecast` deployments → the feature
  change reaches production on next deploy (intended: paper-strict features in prod).

## 4. Experiment matrix

| Config | Model | Test window | Calib. windows | Refit | Exogenous |
|---|---|---|---|---|---|
| `dk1_lear` | LEAR ensemble | 2025-10-24 → 2026-05-31 | [56, 84, 1092] | 1d | TotalLoad + Wind |
| `dk1_dnn` | DNN ensemble ×4 | same | [730] | 1d | TotalLoad + Wind |
| `dk1_transformer` | Transformer | same | [1092] | 7d | TotalLoad + Wind |
| `de_lear` | LEAR ensemble | same | [56, 84, 1092] | 1d | TotalLoad + Renewables |
| `de_dnn` | DNN ensemble ×4 | same | [730] | 1d | TotalLoad + Renewables |
| `de_transformer` | Transformer | same | [365 → attempt 1092] | 7d | TotalLoad + Renewables |

Notes:
- `de_transformer`: with exog history extended to 2022-03 (wind+solar backfill), usable
  sequence rows should grow well past the previous ~481; attempt 1092, fall back to max
  feasible, document the final value.
- Transformer `n_exog` stays 2; `model_params` keep the Llorente & Portela values
  (their NP search optimum) — per-market Transformer re-tuning is documented future work.
- LEAR/DNN val dates: keep 42-week val windows ending 2025-10-23 in all configs
  (`2025-01-01 → 2025-10-23` style) for `tune` compatibility and documentation.

## 5. Work plan

### Phase 1 — Data (unattended, ~1h)
1. `data-cli entsoe backfill wind-solar -a DK1 -s 2022-03-10 -e 2026-06-04`
2. Same for `-a DE`
3. Verify per-day completeness of WindOnshore/WindOffshore/Solar for both areas
   (row counts per day, no gaps inside 2022-03-10 → now); `OPTIMIZE TABLE algo.forecasts FINAL`

### Phase 2 — Code (small, tested)
4. `ExperimentConfig.exogenous_aggregates: dict[str, list[str]] | None = None`
5. `load_exogenous_series()` / `load_dataset()`: fetch member curves, sum into the
   aggregate column (native-resolution sum, then the existing join logic applies)
6. Tests: fake-client loader tests for the aggregate path (sum correctness, missing-curve
   error, schema), config-level test
7. Update all six configs per §4 (window, exog aggregates, val dates)

### Phase 3 — Sanity + LEAR (fast)
8. Run `backtest dk1_lear --track` and `backtest de_lear --track`; verify feature counts
   (DK1: 4×24 + 2×3×24 + 7 = 247 exactly; DE: 96-period analog), inspect metrics for sanity

### Phase 4 — DNN tuning (overnight ×2)
9. `forecast-cli tune dk1_dnn -n 50`, then `tune de_dnn -n 50` (val ends 2025-10-23)
10. Commit best params into configs (existing convention, comment with study name + val MAE)

### Phase 5 — Heavy backtests (overnight, sequential)
11. `backtest dk1_dnn --track`, `backtest de_dnn --track` (~220 days × 4 nets, daily refit)
12. `backtest dk1_transformer --track`, `backtest de_transformer --track` (~32 weekly refits each)

### Phase 6 — Analysis
13. New `scripts/report/extract_model_comparison.py` (mirrors `extract_metrics.py`):
    reads the six runs' outputs → writes `Report/metrics/model_comparison.md` containing:
    - per-market headline table (MAE/RMSE/sMAPE/rMAE × LEAR/DNN/Transformer/naive)
    - per-market GW p-value matrix (via `build_dm_matrix`)
    - computation-cost table (training seconds per daily recalibration, Lago Table 4 analog)
    - paper-comparison table (our rMAE + rankings vs Lago Table 3 NP/DE rows and
      Llorente Table 5 NP/DE rows, with the different-period caveat stated)
    - LaTeX-ready versions of each table
14. (Nice-to-have) per-hour DM profile

### Phase 7 — Report writing
15. **NEW** `Report/chapters/methods_models_draft.tex` (label `ch:methods-models`):
    model specs as implemented; paper-exact features incl. aggregates; split/window table;
    recalibration scheme; metrics + DM/GW; tuning protocol; **deviations-from-paper table**:
    - 31-week test vs Lago's 2-year recommendation (data-constrained; stated)
    - 50 Optuna trials vs Lago's 1500 TPE iterations
    - calibration windows [56, 84, 1092] without 1456 (dataset starts 2022-03)
    - DNN window 730d vs Lago's 4 years
    - LassoCV(TimeSeriesSplit) vs LARS+AIC for λ
    - architecture-only DNN search space (no binary feature-selection HPs)
    - DK1 prices = hourly grid sample of a 15-min market after 2025-10-01
    - Transformer adapted into the calibration-window pipeline, weekly refit, vs the
      paper's train-once + renormalize
    - DE Transformer calibration window if < 1092
16. **NEW** `Report/chapters/results_models_draft.tex` (label `ch:results-models`):
    the §13 tables; figures (GW heatmap, sample forecast week per market, per-hour MAE
    profile); discussion vs both papers; computation-cost section
17. Wire cross-references in `evaluation_framework_draft.tex` and
    `results_system_draft.tex` (labels already referenced there)
18. `references.bib`: add `llorente2025`, `uniejewski2018` (asinh VST),
    `diebold1995`, `giacomini2006`
19. Standalone-compile wrappers for the two new chapters (existing pattern)

### Phase 8 — Verification & wrap-up
20. Full `pytest tests/ -v` + ruff green
21. Refresh `lago_epf_benchmark_reading_guide.md` scorecard (checklist #2 PARTIAL → PASS)
22. PR per branch convention; after merge, CD deploys configs (feature change goes live)

## 6. Estimated calendar

~4–6 days wall-clock, dominated by unattended overnight compute (2 tune nights,
2 DNN backtest nights, transformer runs interleavable). Code + writing work is
parallelizable with the compute.

## 7. Out of scope (named as future work in the report)

- 1456-day calibration window; LARS+AIC λ-selection
- Probabilistic forecasting (pinball/CRPS)
- Transformer per-market hyperparameter search
- epftoolbox side-by-side reruns on the original 2016–2018 datasets
- Per-hour DM profile if time does not permit (nice-to-have)

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| ENTSOE wind/solar backfill has gaps for 2022–2023 | Phase 1 verification step before any code work; if a curve is structurally missing, fall back per-market (e.g. DK1 wind = onshore only) and document |
| DE Transformer still data-starved after backfill | Attempt 1092, fall back to max feasible, document (existing footnote pattern) |
| DNN tune/backtest runtime explodes | Window already kept at 730 (D5); runs staged overnight; LEAR results land first so report writing can start |
| Aggregate sum hits misaligned timestamps (15-min vs hourly members) | Sum at native resolution before join; loader tests cover both resolutions |
| Production behavior changes on deploy | Intended (paper-strict features); noted in PR description |
