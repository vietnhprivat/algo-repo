# Contributing

## Setup

1. Install `uv`: <https://docs.astral.sh/uv/>
2. Clone and sync: `uv sync`
3. Bring up the stack: `docker-compose up -d`
4. Run migrations: `uv run python -m infrastructure_clickhouse.migrations.run_migrations`
5. Run tests: `uv run python -m pytest tests/ -v`

## Conventions

- Curve names use **spaces**: `ENTSOE DK1 TotalLoad Dayahead`.
- Migrations are append-only — never edit an existing numbered file.
- Avoid `print()` in `schedules/*` or `infrastructure_*`; use the module logger with `build_log_extra(**context)`.
- New configs go in `configs/<area>_<model>.py` and follow the pattern of `dk1_lear.py`.
- Tests use the `class Test<Feature>:` pattern.

## Branching and PRs

- Branch from `main`; keep PRs focused (one feature or fix).
- CI runs `ruff` and `pytest`; both must pass.
- On merge, `cd_deploy.yml` rebuilds the image and redeploys Prefect.

## Adding a new area

1. Run a backfill: `data-cli entsoe backfill price-document -a XX -s ... -e ...`
2. Confirm the area is in the `AREAS` list in `deploy_ingestion.py`.
3. Create `configs/<xx>_lear.py` (and optionally `<xx>_dnn.py`).
4. Add config name to `FORECAST_CONFIGS` and area to `DRIFT_AREAS` in `deploy_forecast.py`.
5. Redeploy: `PREFECT_API_URL=... uv run python src/schedules/src/schedules/deploy_forecast.py`.

## Adding a new feature transformer

See `src/price_forecasting/data/transformers.py`. Subclass `FeatureTransformer`, implement `transform(hourly_df, daily_prices) -> pd.DataFrame`. Add to `default_transformers_for_model` only if it belongs in defaults.

## Modeling research alignment

LEAR follows Lago et al. 2021 §4.2. Calibration windows for LEAR ensemble are `[56, 84, 1092, 1456]`. Target uses `asinh` variance-stabilization. Any deviation from the paper should be documented in the config docstring.

DNN follows Lago §4.3.3. Hyperparameters are tuned via `forecast-cli tune <config>` (Optuna TPE, 11 binary + 8 numeric HPs). At serving time, `n_dnn_ensemble=4` averages 4 DNNs with distinct random seeds (Lago §4.4).

## Tuning a config

```bash
uv run python -m forecast_cli.main tune dk1_dnn --n-trials 100
```

The config must declare `val_start_date` and `val_end_date`. Trials persist to `algo.hyperparam_trials`. After tuning, paste the best params into the config's `model_params` dict and commit.
