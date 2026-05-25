# Model Cleanup + DNN/Transformer Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drop unused models (XGBoost, GBT base, RandomForest, sklearn base), reorganise remaining base classes into a `models/base/` subpackage, backfill missing Generation forecasts, tune the DNN per market, and deploy DNN + Transformer flows alongside the existing LEAR ones — with calibration windows that respect a 2023-01-01 training-data floor.

**Architecture:** Six sequential tasks. Tasks 1 (backfill) and 2 (model drops) can run in parallel wall-clock-wise. Each task ends in a commit; the work spans a single PR. Production deploy happens automatically via `cd_deploy.yml` on merge.

**Tech Stack:** Python (uv workspace), Optuna TPE, Lightning (DNN/Transformer), ClickHouse (`ReplacingMergeTree`), Prefect deployments, ENTSO-E CLI backfill.

**Spec reference:** `docs/superpowers/specs/2026-05-25-model-cleanup-and-deploy-design.md`.

---

## Task 1: Backfill DK1 and DE Generation forecasts (Section 0)

**Files:**
- No source changes. Writes to `algo.forecasts` in ClickHouse.

The Transformer config uses `Generation` as an exogenous with a 1092-day calibration window from test_start `2026-01-01`. Today `algo.forecasts` only has Generation rows from `2026-04-29` onwards for both DK1 and DE. Without backfill, the Transformer predict join produces NaN-only Generation columns and the training set collapses.

- [ ] **Step 1: Confirm current Generation data range**

Run:
```bash
uv run python -c "
from infrastructure_clickhouse.client_factory import create_client
c = create_client()
for area in ['DK1', 'DE']:
    r = c.query(f\"SELECT min(timestamp_utc), max(timestamp_utc), count() FROM algo.forecasts FINAL WHERE curve_name LIKE 'ENTSOE {area} Generation%'\").result_rows
    print(area, r)
"
```

Expected: both areas return min ≈ `2026-04-29`. If min is already `≤ 2023-01-01`, skip Step 2 and 3.

- [ ] **Step 2: Backfill DK1 Generation 2023-01-01 → 2026-04-28**

Run:
```bash
uv run python -m data_cli.main entsoe backfill generation-forecast -a DK1 -s 2023-01-01 -e 2026-04-28
```

Expected: command exits 0, prints progress per 10-month chunk. ~4 chunks total. Should take a few minutes.

- [ ] **Step 3: Backfill DE Generation 2023-01-01 → 2026-04-28**

Run:
```bash
uv run python -m data_cli.main entsoe backfill generation-forecast -a DE -s 2023-01-01 -e 2026-04-28
```

Expected: same as Step 2 but for DE.

- [ ] **Step 4: Verify backfill landed**

Run the same query as Step 1.

Expected: both areas show `min(timestamp_utc)` ≤ `2023-01-01 23:00:00+00:00`. Row count for DK1 should be roughly `1218 days × 24h ≈ 29 232` (real ENTSO-E sometimes has gaps; ±10% is fine). For DE the count will be ~3-4× higher because DE has 4 bidding zones aggregated under the same area tag.

No commit — data lands in ClickHouse, no source change.

---

## Task 2: Drop unused model files and tests (Section 1 part 1)

**Files:**
- Delete: `src/price_forecasting/src/price_forecasting/models/xgboost_model.py`
- Delete: `src/price_forecasting/src/price_forecasting/models/gbt_base.py`
- Delete: `src/price_forecasting/src/price_forecasting/models/random_forest.py`
- Delete: `src/price_forecasting/src/price_forecasting/models/sklearn_base.py`
- Modify: `src/price_forecasting/src/price_forecasting/models/__init__.py`
- Modify: `tests/price_forecasting/test_models.py` (remove `TestRandomForestModelInterface`, `TestXGBoostModelInterface`, their imports)
- Modify: `src/price_forecasting/pyproject.toml` (remove `xgboost>=2.0.0`)

- [ ] **Step 1: Delete the four model files**

Run:
```bash
git rm src/price_forecasting/src/price_forecasting/models/xgboost_model.py \
       src/price_forecasting/src/price_forecasting/models/gbt_base.py \
       src/price_forecasting/src/price_forecasting/models/random_forest.py \
       src/price_forecasting/src/price_forecasting/models/sklearn_base.py
```

- [ ] **Step 2: Update `models/__init__.py` to remove the dropped imports**

Replace the entire file `src/price_forecasting/src/price_forecasting/models/__init__.py` with:

```python
from price_forecasting.models.base import BaseModel as BaseModel
from price_forecasting.models.lightning_base import LightningModel as LightningModel
from price_forecasting.models.lear import LearModel as LearModel
from price_forecasting.models.dnn import DNNModel as DNNModel
from price_forecasting.models.transformer import TransformerModel as TransformerModel

__all__ = [
    "BaseModel",
    "LightningModel",
    "LearModel",
    "DNNModel",
    "TransformerModel",
    "get_model",
]

MODEL_REGISTRY = {
    "lear": LearModel,
    "dnn": DNNModel,
    "transformer": TransformerModel,
}


def get_model(name: str, **kwargs) -> BaseModel:
    key = name.lower()
    if key not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model: {name}. Available: {list(MODEL_REGISTRY.keys())}"
        )
    return MODEL_REGISTRY[key](**kwargs)
```

(The `lightning_base` import stays — Task 3 moves it.)

- [ ] **Step 3: Remove dropped-model imports and test classes from `tests/price_forecasting/test_models.py`**

Delete lines 9–10 (the imports):

```python
from price_forecasting.models.random_forest import RandomForestModel
from price_forecasting.models.xgboost_model import XGBoostModel
```

Delete the entire `TestRandomForestModelInterface` class (around line 128, includes the `get_model("rf", ...)` test) and the entire `TestXGBoostModelInterface` class (around line 150, includes the `get_model("xgboost", ...)` test).

- [ ] **Step 4: Remove `xgboost` from `src/price_forecasting/pyproject.toml`**

Find this block (around line 13):

```toml
    "lightning>=2.4.0",
    "xgboost>=2.0.0",
```

Replace with:

```toml
    "lightning>=2.4.0",
```

- [ ] **Step 5: Sync dependencies**

Run:
```bash
uv sync
```

Expected: exits 0; `xgboost` shown in "Uninstalled" list.

- [ ] **Step 6: Verify the test suite still passes**

Run:
```bash
uv run pytest tests/price_forecasting/test_models.py -v
```

Expected: all collected tests PASS. Classes `TestRandomForestModelInterface` and `TestXGBoostModelInterface` no longer appear.

- [ ] **Step 7: Full suite sanity check**

Run:
```bash
uv run pytest tests/ -q
```

Expected: all tests PASS (or "skipped" for known smoke-test skips). Any failure here means there's still a stale reference somewhere — fix it before committing.

- [ ] **Step 8: Commit**

Run:
```bash
git add src/price_forecasting/src/price_forecasting/models/__init__.py \
        tests/price_forecasting/test_models.py \
        src/price_forecasting/pyproject.toml \
        uv.lock
git commit -m "$(cat <<'EOF'
refactor(models): drop unused XGBoost, RandomForest, GBT/sklearn base

These models were never wired into FORECAST_CONFIGS and are not part of the
thesis evaluation. Removing them shrinks the MODEL_REGISTRY to the three
families actually deployed (lear, dnn, transformer).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Restructure `base/` subpackage (Section 1 part 2)

**Files:**
- Create: `src/price_forecasting/src/price_forecasting/models/base/__init__.py`
- Create: `src/price_forecasting/src/price_forecasting/models/base/abstract.py` (content from old `base.py`)
- Create: `src/price_forecasting/src/price_forecasting/models/base/lightning.py` (content from old `lightning_base.py`)
- Delete: `src/price_forecasting/src/price_forecasting/models/base.py`
- Delete: `src/price_forecasting/src/price_forecasting/models/lightning_base.py`
- Modify: `src/price_forecasting/src/price_forecasting/models/__init__.py` (import path for `LightningModel`)
- Modify: `src/price_forecasting/src/price_forecasting/models/dnn.py:4`
- Modify: `src/price_forecasting/src/price_forecasting/models/transformer.py:30`

- [ ] **Step 1: Move `base.py` to `base/abstract.py`**

Run:
```bash
mkdir -p src/price_forecasting/src/price_forecasting/models/base
git mv src/price_forecasting/src/price_forecasting/models/base.py \
       src/price_forecasting/src/price_forecasting/models/base/abstract.py
```

- [ ] **Step 2: Move `lightning_base.py` to `base/lightning.py`**

Run:
```bash
git mv src/price_forecasting/src/price_forecasting/models/lightning_base.py \
       src/price_forecasting/src/price_forecasting/models/base/lightning.py
```

- [ ] **Step 3: Create `base/__init__.py` that re-exports both classes**

Write `src/price_forecasting/src/price_forecasting/models/base/__init__.py`:

```python
from price_forecasting.models.base.abstract import BaseModel as BaseModel
from price_forecasting.models.base.lightning import LightningModel as LightningModel

__all__ = ["BaseModel", "LightningModel"]
```

- [ ] **Step 4: Update `dnn.py` import**

In `src/price_forecasting/src/price_forecasting/models/dnn.py` line 4, change:

```python
from price_forecasting.models.lightning_base import LightningModel
```

to:

```python
from price_forecasting.models.base import LightningModel
```

- [ ] **Step 5: Update `transformer.py` import**

In `src/price_forecasting/src/price_forecasting/models/transformer.py` line 30, change:

```python
from price_forecasting.models.lightning_base import LightningModel
```

to:

```python
from price_forecasting.models.base import LightningModel
```

- [ ] **Step 6: Update `models/__init__.py` `LightningModel` import**

In `src/price_forecasting/src/price_forecasting/models/__init__.py`, change:

```python
from price_forecasting.models.lightning_base import LightningModel as LightningModel
```

to:

```python
from price_forecasting.models.base import LightningModel as LightningModel
```

The `BaseModel` import (`from price_forecasting.models.base import BaseModel as BaseModel`) needs no change — it now resolves to the subpackage's `__init__.py` re-export.

- [ ] **Step 7: Confirm no stale references remain**

Run:
```bash
rg "lightning_base" --type py
```

Expected: empty output. If anything appears, update it to use `price_forecasting.models.base`.

- [ ] **Step 8: Verify imports work end-to-end**

Run:
```bash
uv run python -c "
from price_forecasting.models import BaseModel, LightningModel, LearModel, DNNModel, TransformerModel, get_model, MODEL_REGISTRY
print('Registry:', list(MODEL_REGISTRY.keys()))
print('BaseModel:', BaseModel.__module__)
print('LightningModel:', LightningModel.__module__)
"
```

Expected:
```
Registry: ['lear', 'dnn', 'transformer']
BaseModel: price_forecasting.models.base.abstract
LightningModel: price_forecasting.models.base.lightning
```

- [ ] **Step 9: Full test suite**

Run:
```bash
uv run pytest tests/ -q
```

Expected: all tests PASS. The Lightning-using tests (`test_dnn_ensemble.py`, `test_lightning_wandb.py`, `test_transformer_model.py`) exercise the moved imports.

- [ ] **Step 10: Commit**

Run:
```bash
git add src/price_forecasting/src/price_forecasting/models/
git commit -m "$(cat <<'EOF'
refactor(models): move base classes into models/base/ subpackage

Separates framework abstractions (BaseModel, LightningModel) from concrete
implementations. Callers still import from price_forecasting.models.base —
the subpackage's __init__.py re-exports both classes, so the public API is
unchanged.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Config updates enforcing the 2022 floor (Section 2)

**Files:**
- Modify: `configs/dk1_lear.py`
- Modify: `configs/de_lear.py`
- Modify: `configs/dk1_dnn.py`
- Modify: `configs/de_dnn.py`
- Create: `configs/de_transformer.py`

- [ ] **Step 1: Trim LEAR calibration windows in `configs/dk1_lear.py`**

Find:

```python
    calibration_windows=[56, 84, 1092, 1456],
```

Replace with:

```python
    calibration_windows=[56, 84, 1092],
```

- [ ] **Step 2: Same in `configs/de_lear.py`**

Same find-and-replace as Step 1.

- [ ] **Step 3: Update `configs/dk1_dnn.py` dates and calibration window**

Apply these edits to `configs/dk1_dnn.py`:

| Find | Replace |
|---|---|
| `test_start_date="2024-05-20",` | `test_start_date="2025-10-24",` |
| `test_end_date="2026-05-19",` | (unchanged) |
| `val_start_date="2023-07-30",` | `val_start_date="2025-01-01",` |
| `val_end_date="2024-05-19",` | `val_end_date="2025-10-23",` |
| `calibration_windows=[1456],` | `calibration_windows=[730],` |

Leave `model_params` placeholder dict alone — Task 5 overwrites it with tuned values.

- [ ] **Step 4: Update `configs/de_dnn.py` the same way**

Same five edits as Step 3 applied to `configs/de_dnn.py`.

- [ ] **Step 5: Create `configs/de_transformer.py`**

Write a new file `configs/de_transformer.py` that mirrors `configs/dk1_transformer.py` with `experiment_name` and `area` swapped to DE. Full contents:

```python
"""DE day-ahead forecasting config — pure-Transformer model
(Llorente & Portela, 2025).

Mirror of dk1_transformer.py with area='DE'. Production deployment
defined in src/schedules/src/schedules/deploy_forecast.py:FORECAST_CONFIGS.
"""

from price_forecasting import ExperimentConfig
from price_forecasting.data import default_transformers_for_transformer

_EXOG = ["TotalLoad", "Generation"]
_SEQ = 14  # m days of past prices (paper search: m in {14, 28})

config = ExperimentConfig(
    experiment_name="de_transformer",
    area="DE",
    model_type="transformer",
    results_dir="results",
    test_start_date="2026-01-01",
    test_end_date="2026-03-22",
    calibration_windows=[1092],
    refit_interval_days=7,
    exogenous_curve_types=_EXOG,
    target_scaler="asinh",
    feature_transformers=default_transformers_for_transformer(
        exogenous_columns=_EXOG,
        sequence_length_days=_SEQ,
    ),
    model_params={
        "seq_length_days": _SEQ,
        "n_exog": len(_EXOG),
        "embedding_dim": 128,
        "n_heads": 8,
        "n_encoder_layers": 6,
        "ff_dim": 1024,
        "dropout": 0.2,
        "mlp_hidden": 128,
        "gradient_clip_val": None,
        "lr_scheduler_step": 70,
        "lr_scheduler_gamma": 0.1,
        "epochs": 200,
        "batch_size": 32,
        "learning_rate": 1e-4,
        "validation_fraction": 0.16,
        "early_stopping_patience": 25,
        "random_seed": 42,
    },
)
```

- [ ] **Step 6: Verify LEAR backtest still runs cleanly with the new calibration list**

Run:
```bash
uv run python -m forecast_cli.main backtest dk1_lear
```

Expected: exits 0, prints MAE/RMSE/sMAPE/rMAE summary. No "Not enough training data" errors — `1092` from test_start `2026-01-01` lands at `2023-01-04`, which is well inside the available data window.

- [ ] **Step 7: Verify Transformer DE config loads**

Run:
```bash
uv run python -c "
from forecast_cli.config_loader import load_config
c = load_config('de_transformer')
print('experiment_name:', c.experiment_name)
print('area:', c.area)
print('model_type:', c.model_type)
print('calibration_windows:', c.calibration_windows)
"
```

Expected:
```
experiment_name: de_transformer
area: DE
model_type: transformer
calibration_windows: [1092]
```

- [ ] **Step 8: Commit**

Run:
```bash
git add configs/dk1_lear.py configs/de_lear.py configs/dk1_dnn.py configs/de_dnn.py configs/de_transformer.py
git commit -m "$(cat <<'EOF'
config: enforce 2023-01-01 training floor + add de_transformer

LEAR configs: drop 1456-day window (would dip into 2022 European energy
crisis). DNN configs: shift val/test dates to 2025-2026, calibration
window 730d. New de_transformer mirrors dk1_transformer for the DE
market.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: DNN hyperparameter tuning (Section 3)

**Files:**
- Modify (Step 7): `configs/dk1_dnn.py`
- Modify (Step 7): `configs/de_dnn.py`

**Prerequisite:** Task 4 must be committed (the tune crashes on the calibration-window precondition without the new dates). Task 1 is not a hard prerequisite for the DNN tune (DNN uses TotalLoad, not Generation), so the tune can run while the backfill is still in flight.

- [ ] **Step 1: Time-boxed DK1 tune (35 trials)**

Run:
```bash
(time uv run python -m forecast_cli.main tune dk1_dnn -n 35 --study-name dk1_dnn_tune_v1) 2>&1 | tee /tmp/tune_dk1.log
```

Expected: prints `study_name=dk1_dnn_tune_v1 n_trials=35`, then 35 lines like `[I ... Trial N finished with value: ...`. Final `real Xm Ys` line gives wall-clock time. Note this number — it sizes the DE budget.

If any trial fails with `ValueError: Not enough training data ...`, Task 4 wasn't applied correctly — go back, verify `val_start_date="2025-01-01"` and `calibration_windows=[730]` in `configs/dk1_dnn.py`.

- [ ] **Step 2: Decide DE budget**

If Step 1 took less than 2 hours wall-clock, proceed with 35 trials for DE.
If it took longer, drop DE to 20 trials (so the total stays under ~4 hours).

- [ ] **Step 3: Run DE tune**

Run:
```bash
(time uv run python -m forecast_cli.main tune de_dnn -n <BUDGET_FROM_STEP_2> --study-name de_dnn_tune_v1) 2>&1 | tee /tmp/tune_de.log
```

Replace `<BUDGET_FROM_STEP_2>` with `35` or `20`.

Expected: same pattern as Step 1.

- [ ] **Step 4: Extract best params for DK1**

Run:
```bash
uv run python -c "
import json
from infrastructure_clickhouse.client_factory import create_client
c = create_client()
row = c.query(\"\"\"
    SELECT params_json, value
    FROM algo.hyperparam_trials FINAL
    WHERE study_name = 'dk1_dnn_tune_v1' AND state = 'COMPLETE'
    ORDER BY value ASC LIMIT 1
\"\"\").result_rows[0]
print('best val MAE:', row[1])
print('params:', json.dumps(json.loads(row[0]), indent=2))
"
```

Expected: prints `best val MAE: <float>` and a JSON object containing keys `n_neurons, activation, dropout, learning_rate, batch_norm, l1_reg`. Record these.

- [ ] **Step 5: Extract best params for DE**

Same as Step 4 but with `study_name = 'de_dnn_tune_v1'`.

- [ ] **Step 6: Boundary sanity check**

For each tuned param across both studies, confirm none sits at the edge of its search range as defined in `src/price_forecasting/src/price_forecasting/tuning/dnn_search.py`. Open that file and compare each best param against its `suggest_*` call.

If any param is at a boundary (e.g. `n_neurons` exactly equal to the maximum, or `dropout` at the documented minimum), record it in the eventual chapter prose as "search-space-limited" — but do NOT widen the range and re-tune now. The number stands as the result of the budgeted search.

- [ ] **Step 7: Paste tuned params into `configs/dk1_dnn.py`**

Replace the entire `model_params={...}` block in `configs/dk1_dnn.py` with:

```python
    model_params={
        "hidden_units": <DK1_BEST.n_neurons>,
        "activation": "<DK1_BEST.activation>",
        "dropout": <DK1_BEST.dropout>,
        "learning_rate": <DK1_BEST.learning_rate>,
        "batch_norm": <DK1_BEST.batch_norm>,
        "l1_reg": <DK1_BEST.l1_reg>,
        "epochs": 200,
        "early_stopping_patience": 20,
    },
```

Substitute the actual values from Step 4. Note the `n_neurons` → `hidden_units` rename (per `tuning/objective.py::_PARAM_REMAP`). Keep `epochs=200, early_stopping_patience=20` as-is (these are not part of the Optuna search space).

- [ ] **Step 8: Paste tuned params into `configs/de_dnn.py`**

Same as Step 7 but with DE best values from Step 5.

- [ ] **Step 9: Smoke-test the tuned configs**

Run:
```bash
uv run python -m forecast_cli.main predict dk1_dnn -d 2026-05-25
uv run python -m forecast_cli.main predict de_dnn  -d 2026-05-25
```

Expected: each prints a 24-row `period | HH:MM | predicted` table. No tracebacks. No `--track` flag here — this is just a smoke test, not a logged prediction.

- [ ] **Step 10: Commit**

Run:
```bash
git add configs/dk1_dnn.py configs/de_dnn.py
git commit -m "$(cat <<'EOF'
feat(configs): tuned DNN hyperparameters from Optuna study v1

35-trial TPE study per market against the 2025 validation window
(val_start=2025-01-01, 42 weeks). Trials persisted to
algo.hyperparam_trials under study_name dk1_dnn_tune_v1 / de_dnn_tune_v1.
Lago §4.3.3 specifies 1500 trials; reduced to 35 per market under
project deadline (footnoted in thesis).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Deploy DNN + Transformer flows (Section 4)

**Files:**
- Modify: `src/schedules/src/schedules/deploy_forecast.py`

**Prerequisites:** Tasks 1 (Generation backfill complete), 4 (configs landed), 5 (DNN tuned and committed).

- [ ] **Step 1: Pre-deploy verification — local predict per new config**

Run each, one at a time so the output is readable:

```bash
uv run python -m forecast_cli.main predict dk1_dnn         -d 2026-05-25 --track
uv run python -m forecast_cli.main predict de_dnn          -d 2026-05-25 --track
uv run python -m forecast_cli.main predict dk1_transformer -d 2026-05-25 --track
uv run python -m forecast_cli.main predict de_transformer  -d 2026-05-25 --track
```

Expected for each: prints the 24-row prediction table, then a tracking confirmation. No tracebacks.

- [ ] **Step 2: Confirm tracked rows landed in ClickHouse**

Run:
```bash
uv run python -c "
from infrastructure_clickhouse.client_factory import create_client
c = create_client()
r = c.query(\"\"\"
    SELECT experiment_name, area, model_type, training_duration_seconds, model_artifact_id != '' AS has_artifact
    FROM algo.experiment_runs FINAL
    WHERE created_utc >= now() - INTERVAL 1 HOUR
      AND experiment_name IN ('dk1_dnn','de_dnn','dk1_transformer','de_transformer')
    ORDER BY created_utc
\"\"\").result_rows
for row in r:
    print(row)
"
```

Expected: 4 rows, one per new config, each with `training_duration_seconds > 0` and `has_artifact = 1`.

If any row is missing or `has_artifact = 0`, do not proceed to Step 3 — go back and debug the failing predict.

- [ ] **Step 3: Update `deploy_forecast.py`**

In `src/schedules/src/schedules/deploy_forecast.py`, find:

```python
# LEAR configs only — DNN configs (configs/dk1_dnn.py, configs/de_dnn.py) ship
# with placeholder hyperparameters and are excluded from scheduling until
# `forecast-cli tune` has produced validated best_params. Append a DNN config
# here once its `model_params` block has been replaced with tuned values.
FORECAST_CONFIGS = ["dk1_lear", "de_lear"]
```

Replace with:

```python
FORECAST_CONFIGS = [
    "dk1_lear",
    "de_lear",
    "dk1_dnn",
    "de_dnn",
    "dk1_transformer",
    "de_transformer",
]
```

(The gating comment is removed because tuning is complete.)

- [ ] **Step 4: Commit deploy script**

Run:
```bash
git add src/schedules/src/schedules/deploy_forecast.py
git commit -m "$(cat <<'EOF'
feat(deploy): add DNN + Transformer to daily-forecast deployments

DNN configs (dk1_dnn, de_dnn) now carry tuned model_params from the
Optuna v1 study; Transformer configs use the paper's published HPs.
DRIFT_AREAS is unchanged — drift detection is per-area, so the existing
DK1 + DE drift flows cover all six new daily-forecast deployments.
retrain_on_drift stays False on the new configs pending operational soak.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 5: Open the PR**

Run:
```bash
git push -u origin <your-branch>
gh pr create --title "Model cleanup + DNN/Transformer deployment" --body "$(cat <<'EOF'
## Summary
- Drop unused models: XGBoost, GBT base, RandomForest, sklearn base
- Reorganise: `BaseModel` and `LightningModel` into `models/base/` subpackage
- Backfill `Generation` forecasts (2023-01-01 → 2026-04-28) for DK1 and DE
- Update configs to enforce a 2023-01-01 training floor (drop Lago's 4-year window)
- Tune DNN per market (35 trials, Optuna TPE, ex-ante on 2025 validation window)
- Deploy DNN + Transformer alongside LEAR (6 `daily-forecast-*` flows total)

Spec: `docs/superpowers/specs/2026-05-25-model-cleanup-and-deploy-design.md`.
Plan: `docs/superpowers/plans/2026-05-25-model-cleanup-and-deploy.md`.

## Test plan
- [x] Local: `pytest tests/ -q` passes after each refactor commit
- [x] Local: `forecast-cli backtest dk1_lear` runs with `[56, 84, 1092]`
- [x] Local: `forecast-cli predict {dk1_dnn,de_dnn,dk1_transformer,de_transformer} -d <today> --track` writes one `experiment_runs` row + 24 `experiment_predictions` rows + one `model_artifacts` row per config
- [ ] CD: post-merge, `daily-forecast-*` deployments visible in Prefect UI (6 total at `0 6 * * *`)
- [ ] CD: tomorrow's 06:00 UTC run completes cleanly for all six configs

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 6: Post-merge verification (after CI passes and PR is merged)**

The CD pipeline reruns `deploy_forecast.py` on the deploy host. After merge, verify:

```bash
# From any host with PREFECT_API_URL set:
uv run python -c "
from prefect.client.orchestration import get_client
import asyncio

async def main():
    async with get_client() as client:
        deps = await client.read_deployments()
        forecast_deps = sorted([d.name for d in deps if d.name.startswith('daily-forecast-')])
        print('Forecast deployments:', forecast_deps)

asyncio.run(main())
"
```

Expected output:
```
Forecast deployments: ['daily-forecast-de_dnn', 'daily-forecast-de_lear', 'daily-forecast-de_transformer', 'daily-forecast-dk1_dnn', 'daily-forecast-dk1_lear', 'daily-forecast-dk1_transformer']
```

(6 deployments, alphabetically sorted.)

---

## Summary of files changed

**Created:**
- `src/price_forecasting/src/price_forecasting/models/base/__init__.py`
- `src/price_forecasting/src/price_forecasting/models/base/abstract.py` (from `base.py`)
- `src/price_forecasting/src/price_forecasting/models/base/lightning.py` (from `lightning_base.py`)
- `configs/de_transformer.py`

**Deleted:**
- `src/price_forecasting/src/price_forecasting/models/xgboost_model.py`
- `src/price_forecasting/src/price_forecasting/models/gbt_base.py`
- `src/price_forecasting/src/price_forecasting/models/random_forest.py`
- `src/price_forecasting/src/price_forecasting/models/sklearn_base.py`
- `src/price_forecasting/src/price_forecasting/models/base.py` (moved)
- `src/price_forecasting/src/price_forecasting/models/lightning_base.py` (moved)

**Modified:**
- `src/price_forecasting/src/price_forecasting/models/__init__.py` (registry + imports)
- `src/price_forecasting/src/price_forecasting/models/dnn.py` (import path)
- `src/price_forecasting/src/price_forecasting/models/transformer.py` (import path)
- `src/price_forecasting/pyproject.toml` (drop `xgboost`)
- `tests/price_forecasting/test_models.py` (remove RF/XGBoost classes)
- `configs/dk1_lear.py`, `configs/de_lear.py` (calibration trim)
- `configs/dk1_dnn.py`, `configs/de_dnn.py` (dates + window + tuned params)
- `src/schedules/src/schedules/deploy_forecast.py` (FORECAST_CONFIGS)

**Data writes:**
- `algo.forecasts` — Generation rows for DK1 and DE from 2023-01-01 to 2026-04-28
- `algo.hyperparam_trials` — 35 × 2 (or 35 + 20) Optuna trials
- `algo.experiment_runs`, `algo.experiment_predictions`, `algo.model_artifacts` — verification predicts (4 rows in each, 24 in predictions)
