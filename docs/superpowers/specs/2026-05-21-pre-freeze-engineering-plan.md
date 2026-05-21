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
- `Dockerfile` (only — `Dockerfile.worker` is the Prefect worker daemon, it
  does not run flows or write `experiment_runs`, so it does not need `GIT_SHA`):
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
| 3 | Computational cost evaluated | FAIL | PASS | `training_duration_seconds` column in `algo.experiment_runs` (migration 006); per-run timing captured by `LiveRunner.run_live_with_metadata` in the scheduled Prefect flow (see PR 4 — backtest + CLI `predict` instrumentation required to make this PASS true for the thesis research path) |
| 5 | Multiple markets tested | FAIL | PASS | `configs/de_lear.py` exists and is deployed via `deploy_forecast.py::FORECAST_CONFIGS = ["dk1_lear", "de_lear"]` |
| 7 | Statistical testing for significance | FAIL | PASS | `price_forecasting/evaluation/statistical_tests.py` implements `diebold_mariano` + `giacomini_white_multivariate`; `build_dm_matrix` in `evaluation/summary.py` for >2 models |
| 9 | Hyperparameters estimated ex-ante | PARTIAL | PASS | `val_start_date`/`val_end_date` declared in both production configs; `split_by_dates_with_validation` in `backtesting/splitting.py`; Optuna tuning persists trials to `algo.hyperparam_trials` (see PR 4 — LEAR `alpha="auto"` + reframed description required to make the LEAR side of this claim true) |

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

### PR 4 — `feat/lago-compliance-followup`  (added post-review of PR 3)

Code-review of PR 3 found that two upgraded PASS rows (#3 and #9) describe
the *intended* design rather than the *deployed* behaviour. The components
exist (`run_live_with_metadata`, `split_by_dates_with_validation`, the
`LassoCV` branch in `LearModel.fit`) but they are not wired into the paths
the thesis actually runs. This PR closes the gap so the scorecard's PASS
claims are honest.

**#3 — instrument the backtest + CLI predict timing path**

Today only `schedules/forecast.py` (the daily Prefect flow) populates
`training_duration_seconds`. Backtests and CLI predictions store `0.0`.

Changes:
- `src/price_forecasting/src/price_forecasting/backtesting/runner.py`:
  Wrap the `BacktestRunner.execute()` work in `time.perf_counter()` and
  return `training_duration_seconds` in the result dict.
- `src/forecast_cli/src/forecast_cli/tracking.py`:
  Add `training_duration_seconds: float = 0.0` kwarg to
  `track_backtest_run`, forward to `insert_experiment_run`.
- `src/forecast_cli/src/forecast_cli/main.py`:
  In the `predict` command, swap `runner.run_live()` →
  `runner.run_live_with_metadata()` and pass
  `result.training_duration_seconds` to `track_prediction`.

**#9 — make LEAR ex-ante hyperparameter selection actually run**

Today both LEAR configs set `model_params={"alpha": 0.01}`, and
`LearModel.fit()` only invokes `LassoCV` when `alpha in (None, "auto")`.
So `LassoCV` is never invoked in production. The 3-way splitter is
defined but `BacktestRunner._split_data()` calls the 2-way `split_by_dates`.

Changes:
- `configs/dk1_lear.py` and `configs/de_lear.py`: change
  `model_params={"alpha": 0.01}` → `model_params={"alpha": "auto"}`. This
  flips `LearModel.fit()` to the `LassoCV(cv=TimeSeriesSplit)` branch —
  ex-ante alpha selection by construction (CV folds within training data).
- Re-run baseline backtests on DK1 and DE; confirm `rMAE` does not
  regress materially. If it does, fall back to fixed `alpha` and reframe
  #9 description rather than re-fudge the claim.
- *Optional* — wire `split_by_dates_with_validation` into
  `BacktestRunner._split_data()` when `val_start_date`/`val_end_date` are
  set in config. Not strictly required for LEAR (LassoCV does internal
  TimeSeriesSplit on the training fold), but makes the validation set
  explicit for downstream DNN work.

After landing, reframe the #9 row to:
> Both configs declare `val_start_date`/`val_end_date`. DNN/Optuna path
> uses them for ex-ante tuning (trials in `algo.hyperparam_trials`,
> migration 008). LEAR uses `LassoCV(cv=TimeSeriesSplit)` on training
> data — ex-ante by construction.

**Validation:**
- `pytest tests/ -v` passes (add tests for timing capture in backtest +
  CLI predict paths).
- One backtest run on DK1 after the change writes a non-zero
  `training_duration_seconds`.
- `LearModel.best_alphas` is populated for at least one fit (proof that
  the `LassoCV` branch ran).
- DK1 rMAE on the standard backtest window is within ~5% of the
  `alpha=0.01` baseline.

**Risk:** Medium. `LassoCV` makes each LEAR fit ~5× slower (inner CV
loop). If thesis backtests are already tight on wall-clock, schedule the
re-run window accordingly. The fallback (keep `alpha=0.01`, narrow the
#9 description) is always available.

---

### PR 5 — `ci/cd-auto-apply-migrations`  (added post-PR-2 deploy incident)

**Incident:** Merging PR 2 (`feat/git-sha-experiment-tracking`) broke the
post-deploy smoke run on 2026-05-21. The CD pipeline rebuilt the image
with the new `insert_experiment_run(... git_sha=...)` call site but
never applied migration `010_alter_experiment_runs_add_git_sha.sql` on
the deploy host. The first `daily-forecast-dk1_lear` flow run on the
new image hit ClickHouse with a `git_sha` column the DB didn't have,
and the flow failed.

This is a pre-existing pattern (migrations 007, 008, 009 also relied on
a manual `run_migrations` step documented in `DEPLOYMENT.md`), but PR 2
is the first where a schema gap and a code gap shipped in the *same*
image — so the implicit "operator remembers to run migrations" coupling
finally failed loudly. The fix is to wire migration application into CD
so this class of bug cannot recur.

**Changes:**
- `.github/workflows/cd_deploy.yml`:
  - After the `git reset --hard origin/main` step on the deploy host,
    before `docker build`, add a step that runs
    `uv run python -m infrastructure_clickhouse.migrations.run_migrations`
    on the deploy host (same `tailscale ssh` block).
  - Migrations are idempotent (`IF NOT EXISTS`) so re-runs are safe.
  - If migrations fail, the workflow fails before image rebuild — old
    image keeps running against the old schema. No half-deployed state.
- `DEPLOYMENT.md`:
  - Update the migration section: note that migrations now auto-apply
    on every CD deploy. The manual `run_migrations` command stays
    documented as a recovery procedure but is no longer the primary
    path.
  - Update the migration count to reflect current head (010 as of
    today; bump whenever a new one lands).

**Validation:**
- A fresh CD deploy applies all pending migrations before image rebuild.
- The `daily-forecast-dk1_lear` smoke run on the post-deploy image
  reaches `state=COMPLETED`.
- Inspect `system.parts` for `algo.experiment_runs` to confirm the
  `git_sha` column exists on the deploy DB.

**Recovery for the current incident (do this before PR 5 lands):**
```bash
tailscale ssh "$DEPLOY_USER@$DEPLOY_HOST"
cd "$REPO_PATH"
uv run python -m infrastructure_clickhouse.migrations.run_migrations
```
Then re-run the failed CD workflow (or wait for the next scheduled
flow). Confirm the next `daily-forecast` flow completes.

**Risk:** Low — migrations are idempotent and `run_migrations.py` is
the same script operators have been running by hand. Worst case: a
new migration with a logic bug breaks deploys; mitigation is that the
deploy fails *before* the image is rebuilt, so the running service
keeps working.

**Priority:** High — this is the root cause of the 2026-05-21 smoke
failure and will recur on the next migration-bearing PR if not fixed.
Land before PR 4.

---

## Sequencing

PRs 1–3 are file-level disjoint and can be reviewed in parallel. PR 4
was added after code review of PR 3 surfaced the #3 + #9 honesty gap;
it depends on PR 2 (the `git_sha` schema additions in `experiment_runs`
must already be applied) but is otherwise independent.

Suggested merge order:

1. **PR 1** (lowest risk, clears the deck) — ~30 min implementation
2. **PR 3** (independent, can be drafted in parallel) — ~20 min
3. **PR 2** (touches deploy pipeline) — ~1 h
4. **PR 5** (CD auto-apply migrations — root-cause fix for the
   2026-05-21 smoke failure; land before PR 4 so PR 4's eventual schema
   touches stay safe) — ~30 min
5. **PR 4** (closes the honesty gap surfaced by review of PR 3) — ~1–2 h
   implementation + 1 backtest re-run

Total wall-clock: ~4 hours implementation + review + one backtest.

## Definition of done

- All five PRs merged to `main`.
- CD pipeline green on the post-PR-2 deploy *and* the post-PR-5 deploy.
- `algo.experiment_runs` rows created after PR 2 deploy carry a non-empty
  `git_sha`.
- After PR 5: a CD deploy applies pending migrations automatically, and
  the post-deploy smoke run reaches `state=COMPLETED`.
- After PR 4: a fresh DK1 backtest writes a non-zero
  `training_duration_seconds`, and `LearModel.best_alphas` is populated
  (proof the `LassoCV` branch actually ran).
- `pytest tests/ -v` green.
- `ruff check` clean.
- Codebase frozen. Any further change requires explicit thesis-blocking
  justification.
