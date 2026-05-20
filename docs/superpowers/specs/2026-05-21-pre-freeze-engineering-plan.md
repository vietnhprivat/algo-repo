# Pre-Freeze Engineering Plan

**Date:** 2026-05-21
**Context:** Bachelor's thesis enters a 2-week writing-focused phase. The
codebase will be frozen except for the small set of engineering items
documented here, which exist because they materially affect what the
thesis can claim. After this plan ships, no further engineering work
should land unless it is a bug fix surfaced by experiments.

## Goals

1. Land the one engineering feature still required to make the P3
   ("Ensuring reproducibility") claim airtight: git SHA capture in
   experiment metadata.
2. Clean up dead code, orphan configs, and tracked artefacts so the
   repository can be screenshotted and quoted in the thesis without
   asterisks.
3. Refresh the Lago 13-point checklist reading guide so the thesis can
   lift the new scorecard directly.

Out of scope: any new model, any new feature, Prometheus/W&B integration
(both already documented as deferred-with-rationale in
`researh_material/reading_guides/mlops_implementation_plan.md`), DNN
production deploy.

## PR breakdown

Three independent PRs, file-level disjoint, mergeable in any order.

### PR 1 — `chore/pre-freeze-cleanup`

Combined cleanup. Pure deletions, no new logic.

**Changes:**
- Delete orphan YAML configs:
  - `configs/default.yaml`
  - `configs/experiment_7day_calibration.yaml`
  - `configs/experiment_14day_calibration.yaml`
  All three reference `src/backtesting/src/backtesting/data/DE_data.csv`,
  which is from a `backtesting` workspace package that no longer exists.
  `config_loader.py` only loads `.py` configs — these are unwired.
- Remove dead `algo.energy_prices` code:
  - `create_energy_prices_table()` in `infrastructure_clickhouse/queries.py`
  - `EnergyPriceObservation` domain class (and any re-exports)
  - `insert_energy_prices_batch()` in `infrastructure_clickhouse/ingest.py`
  - Any tests referencing them
  The ClickHouse table itself is not dropped — it's empty, harmless, and
  `IF NOT EXISTS` migrations remain safe. The PR description should call
  this out.
- Remove stub models from registry and exports:
  - Delete `src/price_forecasting/src/price_forecasting/models/lightgbm_model.py`
  - Delete `src/price_forecasting/src/price_forecasting/models/catboost_model.py`
  - Remove their entries from `MODEL_REGISTRY` in `models/__init__.py`
  - Remove their re-exports from `price_forecasting/__init__.py`
  Decision: delete files entirely (no gravestone stubs).
- Remove `AggregatedLagTransformer`:
  - Delete the class body in `src/price_forecasting/src/price_forecasting/data/transformers.py`
  - Remove the re-export from `data/__init__.py`
- `.gitignore` `results/`:
  - Append `results/` to `.gitignore`
  - `git rm --cached results/*.csv results/*.json` for currently-tracked outputs
- Fix stale REPO_OVERVIEW references:
  - Replace `[56, 84, 730, 1092]` with `[56, 84, 1092, 1456]` to match
    the actual `configs/dk1_lear.py`
  - Remove `LightGBMModel` and `CatBoostModel` from the `MODEL_REGISTRY`
    table and any "Wrapped via GBTModel" prose (only `XGBoostModel`
    remains under `GBTModel`)
  - Remove `AggregatedLagTransformer` from the feature-transformer table

**Validation:**
- `pytest tests/ -v` passes (must remove tests for deleted symbols)
- `ruff check` clean
- `git grep -E 'energy_prices|LightGBMModel|CatBoostModel|AggregatedLagTransformer'` returns no production references

**Risk:** Low. Pure deletions. Failure mode is a forgotten test, caught by pytest.

---

### PR 2 — `feat/git-sha-experiment-tracking`

P3 evidence — adds a `git_sha` column to `algo.experiment_runs` and wires
the value through the build + runtime path.

**Changes:**
- New migration `migrations/010_alter_experiment_runs_add_git_sha.sql`:
  ```sql
  ALTER TABLE algo.experiment_runs
    ADD COLUMN IF NOT EXISTS git_sha String DEFAULT '';
  ```
  (Use the next free migration number at implementation time —
  `010` here is illustrative.)
- `Dockerfile` and `Dockerfile.worker`:
  - `ARG GIT_SHA=""` near the top
  - `ENV GIT_SHA=${GIT_SHA}` so it survives into the running container
- `.github/workflows/cd_deploy.yml`:
  - Pass `--build-arg GIT_SHA=$(git rev-parse HEAD)` on the `docker build`
    invocation that already runs over SSH
- `src/infrastructure_clickhouse/src/infrastructure_clickhouse/ingest.py`:
  - `insert_experiment_run` gains a keyword-only `git_sha: str = ""` param,
    threaded into the existing dict + schema (Polars `pl.Utf8`)
- `src/forecast_cli/src/forecast_cli/tracking.py`:
  - `track_prediction` and `track_backtest` read `os.environ.get("GIT_SHA", "")`
    and forward it to `insert_experiment_run`
- One unit test under `tests/forecast_cli/` that monkey-patches
  `GIT_SHA=deadbeef` and asserts the column round-trips via a fake
  ClickHouse client.

**Convention (documented in CLAUDE.md as part of this PR):**
- Capture is **env-driven**: production sets `GIT_SHA` at image build time
  (via `cd_deploy.yml`). Local runs leave it unset → empty string.
- This avoids stamping dirty working trees with misleading SHAs during
  ad-hoc local backtests.

**Validation:**
- `pytest tests/ -v` passes
- Migration applies cleanly against the live DB:
  `uv run python -m infrastructure_clickhouse.migrations.run_migrations`
- After the next CD run, this query returns real 40-char SHAs:
  ```sql
  SELECT DISTINCT git_sha FROM algo.experiment_runs FINAL
  WHERE created_utc > now() - INTERVAL 1 DAY
  ```

**Risk:** Medium — touches the deploy pipeline. Mitigation: the column
defaults to `""`, so any in-flight run between migration apply and image
rebuild stays valid.

---

### PR 3 — `docs/refresh-lago-checklist-scorecard`

Pure doc rewrite of
`researh_material/reading_guides/lago_epf_benchmark_reading_guide.md`.

**Score updates** (table at section "The Paper's 13-Point Checklist vs Your Codebase"):

| # | Requirement | Old | New | Evidence to cite |
|---|---|---|---|---|
| 3 | Computational cost evaluated | FAIL | PASS | `training_duration_seconds` column in `algo.experiment_runs` (migration 006); per-run timing captured by `LiveRunner.run_live_with_metadata` |
| 5 | Multiple markets tested | FAIL | PASS | `configs/de_lear.py` exists and is deployed via `deploy_forecast.py::FORECAST_CONFIGS = ["dk1_lear", "de_lear"]` |
| 7 | Statistical testing for significance | FAIL | PASS | `price_forecasting/evaluation/statistical_tests.py` implements `diebold_mariano` + `giacomini_white_multivariate`; `compute_dm_pvalue_matrix` in `evaluation/summary.py` for >2 models |
| 9 | Hyperparameters estimated ex-ante | PARTIAL | PASS | `val_start_date`/`val_end_date` declared in both production configs; `split_train_val_test_by_dates` in `backtesting/splitting.py`; Optuna tuning persists trials to `algo.hyperparam_trials` |

**Deep-comparison row updates** (section "Deep Comparison: Paper's LEAR Specification vs Your Implementation"):
- VST asinh: `DIFFERENT — paper uses asinh, you use z-score standardization`
  → `MATCH — target_scaler="asinh" in configs/{dk1,de}_lear.py; implementation in price_forecasting/data/asinh_scaler.py`
- (Leave the Lambda selection LARS+AIC vs LassoCV row as `DIFFERENT`;
  both valid, CV is more standard, no claim to change.)

**Headline score update:**
- Old: `8 PASS, 2 PARTIAL, 3 FAIL out of 13`
- New: `12 PASS, 1 PARTIAL, 0 FAIL out of 13` (only #2 state-of-the-art
  comparison remains PARTIAL — DNN is implemented but not deployed)

**Top-of-file:** Add a date-stamped line — `Refreshed 2026-05-21 against
commits up to <PR-1 merge SHA>`.

**Validation:** None — pure prose.

**Risk:** None.

---

## Sequencing

All three PRs are file-level disjoint and can be reviewed in parallel.
Suggested merge order:

1. **PR 1** (lowest risk, clears the deck) — ~30 min implementation
2. **PR 3** (independent, can be drafted in parallel) — ~20 min
3. **PR 2** (touches deploy pipeline, ship last) — ~1 h

Total wall-clock: ~2 hours implementation + review.

## Definition of done

- All three PRs merged to `main`.
- CD pipeline green on the post-PR-2 deploy.
- `algo.experiment_runs` rows created after PR 2 deploy carry a non-empty
  `git_sha`.
- `pytest tests/ -v` green.
- `ruff check` clean.
- Codebase frozen. Any further change requires explicit thesis-blocking
  justification.
