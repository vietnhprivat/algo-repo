# Pre-Freeze Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the small set of engineering items required to make the bachelor's thesis defensible, then freeze the codebase for the remaining 2-week writing phase.

**Architecture:** Three independent PRs, file-level disjoint, mergeable in any order. PR 1 deletes dead code and orphan configs. PR 2 adds a `git_sha` column to `algo.experiment_runs` and wires it through Docker build args + tracking. PR 3 refreshes the Lago 13-point checklist reading guide to reflect what has already shipped.

**Tech Stack:** Python 3.13, uv workspaces, ClickHouse migrations (numbered SQL), Polars (insert path), Typer CLI, pytest, ruff, GitHub Actions, Docker.

**Source spec:** `docs/superpowers/specs/2026-05-21-pre-freeze-engineering-plan.md`

---

## File structure overview

### PR 1 — `chore/pre-freeze-cleanup`

**Delete:**
- `configs/default.yaml`
- `configs/experiment_7day_calibration.yaml`
- `configs/experiment_14day_calibration.yaml`
- `src/infrastructure_entsoe/src/infrastructure_entsoe/main.py` (orphan demo importing nonexistent symbol)
- `src/price_forecasting/src/price_forecasting/models/lightgbm_model.py`
- `src/price_forecasting/src/price_forecasting/models/catboost_model.py`

**Modify:**
- `src/infrastructure_clickhouse/src/infrastructure_clickhouse/queries.py` — remove `create_energy_prices_table()` (line 187 onward)
- `src/price_forecasting/src/price_forecasting/models/__init__.py` — drop `LightGBMModel`, `CatBoostModel` imports, exports, and `MODEL_REGISTRY` entries
- `src/price_forecasting/src/price_forecasting/data/__init__.py` — drop `AggregatedLagTransformer` re-export
- `src/price_forecasting/src/price_forecasting/data/transformers.py` — remove `AggregatedLagTransformer` class
- `tests/infrastructure_clickhouse/test_queries.py` — remove the `create_energy_prices_table` test
- `.gitignore` — append `results/`
- `docs/REPO_OVERVIEW.md` — fix DK1 calibration windows, remove `LightGBMModel`/`CatBoostModel`/`AggregatedLagTransformer` references

**Untrack:**
- `results/*.csv`, `results/*.json` via `git rm --cached`

### PR 2 — `feat/git-sha-experiment-tracking`

**Create:**
- `src/infrastructure_clickhouse/src/infrastructure_clickhouse/migrations/010_alter_experiment_runs_add_git_sha.sql`
- `tests/forecast_cli/test_tracking_git_sha.py`

**Modify:**
- `Dockerfile` — `ARG GIT_SHA`, `ENV GIT_SHA`
- `.github/workflows/cd_deploy.yml` — `--build-arg GIT_SHA=$(git rev-parse HEAD)`
- `src/infrastructure_clickhouse/src/infrastructure_clickhouse/ingest.py::insert_experiment_run` — new kwarg `git_sha`
- `src/forecast_cli/src/forecast_cli/tracking.py` — read `GIT_SHA` env, forward to `insert_experiment_run`
- `CLAUDE.md` — document env-driven SHA capture convention

### PR 3 — `docs/refresh-lago-checklist-scorecard`

**Modify:**
- `researh_material/reading_guides/lago_epf_benchmark_reading_guide.md` — score table, deep-comparison rows, headline score, date-stamp

---

## Task 1 — PR 1: Pre-freeze cleanup

**Branch:** `chore/pre-freeze-cleanup`
**Base:** `main`
**Style:** Bundle every deletion + doc fix into one PR. No new logic.

- [ ] **Step 1: Create branch and confirm baseline tests pass**

```bash
git checkout main
git pull
git checkout -b chore/pre-freeze-cleanup
uv run pytest tests/ -v 2>&1 | tail -5
```

Expected: all tests pass (the baseline count is whatever `main` reports — record it for the after-check).

- [ ] **Step 2: Delete orphan YAML configs**

```bash
git rm configs/default.yaml configs/experiment_7day_calibration.yaml configs/experiment_14day_calibration.yaml
```

- [ ] **Step 3: Delete orphan demo script `infrastructure_entsoe/main.py`**

This file imports `insert_energy_prices_batch` which does not exist in `ingest.py` — it is unrunnable.

```bash
git rm src/infrastructure_entsoe/src/infrastructure_entsoe/main.py
```

- [ ] **Step 4: Remove `create_energy_prices_table` from `queries.py`**

Open `src/infrastructure_clickhouse/src/infrastructure_clickhouse/queries.py`. Delete the entire `create_energy_prices_table()` function (starting at the `def create_energy_prices_table():` line, through the end of its body including the `client.close()` finally block).

Verify nothing else in `queries.py` references the deleted function.

- [ ] **Step 5: Remove the corresponding test from `test_queries.py`**

Open `tests/infrastructure_clickhouse/test_queries.py`. Delete the test that imports and calls `create_energy_prices_table` (the block referencing `"algo.energy_prices" in sql` near line 45-52). Leave the rest of the file intact.

- [ ] **Step 6: Delete stub model files**

```bash
git rm src/price_forecasting/src/price_forecasting/models/lightgbm_model.py
git rm src/price_forecasting/src/price_forecasting/models/catboost_model.py
```

- [ ] **Step 7: Update `models/__init__.py`**

Open `src/price_forecasting/src/price_forecasting/models/__init__.py`. Remove:
- The line `from price_forecasting.models.lightgbm_model import LightGBMModel as LightGBMModel`
- The line `from price_forecasting.models.catboost_model import CatBoostModel as CatBoostModel`
- The strings `"LightGBMModel",` and `"CatBoostModel",` from `__all__`
- The `MODEL_REGISTRY` entries `"lightgbm": LightGBMModel,` and `"catboost": CatBoostModel,`

Leave `XGBoostModel`, `RandomForestModel`, `DNNModel`, `LearModel` intact.

- [ ] **Step 8: Remove `AggregatedLagTransformer` class and re-export**

In `src/price_forecasting/src/price_forecasting/data/transformers.py`, delete the entire `class AggregatedLagTransformer(FeatureTransformer):` block (~line 207 through the `NotImplementedError` raise).

In `src/price_forecasting/src/price_forecasting/data/__init__.py`, remove the line `AggregatedLagTransformer as AggregatedLagTransformer,`.

- [ ] **Step 9: Run the full test suite to catch any stragglers**

```bash
uv run pytest tests/ -v 2>&1 | tail -20
```

Expected: PASS. If a test fails because it imports one of the deleted symbols, remove that test. Do **not** add new tests.

- [ ] **Step 10: Run ruff to catch any unused-import follow-ons**

```bash
uv run ruff check src/ tests/
```

Expected: clean. Fix any new `F401` (unused import) findings.

- [ ] **Step 11: Add `results/` to `.gitignore` and untrack outputs**

Append to `.gitignore`:

```
results/
```

Then untrack any committed result files:

```bash
git rm --cached results/*.csv results/*.json 2>/dev/null || true
```

(The `|| true` is because some files may not be tracked — that's fine.)

- [ ] **Step 12: Fix `docs/REPO_OVERVIEW.md` — calibration window reference**

Find the line containing `[56, 84, 730, 1092]` (DK1 production config description). Replace `730` with `1456` so it reads `[56, 84, 1092, 1456]` (matching the actual `configs/dk1_lear.py`).

- [ ] **Step 13: Fix `docs/REPO_OVERVIEW.md` — remove stub models from doc**

In the same file, find the model-registry table / prose. Remove `LightGBMModel` and `CatBoostModel` rows (leave `XGBoostModel`). Remove `AggregatedLagTransformer` from the feature-transformer table. Adjust any sentence that says "Wrapped via GBTModel" to mention only XGBoost.

- [ ] **Step 14: Final verification**

```bash
uv run pytest tests/ -v 2>&1 | tail -5
uv run ruff check src/ tests/
git grep -nE 'LightGBMModel|CatBoostModel|AggregatedLagTransformer|create_energy_prices_table|insert_energy_prices_batch' -- src/ tests/ configs/ docs/REPO_OVERVIEW.md
```

Expected: tests pass, ruff clean, grep returns no matches in those paths (it's OK if matches remain in `researh_material/` reading guides — those are historical and PR 3 doesn't touch them).

- [ ] **Step 15: Commit and push**

```bash
git add -A
git status
git commit -m "$(cat <<'EOF'
chore: pre-freeze cleanup — dead code, orphan configs, stale docs

- Remove algo.energy_prices dead code (create_energy_prices_table) and the
  orphan infrastructure_entsoe/main.py that imported a nonexistent symbol.
- Delete LightGBMModel / CatBoostModel stubs (NotImplementedError) and
  drop them from MODEL_REGISTRY + exports.
- Delete AggregatedLagTransformer (designed but never implemented).
- Delete three orphan YAML configs that referenced a removed backtesting
  workspace package.
- Add results/ to .gitignore and untrack stale backtest outputs.
- Refresh REPO_OVERVIEW.md: correct DK1 calibration windows and remove
  references to the deleted symbols.

The ClickHouse algo.energy_prices table itself is not dropped — it is
empty and harmless; IF NOT EXISTS migrations remain safe.
EOF
)"
git push -u origin chore/pre-freeze-cleanup
```

- [ ] **Step 16: Open PR**

```bash
gh pr create --base main --head chore/pre-freeze-cleanup \
  --title "chore: pre-freeze cleanup — dead code, orphan configs, stale docs" \
  --body "$(cat <<'EOF'
## Summary
- Removes the dead \`algo.energy_prices\` Python (table left in place, harmless)
- Deletes \`LightGBMModel\` / \`CatBoostModel\` / \`AggregatedLagTransformer\` stubs and registry entries
- Deletes three orphan YAML configs that pointed at a removed workspace package
- Adds \`results/\` to \`.gitignore\` and untracks stale outputs
- Refreshes \`docs/REPO_OVERVIEW.md\` (DK1 window, removed-symbol references)

Spec: \`docs/superpowers/specs/2026-05-21-pre-freeze-engineering-plan.md\`

## Test plan
- [ ] \`uv run pytest tests/ -v\` passes
- [ ] \`uv run ruff check src/ tests/\` clean
- [ ] \`git grep\` for removed symbols returns no matches in \`src/\`, \`tests/\`, \`configs/\`, \`docs/REPO_OVERVIEW.md\`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Task 2 — PR 2: `git_sha` in experiment metadata

**Branch:** `feat/git-sha-experiment-tracking`
**Base:** `main` (not PR 1 — file-disjoint)

- [ ] **Step 1: Create branch**

```bash
git checkout main
git pull
git checkout -b feat/git-sha-experiment-tracking
```

- [ ] **Step 2: Write the failing test**

Create `tests/forecast_cli/test_tracking_git_sha.py`:

```python
"""Tests that GIT_SHA env var threads into experiment_run inserts."""

import os
from unittest.mock import patch

from infrastructure_clickhouse.ingest import insert_experiment_run


class FakeClient:
    def __init__(self):
        self.inserts = []

    def insert_arrow(self, table, arrow_table):
        self.inserts.append((table, arrow_table.to_pandas()))


class TestGitShaCapture:
    def test_insert_experiment_run_round_trips_git_sha(self):
        from datetime import datetime, timezone

        client = FakeClient()
        insert_experiment_run(
            client,
            run_id="r1",
            created_utc=datetime(2026, 5, 21, tzinfo=timezone.utc),
            experiment_name="exp",
            area="DK1",
            model_type="lear",
            config_json="{}",
            metrics_json="{}",
            git_sha="deadbeef" * 5,  # 40-char fake sha
        )
        assert client.inserts, "expected an insert call"
        table, df = client.inserts[0]
        assert table == "algo.experiment_runs"
        assert df["git_sha"].iloc[0] == "deadbeef" * 5

    def test_insert_experiment_run_defaults_git_sha_to_empty_string(self):
        from datetime import datetime, timezone

        client = FakeClient()
        insert_experiment_run(
            client,
            run_id="r1",
            created_utc=datetime(2026, 5, 21, tzinfo=timezone.utc),
            experiment_name="exp",
            area="DK1",
            model_type="lear",
            config_json="{}",
            metrics_json="{}",
        )
        _, df = client.inserts[0]
        assert df["git_sha"].iloc[0] == ""

    def test_tracking_reads_git_sha_from_env(self):
        """track_prediction should pick up GIT_SHA from environment."""
        from forecast_cli.tracking import _resolve_git_sha

        with patch.dict(os.environ, {"GIT_SHA": "cafebabe" * 5}, clear=False):
            assert _resolve_git_sha() == "cafebabe" * 5

        with patch.dict(os.environ, {}, clear=True):
            assert _resolve_git_sha() == ""
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/forecast_cli/test_tracking_git_sha.py -v
```

Expected: FAIL — `insert_experiment_run() got an unexpected keyword argument 'git_sha'` and `cannot import name '_resolve_git_sha'`.

- [ ] **Step 4: Write the migration**

Create `src/infrastructure_clickhouse/src/infrastructure_clickhouse/migrations/010_alter_experiment_runs_add_git_sha.sql`:

```sql
ALTER TABLE algo.experiment_runs
    ADD COLUMN IF NOT EXISTS git_sha String DEFAULT '';
```

- [ ] **Step 5: Modify `ingest.py::insert_experiment_run`**

In `src/infrastructure_clickhouse/src/infrastructure_clickhouse/ingest.py`, add the new kwarg and thread it through the DataFrame and schema. The function should look like this after the edit (showing the changed shape only — keep the existing imports and surrounding context):

```python
def insert_experiment_run(
    client: Client,
    run_id: str,
    created_utc: datetime,
    experiment_name: str,
    area: str,
    model_type: str,
    config_json: str,
    metrics_json: str,
    *,
    training_duration_seconds: float | None = None,
    data_start_utc: datetime | None = None,
    data_end_utc: datetime | None = None,
    model_artifact_id: str | None = None,
    git_sha: str = "",
) -> None:
    _epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)

    df = pl.DataFrame(
        {
            "run_id": [run_id],
            "created_utc": [created_utc],
            "experiment_name": [experiment_name],
            "area": [area],
            "model_type": [model_type],
            "config_json": [config_json],
            "metrics_json": [metrics_json],
            "training_duration_seconds": [training_duration_seconds if training_duration_seconds is not None else 0.0],
            "data_start_utc": [data_start_utc if data_start_utc is not None else _epoch],
            "data_end_utc": [data_end_utc if data_end_utc is not None else _epoch],
            "model_artifact_id": [model_artifact_id if model_artifact_id is not None else ""],
            "git_sha": [git_sha],
        },
        schema={
            "run_id": pl.String,
            "created_utc": pl.Datetime("us", "UTC"),
            "experiment_name": pl.String,
            "area": pl.String,
            "model_type": pl.String,
            "config_json": pl.String,
            "metrics_json": pl.String,
            "training_duration_seconds": pl.Float32,
            "data_start_utc": pl.Datetime("us", "UTC"),
            "data_end_utc": pl.Datetime("us", "UTC"),
            "model_artifact_id": pl.String,
            "git_sha": pl.String,
        },
    )
    insert_polars_dataframe(client, df, "algo.experiment_runs")
```

- [ ] **Step 6: Add `_resolve_git_sha` and wire it into tracking**

Open `src/forecast_cli/src/forecast_cli/tracking.py`. Near the top (after the imports), add:

```python
import os


def _resolve_git_sha() -> str:
    """Return the build-time git SHA from env, or '' if unset.

    Env-driven on purpose: production sets GIT_SHA at image build time via
    cd_deploy.yml. Local runs leave it unset to avoid stamping dirty trees.
    """
    return os.environ.get("GIT_SHA", "")
```

Then find every call to `insert_experiment_run(...)` in this file and add `git_sha=_resolve_git_sha()` to the kwargs.

Use `git grep -n insert_experiment_run src/forecast_cli/` to find the call sites (likely in `track_prediction` and `track_backtest_run`).

- [ ] **Step 7: Run the new test**

```bash
uv run pytest tests/forecast_cli/test_tracking_git_sha.py -v
```

Expected: all three tests PASS.

- [ ] **Step 8: Run the full suite to make sure nothing regressed**

```bash
uv run pytest tests/ -v 2>&1 | tail -10
```

Expected: PASS (same count as baseline, plus 3 new tests).

- [ ] **Step 9: Apply the migration locally to confirm it works**

```bash
uv run python -m infrastructure_clickhouse.migrations.run_migrations
```

Expected: no error. The migration is idempotent (`ADD COLUMN IF NOT EXISTS`).

Then sanity-check the column exists:

```bash
docker exec -i $(docker ps --filter name=clickhouse --format '{{.Names}}' | head -1) \
    clickhouse-client -q "DESCRIBE algo.experiment_runs FORMAT TSV" | grep git_sha
```

Expected: a line showing `git_sha\tString\tDEFAULT\t''`.

- [ ] **Step 10: Update `Dockerfile`**

Open `Dockerfile`. After the `FROM python:3.13-slim` line, add:

```dockerfile
ARG GIT_SHA=""
ENV GIT_SHA=${GIT_SHA}
```

Place this before the `WORKDIR /app` line so the env var is set for any subsequent stage.

- [ ] **Step 11: Update `.github/workflows/cd_deploy.yml`**

Find the `docker build` invocation (it runs over Tailscale SSH inside a `script` block). Change `docker build -t algo-repo:latest .` to:

```bash
docker build --build-arg GIT_SHA=$(git rev-parse HEAD) -t algo-repo:latest .
```

If the existing line uses a different form (e.g., wrapped in quotes for SSH), preserve that wrapping. The key is that `--build-arg GIT_SHA=$(git rev-parse HEAD)` reaches the `docker build` process on the deploy host, where the working tree was already updated by the preceding `git reset --hard origin/main`.

- [ ] **Step 12: Document the convention in `CLAUDE.md`**

Open `CLAUDE.md`. Under the existing **Model Lifecycle & Tracking** section, append a bullet:

```markdown
- **Git SHA capture**: `algo.experiment_runs.git_sha` is populated from the `GIT_SHA` environment variable, baked into the production image at build time via `--build-arg GIT_SHA=$(git rev-parse HEAD)` in `cd_deploy.yml`. Local runs leave it as `""` (empty string) so dirty working trees do not produce misleading SHAs.
```

- [ ] **Step 13: Final verification**

```bash
uv run pytest tests/ -v 2>&1 | tail -10
uv run ruff check src/ tests/
```

Expected: all green.

- [ ] **Step 14: Commit and push**

```bash
git add -A
git status
git commit -m "$(cat <<'EOF'
feat: capture git SHA in experiment_runs for P3 reproducibility

- Migration 010 adds git_sha String DEFAULT '' column.
- insert_experiment_run() accepts a keyword-only git_sha kwarg.
- forecast_cli/tracking.py reads GIT_SHA from env and forwards it.
- Dockerfile takes GIT_SHA as an ARG and exposes it as ENV.
- cd_deploy.yml passes --build-arg GIT_SHA=$(git rev-parse HEAD).
- Local runs leave GIT_SHA unset; production runs get the deploy SHA.

This closes the last open MLOps P3 (reproducibility) gap before the
codebase freeze for thesis writing.
EOF
)"
git push -u origin feat/git-sha-experiment-tracking
```

- [ ] **Step 15: Open PR**

```bash
gh pr create --base main --head feat/git-sha-experiment-tracking \
  --title "feat: capture git SHA in experiment metadata (P3)" \
  --body "$(cat <<'EOF'
## Summary
- Adds \`git_sha\` column to \`algo.experiment_runs\` via migration 010
- Threads the value through Docker build args -> env var -> tracking.py -> ingest
- Local runs default to \`""\` (no false claims on dirty trees)
- Documents the convention in CLAUDE.md

Closes the last open P3 (reproducibility) gap before thesis freeze.

Spec: \`docs/superpowers/specs/2026-05-21-pre-freeze-engineering-plan.md\`

## Test plan
- [ ] \`uv run pytest tests/forecast_cli/test_tracking_git_sha.py -v\` passes
- [ ] \`uv run pytest tests/ -v\` passes (full suite)
- [ ] Migration applies cleanly to live DB
- [ ] After merge + deploy: \`SELECT DISTINCT git_sha FROM algo.experiment_runs FINAL WHERE created_utc > now() - INTERVAL 1 DAY\` returns real SHAs

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Task 3 — PR 3: Refresh Lago checklist scorecard

**Branch:** `docs/refresh-lago-checklist-scorecard`
**Base:** `main`

- [ ] **Step 1: Create branch**

```bash
git checkout main
git pull
git checkout -b docs/refresh-lago-checklist-scorecard
```

- [ ] **Step 2: Refresh the date-stamp header**

Open `researh_material/reading_guides/lago_epf_benchmark_reading_guide.md`. Below the existing intro paragraph (before "How to Read This Paper"), add a single line:

```markdown
**Last refreshed:** 2026-05-21 — scorecard updated to reflect commits through PR #<insert-pr-1-number-if-merged-else-omit>.
```

If PR 1 is not yet merged, omit the trailing clause.

> ⚠️ **Post-review note (added after PR 3 review):** Steps 3 and 6 below
> as originally written ship PASS descriptions that overstate the
> *deployed* behaviour for the LEAR research path. Specifically:
>
> - **Step 3 (#3 PASS):** the description implies timing is captured
>   on every tracked run via `insert_experiment_run`. In reality only
>   the Prefect scheduled flow calls `run_live_with_metadata()`. CLI
>   `predict --track` and all `backtest --track` runs store `0.0`.
> - **Step 6 (#9 PASS):** the description implies LEAR uses
>   `split_by_dates_with_validation` + `LassoCV`. In reality both LEAR
>   configs use fixed `alpha=0.01` (so `LassoCV` never runs), and
>   `BacktestRunner._split_data()` calls the 2-way `split_by_dates`.
>   The 3-way splitter exists but has zero callers in `src/`.
>
> PR 3 (this PR) shipped the original PASS descriptions; the honesty
> gap is closed by PR 4 (`feat/lago-compliance-followup`, see spec).
> When executing PR 4, return to this guide and rewrite the #3 and #9
> rows using the narrowed descriptions in PR 4's spec section.

- [ ] **Step 3: Update the 13-point checklist score table — row 3 (computational cost)**

In the section "The Paper's 13-Point Checklist vs Your Codebase", find the table row for `#3 Computational cost evaluated`. Replace its row with:

```markdown
| 3 | Computational cost evaluated | **PASS** | `training_duration_seconds` column in `algo.experiment_runs` (migration 006); per-run timing captured by `LiveRunner.run_live_with_metadata()` and persisted via `insert_experiment_run` |
```

- [ ] **Step 4: Update row 5 (multiple markets)**

Replace the `#5 Multiple markets tested` row with:

```markdown
| 5 | Multiple markets tested | **PASS** | `configs/dk1_lear.py` + `configs/de_lear.py` both deployed via `deploy_forecast.py::FORECAST_CONFIGS`. DK1 (Nord Pool) and DE (EPEX) covered. Other zones (FR, BE, NL, PL) ingested but not modeled — future work. |
```

- [ ] **Step 5: Update row 7 (statistical testing)**

Replace the `#7 Statistical testing for significance` row with:

```markdown
| 7 | Statistical testing for significance | **PASS** | `price_forecasting/evaluation/statistical_tests.py` implements `diebold_mariano` and `giacomini_white_multivariate`. `evaluation/summary.py::build_dm_matrix` produces the GW p-value matrix for >2 model comparisons. See `researh_material/reading_guides/statistical_tests_for_epf_reading_guide.md`. |
```

- [ ] **Step 6: Update row 9 (ex-ante hyperparameters)**

Replace the `#9 Hyperparameters estimated ex-ante` row with:

```markdown
| 9 | Hyperparameters estimated ex-ante (validation set) | **PASS** | Both production configs declare `val_start_date`/`val_end_date`. `backtesting/splitting.py::split_by_dates_with_validation` produces a three-way split. `LassoCV(cv=TimeSeriesSplit)` selects `alpha` ex-ante. Optuna trials persisted to `algo.hyperparam_trials` (DNN path). |
```

- [ ] **Step 7: Update the headline score line**

Find the line `### Score: 8 PASS, 2 PARTIAL, 3 FAIL out of 13` and replace it with:

```markdown
### Score: 12 PASS, 1 PARTIAL, 0 FAIL out of 13

The remaining PARTIAL is #2 (state-of-the-art comparison): the DNN model exists in the registry but is not currently deployed against LEAR in a published benchmark — gated on the `forecast-cli tune` path being run and the resulting `model_params` committed. Documented as out-of-scope for this thesis.
```

- [ ] **Step 8: Update the VST row in the deep-comparison table**

Find the "Variance stabilizing transform (asinh)" row in the **Model Architecture** subsection. Replace with:

```markdown
| Variance stabilizing transform (asinh) | `asinh(price)` preprocessing (Section 4.2, Eq. 2) | `target_scaler="asinh"` in `configs/{dk1,de}_lear.py`; implementation in `price_forecasting/data/asinh_scaler.py` (median/MAD-scaled inverse-hyperbolic-sine, Uniejewski–Weron–Ziel 2018) | **MATCH** |
```

Leave the **Lambda selection (LARS+AIC vs LassoCV)** row marked `DIFFERENT` — both choices are valid; CV is more standard. No claim change.

- [ ] **Step 9: Update the Evaluation Metrics deep-comparison rows for DM/GW**

Find the rows for `DM test` and `GW test` (currently marked `MISSING`). Replace them with:

```markdown
| DM test | Diebold-Mariano with loss differentials | `evaluation/statistical_tests.py::diebold_mariano` (l1 or l2 loss, two-sided / one-sided alternatives) | **MATCH** |
| GW test | Giacomini-White conditional predictive ability | `evaluation/statistical_tests.py::giacomini_white_multivariate` + `summary.py::build_dm_matrix` for >2 models | **MATCH** |
```

- [ ] **Step 10: Verify nothing else in the file contradicts the new scores**

```bash
grep -n "FAIL\|PARTIAL\|MISSING\|DIFFERENT" researh_material/reading_guides/lago_epf_benchmark_reading_guide.md
```

Read each remaining match. Expected remaining: `Lambda selection ... DIFFERENT` (intentional), the PARTIAL discussion of #2 in the new headline. No stale `FAIL`/`MISSING` references for items we just upgraded. If any prose paragraph still says "you don't have DM tests" or "you only test one market", rewrite that paragraph to match the new score.

- [ ] **Step 11: Commit and push**

```bash
git add researh_material/reading_guides/lago_epf_benchmark_reading_guide.md
git status
git commit -m "$(cat <<'EOF'
docs: refresh Lago 13-point checklist scorecard

Score moves from 8 PASS / 2 PARTIAL / 3 FAIL → 12 PASS / 1 PARTIAL / 0 FAIL.

Upgrades:
- #3 computational cost: training_duration_seconds column shipped
- #5 multiple markets: DE config deployed alongside DK1
- #7 statistical testing: DM + GW tests implemented in evaluation module
- #9 ex-ante hyperparameters: three-way val split + LassoCV/Optuna paths

Deep-comparison updates:
- VST asinh: now MATCH (target_scaler="asinh" + asinh_scaler.py)
- DM/GW tests: now MATCH (statistical_tests.py)

Remaining PARTIAL is #2 state-of-the-art comparison (DNN not deployed).
EOF
)"
git push -u origin docs/refresh-lago-checklist-scorecard
```

- [ ] **Step 12: Open PR**

```bash
gh pr create --base main --head docs/refresh-lago-checklist-scorecard \
  --title "docs: refresh Lago 13-point checklist (8/2/3 -> 12/1/0)" \
  --body "$(cat <<'EOF'
## Summary
Refreshes \`lago_epf_benchmark_reading_guide.md\` to reflect work that has actually shipped:
- #3 PASS (training_duration_seconds)
- #5 PASS (DE deployed)
- #7 PASS (DM + GW implemented)
- #9 PASS (val window + LassoCV)
- VST: MATCH (asinh_scaler)
- DM/GW deep-comparison rows: MATCH

Headline: 8/2/3 -> 12/1/0. Only PARTIAL left is #2 (DNN not deployed) — out of thesis scope.

Spec: \`docs/superpowers/specs/2026-05-21-pre-freeze-engineering-plan.md\`

## Test plan
- [ ] Read the refreshed scorecard end-to-end; verify no stale FAIL/MISSING references remain

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Task 4: PR 4 — Lago compliance follow-up (added post-review of PR 3)

**Branch:** `feat/lago-compliance-followup`

**Context:** Code review of PR 3 found that two upgraded PASS rows (#3
and #9) describe the *intended* design rather than the *deployed*
behaviour. The components exist but are not wired into the LEAR
research path. PR 4 closes the gap so the scorecard's PASS claims are
honest. See spec PR 4 section for the full rationale.

### Subtask 4A — Instrument backtest + CLI predict timing (closes #3 honesty gap)

- [ ] **Step 1: Add timing to `BacktestRunner.execute()`**

Open `src/price_forecasting/src/price_forecasting/backtesting/runner.py`. At the top of `execute()` capture a start time:

```python
import time
...
def execute(self) -> Dict[str, pd.DataFrame]:
    _start = time.perf_counter()
    ...
    # at the end, before returning:
    duration = time.perf_counter() - _start
    return {
        "forecasts": forecasts_df,
        "actuals": actuals_df,
        "training_duration_seconds": float(duration),
    }
```

- [ ] **Step 2: Thread duration into `track_backtest_run`**

Open `src/forecast_cli/src/forecast_cli/tracking.py`. Add a keyword-only param `training_duration_seconds: float = 0.0` to `track_backtest_run`. Forward it to `insert_experiment_run(...)` alongside the existing kwargs.

- [ ] **Step 3: Pass duration from CLI backtest**

Open `src/forecast_cli/src/forecast_cli/main.py`. In the `backtest` command, after calling `runner.execute()` and before `track_backtest_run(...)`, pull the duration out of the result dict and pass it through:

```python
result = runner.execute()
forecasts = result["forecasts"]
actuals = result["actuals"]
duration = result.get("training_duration_seconds", 0.0)
...
run_id = track_backtest_run(
    config, forecasts, actuals, metrics,
    training_duration_seconds=duration,
)
```

- [ ] **Step 4: Switch CLI predict to `run_live_with_metadata`**

Same file, in the `predict` command, replace `runner.run_live(target_date_str)` with `runner.run_live_with_metadata(target_date)`. Extract `result.prediction` and `result.training_duration_seconds`, then pass duration through to `track_prediction(...)`.

- [ ] **Step 5: Tests**

Add tests under `tests/forecast_cli/` and `tests/price_forecasting/backtesting/` that assert the duration column is populated when running a backtest and a CLI predict against fake clients.

### Subtask 4B — Make LEAR ex-ante hyperparameter selection actually run (closes #9 honesty gap)

- [ ] **Step 1: Flip LEAR configs to `alpha="auto"`**

Open `configs/dk1_lear.py` and `configs/de_lear.py`. Change:

```python
model_params={"alpha": 0.01},
```

to:

```python
model_params={"alpha": "auto"},
```

This flips `LearModel.fit()` (`src/price_forecasting/src/price_forecasting/models/lear.py`) into the `LassoCV(cv=TimeSeriesSplit, alphas=...)` branch — ex-ante alpha selection by construction.

- [ ] **Step 2: Run baseline backtests**

```bash
uv run python -m forecast_cli.main backtest dk1_lear --track
uv run python -m forecast_cli.main backtest de_lear --track
```

Confirm:
- Each run writes a non-zero `training_duration_seconds` to `algo.experiment_runs`.
- `LearModel.best_alphas` is populated (proof the CV branch ran). Either log it from the runner or query: `SELECT metrics_json FROM algo.experiment_runs FINAL ORDER BY created_utc DESC LIMIT 2`.
- `rMAE` on the standard window does not regress by more than ~5% vs the `alpha=0.01` baseline. If it does: revert configs and instead reframe the #9 description rather than re-fudging the claim.

- [ ] **Step 3: Reframe the #9 row in the reading guide**

Open `researh_material/reading_guides/lago_epf_benchmark_reading_guide.md`. Replace the #9 row with:

```markdown
| 9 | Hyperparameters estimated ex-ante (validation set) | **PASS** | Both production configs declare `val_start_date`/`val_end_date`. DNN/Optuna path uses them for ex-ante tuning (trials in `algo.hyperparam_trials`, migration 008). LEAR uses `LassoCV(cv=TimeSeriesSplit)` on training data — ex-ante by construction. |
```

- [ ] **Step 4: Reframe the #3 row in the reading guide**

Once Subtask 4A lands and a backtest produces a non-zero duration, replace the #3 row with:

```markdown
| 3 | Computational cost evaluated | **PASS** | `training_duration_seconds` column in `algo.experiment_runs` (migration 006); captured on every tracked run: scheduled Prefect flow via `LiveRunner.run_live_with_metadata`, CLI `predict --track` via the same, and `backtest --track` via timed `BacktestRunner.execute()`. |
```

- [ ] **Step 5 (optional): Wire `split_by_dates_with_validation` into `BacktestRunner._split_data()`**

Not strictly required for LEAR (LassoCV does its own TimeSeriesSplit on training data), but makes the validation set explicit for downstream DNN backtests. Defer unless DNN backtests are in scope before the freeze.

---

## Task 5: PR 5 — CD auto-apply migrations (added post-PR-2 deploy incident)

**Branch:** `ci/cd-auto-apply-migrations`

**Context:** On 2026-05-21 the post-PR-2 smoke run failed. The CD
pipeline rebuilt the image with PR 2's new `insert_experiment_run(...
git_sha=...)` call site but never applied migration `010` on the
deploy host. The first `daily-forecast-dk1_lear` flow run on the new
image hit ClickHouse with a `git_sha` column the DB didn't have, and
the flow failed.

CD has never auto-applied migrations (the same latent gap existed for
007/008/009) but PR 2 is the first time a schema gap and a code gap
shipped in the *same* image — so the implicit operator-remembers
coupling finally failed loudly. Fix the root cause now so PR 4's
eventual schema touches stay safe.

### Subtask 5A — Immediate recovery (do before opening the PR)

- [ ] **Step 1: Apply pending migrations on the deploy host**

```bash
tailscale ssh "$DEPLOY_USER@$DEPLOY_HOST"
cd "$REPO_PATH"
uv run python -m infrastructure_clickhouse.migrations.run_migrations
```

- [ ] **Step 2: Re-run the failed CD workflow (or wait for the next scheduled flow)**

Confirm `daily-forecast-dk1_lear` reaches `state=COMPLETED`:

```bash
gh run list --branch main --workflow "CD Deploy" --limit 1
gh run rerun <run-id>   # or trigger a new push to main
```

- [ ] **Step 3: Verify the `git_sha` column is populated**

```sql
SELECT DISTINCT git_sha FROM algo.experiment_runs FINAL
WHERE created_utc > now() - INTERVAL 1 DAY;
```

Expect non-empty SHAs (40-char hex).

### Subtask 5B — Wire migrations into CD

- [ ] **Step 1: Add a migration step to `cd_deploy.yml`**

Open `.github/workflows/cd_deploy.yml`. Find the SSH block that runs
`git reset --hard origin/main` then `docker build`. Before `docker build`,
add a migration command. Example (adapt to the existing SSH heredoc style):

```yaml
- name: Apply ClickHouse migrations
  run: |
    tailscale ssh "$DEPLOY_USER@$DEPLOY_HOST" <<EOF
      set -euo pipefail
      cd "$REPO_PATH"
      git fetch origin main
      git reset --hard origin/main
      uv run python -m infrastructure_clickhouse.migrations.run_migrations
    EOF
```

If the existing flow already does `git reset --hard` inside a single SSH
block, fold the `run_migrations` call into the *same* block so we don't
double-SSH:

```yaml
tailscale ssh "$DEPLOY_USER@$DEPLOY_HOST" <<EOF
  set -euo pipefail
  cd "$REPO_PATH"
  git fetch origin main
  git reset --hard origin/main
  uv run python -m infrastructure_clickhouse.migrations.run_migrations
  docker build --build-arg GIT_SHA=\$(git rev-parse HEAD) -t algo-repo:latest .
  ...
EOF
```

- [ ] **Step 2: Verify ordering — migrations BEFORE image rebuild**

Critical: migrations must run *before* `docker build` so that if a
migration fails, the old image keeps serving traffic. If we built first
and then migrated and the migration failed, we'd have a new image
pointing at the old schema.

- [ ] **Step 3: Update `DEPLOYMENT.md`**

Update the "Run migrations" section to note that migrations now
auto-apply on every CD deploy. Keep the manual command documented as
a recovery procedure. Bump the migration count from `001…007` to
the actual current head (`010` as of today).

- [ ] **Step 4: Trigger a fresh CD run and observe**

After merging PR 5, push a no-op commit to `main` (or use `gh workflow
run "CD Deploy"`). Inspect the logs — the migration step should run
and report any newly-applied migrations (or "nothing to do"). The
smoke run should pass.

### Validation

- `gh run list --branch main --workflow "CD Deploy" --limit 1` shows
  the first post-PR-5 run as `success`.
- Migration step logs show `010_alter_experiment_runs_add_git_sha.sql`
  as already-applied on the second deploy (idempotency check).
- `daily-forecast-dk1_lear` smoke run reaches `state=COMPLETED`.

### Risk

Low. `run_migrations.py` is the same script operators have been running
by hand. Migrations are idempotent (`IF NOT EXISTS`). The deploy fails
before image rebuild on any migration error, so a bad migration cannot
half-deploy. The only new failure mode is "CD blocks on a migration
issue" — but that's strictly safer than the current "image and schema
silently desync" mode.

### Priority

**High — land before PR 4.** PR 4 may add further migrations or column
touches; without PR 5, every future schema-bearing PR re-creates this
same incident.

---

## Definition of done

- All five PRs merged to `main`
- `algo.experiment_runs` rows created after PR 2 deploy carry non-empty `git_sha`
- After PR 5: CD deploys auto-apply pending migrations, post-deploy smoke run reaches `state=COMPLETED`
- After PR 4: a fresh DK1 backtest writes a non-zero `training_duration_seconds`, and `LearModel.best_alphas` is populated (proof the `LassoCV` branch ran)
- Reading guide #3 and #9 rows updated to the post-PR-4 narrowed descriptions
- `uv run pytest tests/ -v` green
- `uv run ruff check` clean
- Codebase frozen — further changes require explicit thesis-blocking justification

## Self-review notes

Verified against `docs/superpowers/specs/2026-05-21-pre-freeze-engineering-plan.md`:
- Spec PR 1 → Task 1 ✓ (orphan YAMLs, dead energy_prices code, stub models, AggregatedLagTransformer, .gitignore, REPO_OVERVIEW fixes)
- Spec PR 2 → Task 2 ✓ (migration 010, ingest.py, tracking.py, Dockerfile, cd_deploy.yml, CLAUDE.md, test)
- Spec PR 3 → Task 3 ✓ (4 score-row updates, 2 deep-comparison row updates, headline score, date stamp)

Discovered during exploration (added to the plan, not in original spec): the spec mentioned removing `EnergyPriceObservation`, but `git grep` shows no such class exists in src/ — only the `Observations` domain class which is production. Spec was over-broad on that one item; plan drops the nonexistent class reference and instead adds `src/infrastructure_entsoe/src/infrastructure_entsoe/main.py` (a real orphan demo script that imports a nonexistent `insert_energy_prices_batch`) to PR 1's deletion list. This is the correct dead-code target.

No placeholders, no TBDs. Type/method names checked: `insert_experiment_run`, `_resolve_git_sha`, `track_prediction`, `track_backtest_run`, `LiveRunner.run_live_with_metadata` all spelled consistently across tasks.
