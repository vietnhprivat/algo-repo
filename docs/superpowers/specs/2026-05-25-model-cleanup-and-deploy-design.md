# Model cleanup + DNN/Transformer deployment

> **Status:** Design (brainstormed 2026-05-25). Implementation plan to follow via `writing-plans` skill.

## Goal

1. Remove the four unused model families (XGBoost, GBT base, RandomForest, sklearn base) from `price_forecasting.models`.
2. Reorganise the remaining model module so the abstract base classes live in a dedicated `base/` subpackage, separating framework code from concrete model implementations.
3. Deploy the DNN (Lago §4.3) and Transformer (Llorente & Portela 2025) models to Prefect alongside the existing LEAR deployments, with calibration windows and dataset splits adjusted so no model training set crosses into the 2022 European energy crisis.

The deliverable is a production system where every model in `MODEL_REGISTRY` is also a deployed daily-forecast flow, and every model the thesis discusses in detail (LEAR, DNN, Transformer) is exercised by the live pipeline.

## Motivation

Today's `MODEL_REGISTRY` advertises five models — `lear`, `dnn`, `rf`, `transformer`, `xgboost` — but only `lear` is wired into `FORECAST_CONFIGS`. The DNN configs ship with placeholder hyperparameters, the Transformer is research-only, and RandomForest / XGBoost are unused vestiges from earlier experimentation. The thesis chapters evaluate LEAR, DNN, and Transformer; the production system should match.

In addition, the post-2022 macroeconomic regime is structurally different from the crisis year (intraday price volatility was 5–10× normal during the 2022 European energy crisis). Training models on a window that straddles 2022 contaminates the validation and test sets with a non-representative regime. Excluding 2022 from training is a deliberate methodological choice for the thesis evaluation.

## Architecture

### Section 0 — Prerequisite: backfill Generation forecasts

The Transformer configs use `Generation` as an exogenous curve. Today `algo.forecasts` only contains Generation rows from **2026-04-29 onwards** for both DK1 and DE — far short of the 1092-day calibration window from test_start 2026-01-01, which needs Generation back to 2023-01-04. Without backfill, the Transformer backtest (and the Section 4 verification predict) will join Generation against an empty range, drop all training rows, and fail.

Backfill, respecting the 2023-01-01 training floor:

```bash
uv run python -m data_cli.main entsoe backfill generation-forecast -a DK1 -s 2023-01-01 -e 2026-04-28
uv run python -m data_cli.main entsoe backfill generation-forecast -a DE  -s 2023-01-01 -e 2026-04-28
```

Default processtype `A01` (day-ahead) matches what the existing scheduler ingests. ENTSO-E rate limit (400/60s) and 10-month forecast chunks mean each command finishes in a few minutes. `ReplacingMergeTree` makes the backfill idempotent.

**Verification:** after backfill, `SELECT min(timestamp_utc), max(timestamp_utc), count() FROM algo.forecasts FINAL WHERE curve_name LIKE 'ENTSOE DK1 Generation%'` should return min ≤ 2023-01-01 and a row count of roughly `1218 days × 24h ≈ 29 232`.

This section is independent of Sections 1–4 and can run in parallel with the refactor in wall-clock time.

### Section 1 — Model cleanup and `base/` subpackage

Delete:

- `src/price_forecasting/src/price_forecasting/models/xgboost_model.py`
- `src/price_forecasting/src/price_forecasting/models/gbt_base.py`
- `src/price_forecasting/src/price_forecasting/models/random_forest.py`
- `src/price_forecasting/src/price_forecasting/models/sklearn_base.py`
- All matching tests under `tests/price_forecasting/models/` for the four files above.

Reorganise:

```
src/price_forecasting/src/price_forecasting/models/
├── base/
│   ├── __init__.py        # re-exports BaseModel, LightningModel
│   ├── abstract.py        # was base.py — BaseModel ABC
│   └── lightning.py       # was lightning_base.py — LightningModel
├── __init__.py            # MODEL_REGISTRY trimmed to {lear, dnn, transformer}
├── lear.py
├── dnn.py
└── transformer.py
```

Import surface:

- `from price_forecasting.models.base import BaseModel` — unchanged for callers (now a subpackage `__init__.py` rather than a module).
- `from price_forecasting.models.lightning_base import LightningModel` → `from price_forecasting.models.base import LightningModel`.
- Update every internal call site identified by `rg "models\.lightning_base"` and `rg "models\.gbt_base|models\.sklearn_base|models\.random_forest|models\.xgboost_model"`.

`models/__init__.py` after cleanup:

```python
from price_forecasting.models.base import BaseModel as BaseModel
from price_forecasting.models.base import LightningModel as LightningModel
from price_forecasting.models.lear import LearModel as LearModel
from price_forecasting.models.dnn import DNNModel as DNNModel
from price_forecasting.models.transformer import TransformerModel as TransformerModel

__all__ = ["BaseModel", "LightningModel", "LearModel", "DNNModel", "TransformerModel", "get_model"]

MODEL_REGISTRY = {
    "lear": LearModel,
    "dnn": DNNModel,
    "transformer": TransformerModel,
}

def get_model(name: str, **kwargs) -> BaseModel:
    key = name.lower()
    if key not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model: {name}. Available: {list(MODEL_REGISTRY.keys())}")
    return MODEL_REGISTRY[key](**kwargs)
```

`pyproject.toml`: remove `xgboost` from the `price_forecasting` package dependencies if present. Keep `scikit-learn` (LEAR depends on it) and `lightning` (DNN and Transformer depend on it).

### Section 2 — Config updates enforcing the 2022 floor

The training data floor is **2023-01-01**. Configs must not request a calibration slice whose start date dips into 2022. The engine itself has no data floor — enforcement is via the configs' calibration windows and val/test dates.

#### LEAR (`configs/dk1_lear.py`, `configs/de_lear.py`)

| Field | Before | After |
|---|---|---|
| `calibration_windows` | `[56, 84, 1092, 1456]` | `[56, 84, 1092]` |

`1092` on test_start `2026-01-01` → 2023-01-04, post-floor. `1456` would dip to 2022-01-06.

#### DNN (`configs/dk1_dnn.py`, `configs/de_dnn.py`)

| Field | Before | After |
|---|---|---|
| `calibration_windows` | `[1456]` | `[730]` |
| `val_start_date` | `2023-07-30` | `2025-01-01` |
| `val_end_date` | `2024-05-19` | `2025-10-23` |
| `test_start_date` | `2024-05-20` | `2025-10-24` |
| `test_end_date` | `2026-05-19` | `2026-05-19` (unchanged) |
| `model_params` | placeholder dict | replaced after Section 3 |

Sanity: tune target_date `2025-01-01` − `730` = `2023-01-02`, post-floor. Validation window is ≈42 weeks (per Lago §4.3.3 checklist).

#### Transformer DK1 (`configs/dk1_transformer.py`)

No changes — `calibration_windows=[1092]`, `test_start_date="2026-01-01"` → slice from `2023-01-04`, already post-floor.

#### Transformer DE (new file `configs/de_transformer.py`)

Mirror `dk1_transformer.py` exactly, swapping:

- `experiment_name = "de_transformer"`
- `area = "DE"`

All other fields (calibration window, dates, model_params, feature transformers) identical. The thesis can then report DK1 and DE Transformer numbers side-by-side without further config work.

### Section 3 — DNN hyperparameter tuning

Two Optuna TPE studies, run locally, persisting trials to `algo.hyperparam_trials`. Lago §4.3.3 specifies 1500 iterations; we run 35 per market with a methodological footnote acknowledging the reduced budget under thesis deadline. The validation-set check (checklist item #9, "hyperparameters estimated ex-ante on a held-out validation window") still passes.

Steps:

1. **Time DK1** — `time uv run python -m forecast_cli.main tune dk1_dnn -n 35 --study-name dk1_dnn_tune_v1`.
2. **Run DE** — `time uv run python -m forecast_cli.main tune de_dnn -n 35 --study-name de_dnn_tune_v1`.
3. **Extract best params** per study from `algo.hyperparam_trials`:

   ```sql
   SELECT params_json
   FROM algo.hyperparam_trials FINAL
   WHERE study_name = 'dk1_dnn_tune_v1' AND state = 'COMPLETE'
   ORDER BY value ASC
   LIMIT 1;
   ```

4. **Paste into configs** with documented `n_neurons` → `hidden_units` rename (see `tuning/objective.py::_PARAM_REMAP`). The 6 tuned HPs map to `DNNModel.__init__`:

   | Optuna key | Config key |
   |---|---|
   | `n_neurons` | `hidden_units` |
   | `activation` | `activation` |
   | `dropout` | `dropout` |
   | `learning_rate` | `learning_rate` |
   | `batch_norm` | `batch_norm` |
   | `l1_reg` | `l1_reg` |

   Non-tuned fields (`epochs`, `early_stopping_patience`, etc.) retain their current placeholder values.

5. **Sanity-check** that no best param sits on the boundary of its search space (would indicate the range was too narrow).

6. **Commit configs** with the tuned params.

**Time budget fallback:** if step 1 takes more than ~2 hours, drop to 20 trials for DE and footnote the asymmetry. Decision is made after step 1, not pre-committed.

### Section 4 — Deploy DNN + Transformer flows

Edit `src/schedules/src/schedules/deploy_forecast.py`:

```python
FORECAST_CONFIGS = [
    "dk1_lear", "de_lear",
    "dk1_dnn", "de_dnn",
    "dk1_transformer", "de_transformer",
]
```

Remove the gating comment ("DNN configs ship with placeholder hyperparameters and are excluded…"); its precondition is now satisfied.

`DRIFT_AREAS = ["DK1", "DE"]` is unchanged — drift detection is per-area, not per-config, so the existing drift flows already cover all six new daily-forecast deployments.

`retrain_on_drift=False` stays on all new configs. Flipping it would mean each drift event triggers a multi-hour Lightning retrain. That switch is operationally riskier than this spec wants to bundle in and is recorded as **out of scope**.

#### Pre-deploy verification

Before merging, run one local predict per new config to confirm the wire-up end-to-end (data load, transformer pipeline, model fit, ensemble averaging, ClickHouse write, model_artifact storage):

```bash
uv run python -m forecast_cli.main predict dk1_dnn         -d 2026-05-25 --track
uv run python -m forecast_cli.main predict de_dnn          -d 2026-05-25 --track
uv run python -m forecast_cli.main predict dk1_transformer -d 2026-05-25 --track
uv run python -m forecast_cli.main predict de_transformer  -d 2026-05-25 --track
```

Each should write:

- 1 row to `algo.experiment_runs` (with `experiment_name='live_*'`, populated `training_duration_seconds`, `data_start_utc`, `data_end_utc`, `model_artifact_id`)
- 24 rows to `algo.experiment_predictions` (one per hour, `actual=0.0` placeholder)
- 1 row to `algo.model_artifacts` (joblib-pickled ensemble dict, base64-encoded)

A failure here blocks the deploy.

#### Production deploy

`cd_deploy.yml` fires on merge to `main`, SSHes the deploy host, and reruns `deploy_forecast.py`. No manual deploy step is required from the developer's machine.

## Order of operations

Single PR or PR-stack, in this commit order:

1. **Section 0** — kick off Generation backfill (no commit; data lands in ClickHouse). Can run concurrently with Section 1.
2. **Section 1** — refactor commits (deletions, `base/` move, import updates, registry update). Tests should still pass after this commit.
3. **Section 2** — config edits (LEAR window trim, DNN dates + window, new `de_transformer.py`).
4. **Section 3** — tune runs locally → tuned `model_params` commit. Requires Section 0 complete only if a tune config used Generation (currently only Transformer does, so DNN tune is independent).
5. **Section 4** — `deploy_forecast.py` edit + pre-deploy verification. Requires Section 0 complete (Transformer predict needs Generation history).
6. Open PR → CI → merge → CD deploys.

## Out of scope

- **Quantitative metrics chapter (§5.2 of the report).** The original quantitative-system-metrics plan (`docs/superpowers/plans/2026-05-23-quantitative-system-metrics.md`) is parked. After this spec lands, that plan's "replay 90 days of historical operation" approach becomes viable because (a) all three model families will be deployed and (b) the configs respect a defensible training-data floor.
- **`retrain_on_drift=True` for DNN / Transformer.** Will be decided after the new flows have run cleanly for several days.
- **Lago HP search dimensions not yet exposed in code.** `preprocessing` and `init_method` (Lago §4.3.3) remain deferred until the preprocessor and `DNNModel.__init__` expose constructor toggles for them. Documented in `CLAUDE.md` already.
- **Tuning the Transformer.** The paper's published hyperparameters are used as-is. A future spec can add an Optuna search over the Transformer's HPs.
- **Trimming 2022 data from ClickHouse.** Enforcement is via config dates only; no DB writes.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Tune takes longer than expected, blocking the deploy commit | Step 1 of Section 3 is a wall-clock measurement; reduce DE trial count if needed. |
| Tuned HPs sit on the search-space boundary | Step 5 of Section 3 explicitly checks; widen the range and rerun if so. |
| ENTSO-E rejects historical generation-forecast requests (rate limit or unavailable processtype) | Section 0 verification step confirms expected row count; if rejected, fall back to dropping `Generation` from the Transformer exogenous list and footnote in the chapter. |
| CD deploy reruns `deploy_forecast.py` against placeholder configs if Section 3 is skipped | Section 4 commit must come after Section 3 commit; PR review enforces this. |

## Verification checklist

- [ ] After Section 0: `algo.forecasts` has Generation rows from ≤ 2023-01-01 for both DK1 and DE.
- [ ] `pytest tests/ -v` passes after Section 1.
- [ ] `uv run python -m forecast_cli.main backtest dk1_lear` runs cleanly with the new `[56, 84, 1092]` calibration list.
- [ ] `algo.hyperparam_trials` shows 35 `COMPLETE` rows per study after Section 3.
- [ ] No best param lands at the edge of its search-space range.
- [ ] All four predict invocations in Section 4's pre-deploy verification write the expected rows to ClickHouse.
- [ ] Post-merge CD run reaches "deploy succeeded" and the Prefect UI shows six `daily-forecast-*` deployments scheduled at `0 6 * * *`.
