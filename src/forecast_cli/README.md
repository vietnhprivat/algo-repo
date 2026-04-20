# forecast-cli

Typer CLI for running backtests and live price predictions. Config files are Python modules in `configs/` at the repo root. Results can optionally be tracked to ClickHouse with `--track`.

---

## Commands

```bash
uv run python -m forecast_cli.main <command> [options]
```

| Command | Usage | Purpose |
|---------|-------|---------|
| `backtest` | `backtest <config_name> [--track]` | Walk-forward backtest over the config's test window |
| `predict` | `predict <config_name> -d <date> [--track]` | Single-date live prediction using the full ensemble |

### `backtest`

```bash
uv run python -m forecast_cli.main backtest dk1_lear
uv run python -m forecast_cli.main backtest dk1_lear --track
```

Prints MAE, RMSE, sMAPE (and rMAE vs weekly naive) to stdout. With `--track`, stores to ClickHouse and prints the `run_id`.

### `predict`

```bash
uv run python -m forecast_cli.main predict dk1_lear -d 2026-03-22
uv run python -m forecast_cli.main predict dk1_lear -d 2026-03-22 --track
```

Prints a 24- or 96-period price table (Period | hh:mm | Price). With `--track`, serializes trained models and stores everything to ClickHouse.

---

## `--track` Flag

| What gets written | `backtest --track` | `predict --track` |
|-------------------|--------------------|-------------------|
| `algo.experiment_runs` row | Yes | Yes |
| `algo.experiment_predictions` rows | Yes (wide→long reshape) | Yes |
| `algo.model_artifacts` blob | No | Yes (joblib + base64) |
| `training_duration_seconds` | No | Yes |
| `data_start_utc` / `data_end_utc` | No | Yes |
| `model_artifact_id` on run | No | Yes |

Live predictions store `actual = 0.0` initially. The `reconcile-predictions` Prefect flow backfills actuals and computes metrics daily at 18:00 UTC.

---

## Config Files

Config files live in `configs/` at the repo root. The config name passed to the CLI is the filename without `.py`.

**Example:** `configs/dk1_lear.py` → config name `dk1_lear`

```python
# configs/dk1_lear.py
from price_forecasting.configs import ExperimentConfig

config = ExperimentConfig(
    experiment_name="dk1_lear",
    results_dir="results/",
    area="DK1",
    test_start_date="2024-01-01",
    test_end_date="2024-12-31",
    model_type="LEAR",
    exogenous_curve_types=["TotalLoad"],
    calibration_windows=[56, 84, 1092, 1456],
)
```

The module must expose a top-level `config` attribute of type `ExperimentConfig`. `config_loader.py` loads it via `importlib` — full IDE support, no YAML parsing.

**Docker:** configs are volume-mounted at `/app/configs`. If the directory is missing, `config_loader.py` exits with a clear error explaining the Docker volume flag.

---

## `tracking.py`

### `track_prediction(config, target_date, predictions, *, training_duration_seconds, data_start_utc, data_end_utc, trained_models, config_name) → str`

Steps:
1. Generate `run_id` (UUID4) and current UTC timestamp
2. If `trained_models` provided: serialize via `joblib` → `BytesIO` → base64 string; insert `algo.model_artifacts` row; capture `artifact_id`
3. Insert `algo.experiment_runs` row (includes metadata keyword args and `model_artifact_id`)
4. Reshape predictions `pd.Series` to long-format `pl.DataFrame` (`run_id, timestamp_utc, actual=0.0, predicted`)
5. Insert `algo.experiment_predictions` rows
6. Return `run_id`

Period-to-timestamp mapping: `minutes_per_period = 1440 // n_periods` (60 min for hourly, 15 min for quarter-hourly).

### `track_backtest_run(config, forecasts, actuals, metrics) → str`

Same as above minus model artifact. Reshapes wide-format DataFrames (days × periods) to long format before insert.

---

## Module Layout

```
forecast_cli/
├── main.py          # Typer app: backtest + predict commands
├── tracking.py      # ClickHouse tracking for runs, predictions, artifacts
└── config_loader.py # Dynamic Python module loading from configs/
```
