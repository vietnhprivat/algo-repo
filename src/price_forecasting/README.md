# price_forecasting

Electricity day-ahead price forecasting package. Implements the **LEAR** (Lasso Estimated AutoRegressive) model with a multi-window ensemble backtesting engine, plus a live prediction runner for single-date forecasts.

---

## Table of Contents

1. [Overview](#overview)
2. [Methodology](#methodology)
3. [Module Map](#module-map)
4. [Module Reference](#module-reference)
5. [Data Flow](#data-flow)
6. [Configuration Reference](#configuration-reference)
7. [Usage Guide](#usage-guide)

---

## Overview

The package takes hourly (or 15-min) energy price timeseries from ClickHouse, engineers a feature matrix, and trains/evaluates forecasting models using a rolling-window ensemble strategy. It supports:

- **Backtesting** — walk-forward evaluation over a historical test period
- **Live prediction** — single-date ensemble forecast for deployment

The primary entry points are `BacktestRunner.execute()` and `LiveRunner.run_live()`, both configured via `ExperimentConfig`.

---

## Methodology

### Feature Engineering

For a given target date `D`, the model sees no data from `D` — only data available at prediction time (day-ahead).

Features are built in three blocks:

| Block | What | Shape |
|---|---|---|
| Price lags | Daily price matrix shifted by d-1, d-2, d-3, d-7 | `4 × n_periods` |
| Exogenous | Day-ahead forecasts for each exogenous curve: d0, d-1, d-7 | `n_exog × 3 × n_periods` |
| Calendar | One-hot day-of-week dummies | `7` |

All features and targets are standardised with `StandardScaler` (fitted on training data only — no leakage).

### LEAR Model

LEAR trains a separate **Lasso regression** for each period of the day (24 models for hourly data, 96 for 15-min). Each Lasso learns which lags and exogenous signals matter for that specific hour.

This follows the approach from:
> *Lago, J., De Ridder, F., & De Schutter, B. (2018). Forecasting spot electricity prices: Deep learning approaches and empirical comparison of traditional algorithms.*

With a fixed `alpha`, each Lasso is trained with `TimeSeriesSplit` CV to avoid look-ahead bias. If `lasso_alphas` are provided, `LassoCV` selects the best alpha per period.

### Multi-Window Ensemble

Rather than picking a single training window, the engine trains the model on **multiple calibration windows** (e.g. 56, 84, 1092, 1456 days) and averages the predictions. This hedges against window-length sensitivity and captures both short-term regime shifts and long-run seasonality.

For each test date, the flow is:
```
for window in calibration_windows:
    train on [D - window, D-1]
    predict D

ensemble = mean(predictions across windows)
```

Models are cached per window and only retrained every `refit_interval_days` days (default: 1), allowing cheaper daily re-use when set higher.

### Resolution Awareness

The pipeline auto-detects whether data is hourly (24 periods/day) or 15-minute (96 periods/day) by inspecting the median timestamp diff. `24` is never hardcoded — `n_periods` is always derived from the data shape or `_detect_n_periods()`.

---

## Module Map

```
price_forecasting/
├── __init__.py              # Central re-export hub
├── live_runner.py           # LiveRunner — single-date prediction
│
├── configs/
│   └── experiment.py        # ExperimentConfig dataclass
│
├── models/
│   ├── base.py              # BaseModel abstract interface
│   ├── lear.py              # LearModel — per-period Lasso ensemble
│   ├── dnn.py               # DNNModel — placeholder
│   └── __init__.py          # MODEL_REGISTRY + get_model() factory
│
├── data/
│   ├── clickhouse_loader.py # load_price_series, load_exogenous_series, load_dataset
│   └── preprocessor.py      # DataPreprocessor — feature engineering + scaling
│
├── backtesting/
│   ├── engine.py            # BacktestEngine — sliding window ensemble loop
│   ├── runner.py            # BacktestRunner (+ BaseRunner) — pipeline orchestrator
│   ├── splitting.py         # split_dataset, split_by_dates, SplitResult
│   └── __init__.py
│
└── evaluation/
    ├── metrics.py           # MAE, RMSE, sMAPE, MAPE, rMAE
    ├── summary.py           # compute_metrics_summary, compute_metrics_per_hour
    └── __init__.py
```

---

## Module Reference

### `configs/experiment.py` — ExperimentConfig

Single dataclass that drives the entire pipeline.

```python
@dataclass
class ExperimentConfig:
    experiment_name: str           # Identifier used in output filenames and DB tracking
    results_dir: str               # Directory to write CSVs and JSON metrics
    area: str                      # Market area, e.g. "DK1", "DE"

    target_column: str = "price"

    # Preferred: explicit test window (reproducible, comparable across runs)
    test_start_date: Optional[str] = None
    test_end_date: Optional[str] = None

    # Fallback: ratio-based split
    train_ratio: float = 0.7
    validation_ratio: float = 0.15
    test_ratio: float = 0.15

    calibration_windows: List[int] = [56, 84, 1092, 1456]  # days per window
    refit_interval_days: int = 1

    model_type: str = "LEAR"
    exogenous_curve_types: list[str] = field(default_factory=list)
    model_params: Dict[str, Any] = field(default_factory=dict)
```

---

### `models/` — Model Layer

#### `base.py`

Abstract interface that `BacktestEngine` codes against. Any new model must implement:

```python
class BaseModel(ABC):
    def fit(self, features: np.ndarray, targets: np.ndarray) -> None: ...
    def predict_day(self, features: np.ndarray) -> np.ndarray: ...
```

- `features` shape: `(n_days, n_features)`
- `targets` shape: `(n_days, n_periods)`
- `predict_day` returns `(n_periods,)` for a single day

#### `lear.py` — LearModel

One `Lasso` (or `LassoCV`) per period. Trained independently per hour.

```python
LearModel(
    alpha=0.01,                 # Fixed regularisation (used if lasso_alphas is None)
    maximum_iterations=5000,
    cross_validation_folds=5,
    lasso_alphas=None,          # Provide to enable LassoCV alpha selection
)
```

After `fit()`, `self.hourly_models: Dict[int, Lasso]` holds one model per period index.

#### `__init__.py` — Registry

```python
MODEL_REGISTRY = {"lear": LearModel, "dnn": DNNModel}

get_model(name: str, **kwargs) -> BaseModel
```

`get_model` is case-insensitive. `**kwargs` are forwarded to the model constructor, sourced from `ExperimentConfig.model_params`.

---

### `data/` — Data Layer

#### `clickhouse_loader.py`

Queries `algo.timeseries` and `algo.forecasts` from ClickHouse.

| Function | Returns |
|---|---|
| `load_price_series(client, area)` | `DataFrame` with DatetimeIndex and `price` column |
| `load_exogenous_series(client, area, curve_types)` | `DataFrame` with one column per curve type |
| `load_dataset(config)` | Combined `DataFrame` (price + exogenous, inner join) |

Curve naming conventions:
- Price: `"ENTSOE {area} EnergyPrice %"`
- Exogenous: `"ENTSOE {area} {curve_type} Dayahead"`

Both functions deduplicate on `timestamp_utc` (keeps last), as required by `ReplacingMergeTree`.

#### `preprocessor.py` — DataPreprocessor

```python
preprocessor = DataPreprocessor(config)
features, targets = preprocessor.build_dataset(dataframe=None)
```

`build_dataset` returns two aligned DataFrames, both indexed by date:
- `features`: shape `(n_days, n_feature_cols)` — all lag/exogenous/calendar features
- `targets`: shape `(n_days, n_periods)` — daily pivoted price matrix, columns `price_p0..pN`

Rows with any NaN are dropped from both before returning (so they stay aligned).

Scaling is done separately in `BacktestEngine` per window, to avoid future leakage:

```python
# Called per window inside engine
features_train_scaled, targets_train_scaled, features_test_scaled = \
    preprocessor.transform_data(features_train, targets_train, features_test)

# For live prediction
features_scaled = preprocessor.transform_features(features)
predictions = preprocessor.inverse_transform_predictions(raw_predictions)
```

---

### `backtesting/` — Backtesting Layer

#### `splitting.py`

```python
# Preferred: reproducible, date-anchored test window
split = split_by_dates(features, targets, "2024-01-01", "2025-01-01")

# Fallback: ratio-based
split = split_dataset(features, targets, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15)
```

Both return `SplitResult(train, validation, test)` where each is a `DatasetSplit(features, targets)`.

`split.test.dates` gives the `DatetimeIndex` of test dates, which is passed to `BacktestEngine.run()`.

#### `engine.py` — BacktestEngine

The core evaluation loop. Takes a `model_factory` callable so it can instantiate fresh models per window without knowing the model type.

```python
engine = BacktestEngine(config)
forecasts_df, actuals_df = engine.run(model_factory, features, targets, test_dates)
```

Both returned DataFrames have shape `(n_test_days, n_periods)` with columns `h0..hN`.

Internal state `_window_state: Dict[int, WindowState]` caches the last-fit model and preprocessor per window to avoid unnecessary refits when `refit_interval_days > 1`.

#### `runner.py` — BacktestRunner

Full pipeline orchestrator. Wires together all other components.

```python
runner = BacktestRunner(config)
outputs = runner.execute()  # or runner.execute(dataframe=df) to skip ClickHouse
```

`execute()` saves four files to `config.results_dir`:

| File | Content |
|---|---|
| `{name}_forecasts.csv` | Predicted prices (days × periods) |
| `{name}_actuals.csv` | Actual prices (days × periods) |
| `{name}_metrics.json` | Overall MAE, RMSE, sMAPE, rMAE |
| `{name}_metrics_per_hour.csv` | Same metrics broken down by hour |

`BaseRunner` holds the shared logic (`_get_model_factory`, `_load_and_preprocess_data`, `_split_data`) used by both `BacktestRunner` and `LiveRunner`.

---

### `evaluation/` — Metrics Layer

#### `metrics.py`

Stateless metric functions operating on flat `np.ndarray`:

| Function | Formula |
|---|---|
| `calculate_mae` | `mean(\|y - ŷ\|)` |
| `calculate_rmse` | `sqrt(mean((y - ŷ)²))` |
| `calculate_smape` | `mean(2\|y - ŷ\| / (\|y\| + \|ŷ\|)) × 100` |
| `calculate_mape` | `mean(\|y - ŷ\| / \|y\|) × 100` |
| `calculate_rmae` | `MAE(y, ŷ) / MAE(y, y_naive)` — skill score vs naive baseline |

#### `summary.py`

```python
naive = build_weekly_naive(actuals)  # shift actuals by 7 days

summary = compute_metrics_summary(forecasts, actuals, naive)
# → {"mae": ..., "rmse": ..., "smape": ..., "rmae": ...}

per_hour = compute_metrics_per_hour(forecasts, actuals, naive)
# → DataFrame with columns [hour, mae, rmse, smape, rmae]
```

`build_weekly_naive` shifts the actuals DataFrame by 7 rows (same weekday last week) — the standard naive benchmark for electricity price forecasting.

---

### `live_runner.py` — LiveRunner

Single-date prediction using the same ensemble logic as the backtest engine.

```python
runner = LiveRunner(config)
predictions = runner.run_live("2026-03-22")
# → pd.Series, index ["p0", "p1", ..., "p23"], name="2026-03-22"
```

Internally calls `BacktestEngine._ensemble_forecast()` directly for the given date. The historical data loaded from ClickHouse is used as the training pool — no test split needed.

---

## Data Flow

### Backtest

```
ExperimentConfig
      │
      ▼
BacktestRunner.execute()
      │
      ├─ DataPreprocessor.build_dataset()
      │       ├─ load_dataset(config)         ← ClickHouse
      │       ├─ _pivot_to_daily(price)
      │       ├─ _build_price_lags()          ← d-1, d-2, d-3, d-7
      │       ├─ _build_exogenous_features()  ← d0, d-1, d-7 per curve
      │       └─ _add_calendar_dummies()      ← day-of-week one-hot
      │       → (features_df, targets_df)
      │
      ├─ split_by_dates() / split_dataset()
      │       → SplitResult.test.dates
      │
      ├─ BacktestEngine.run(model_factory, features, targets, test_dates)
      │       └─ for each date D:
      │               └─ for each window W in [56, 84, 1092, 1456]:
      │                       ├─ _slice_data()           ← [D-W, D-1] train + D test
      │                       ├─ preprocessor.transform_data()
      │                       ├─ model.fit()             ← only if refit needed
      │                       └─ model.predict_day()
      │               → mean across windows
      │       → (forecasts_df, actuals_df)
      │
      ├─ build_weekly_naive(actuals)
      ├─ compute_metrics_summary()
      ├─ compute_metrics_per_hour()
      └─ _save_outputs()  → CSVs + JSON
```

### Live Prediction

```
ExperimentConfig + target_date
      │
      ▼
LiveRunner.run_live(target_date)
      │
      ├─ DataPreprocessor.build_dataset()     ← same as backtest
      │
      └─ BacktestEngine._ensemble_forecast(target_date)
              └─ for each window W:
                      ├─ _slice_data()
                      ├─ transform → fit → predict
              → mean across windows
      → pd.Series(predictions)
```

---

## Configuration Reference

### Minimal config

```python
from price_forecasting.configs import ExperimentConfig

config = ExperimentConfig(
    experiment_name="dk1_lear_2024",
    results_dir="results/",
    area="DK1",
    test_start_date="2024-01-01",
    test_end_date="2024-12-31",
)
```

### With exogenous features and custom model params

```python
config = ExperimentConfig(
    experiment_name="dk1_lear_load",
    results_dir="results/",
    area="DK1",
    test_start_date="2024-01-01",
    test_end_date="2024-12-31",
    exogenous_curve_types=["TotalLoad"],
    model_type="LEAR",
    model_params={"alpha": 0.005},
    calibration_windows=[56, 84, 364, 728],
    refit_interval_days=7,  # refit weekly instead of daily
)
```

Config files for the CLI live in `configs/` at the repo root (e.g. `configs/dk1_lear.py`). The filename without `.py` is the config name used by `forecast_cli`.

---

## Usage Guide

### Run a backtest

```bash
# Via CLI (config file in configs/)
uv run python -m forecast_cli.main backtest dk1_lear

# With experiment tracking to ClickHouse
uv run python -m forecast_cli.main backtest dk1_lear --track
```

```python
# Programmatically
from price_forecasting import BacktestRunner
from price_forecasting.configs import ExperimentConfig

config = ExperimentConfig(...)
runner = BacktestRunner(config)
outputs = runner.execute()

forecasts = outputs["forecasts"]  # DataFrame (days × periods)
actuals = outputs["actuals"]
```

### Run a live prediction

```bash
uv run python -m forecast_cli.main predict dk1_lear -d 2026-03-22
```

```python
from price_forecasting import LiveRunner

runner = LiveRunner(config)
predictions = runner.run_live("2026-03-22")
# pd.Series with n_periods values
```

### Evaluate results manually

```python
from price_forecasting.evaluation import (
    build_weekly_naive,
    compute_metrics_summary,
    compute_metrics_per_hour,
)

naive = build_weekly_naive(actuals)
summary = compute_metrics_summary(forecasts, actuals, naive)
per_hour = compute_metrics_per_hour(forecasts, actuals, naive)
```

### Inject a DataFrame (skip ClickHouse — useful in tests)

```python
runner = BacktestRunner(config)
outputs = runner.execute(dataframe=my_df)
```

The same `dataframe=` parameter is available on `LiveRunner.run_live()`.
