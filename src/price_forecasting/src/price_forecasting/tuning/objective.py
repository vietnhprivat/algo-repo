from typing import Any, Callable, Dict

import numpy as np
import optuna
import pandas as pd

from price_forecasting.backtesting.engine import BacktestEngine
from price_forecasting.configs import ExperimentConfig
from price_forecasting.data import clickhouse_loader
from price_forecasting.data.preprocessor import DataPreprocessor
from price_forecasting.evaluation.metrics import calculate_mae
from price_forecasting.models import get_model

# Search-space params consumed outside the model constructor (feature-selection
# flags and pre-processing / initialisation choices handled by the pipeline).
_NON_MODEL_PARAMS = frozenset(
    {
        "use_price_d_1", "use_price_d_2", "use_price_d_3", "use_price_d_7",
        "use_exog_d", "use_exog_d_1", "use_exog_d_7",
        "use_exog_set_1", "use_exog_set_2",
        "use_dummy",
        "preprocessing",
        "init_method",
    }
)

# Map search-space key → DNNModel / LightningModel constructor kwarg where they differ.
_PARAM_REMAP: Dict[str, str] = {
    "n_neurons": "hidden_units",
}


def _extract_model_kwargs(params: Dict[str, Any]) -> Dict[str, Any]:
    """Filter and remap search-space params to DNNModel constructor kwargs."""
    model_kwargs: Dict[str, Any] = {}
    for key, value in params.items():
        if key in _NON_MODEL_PARAMS:
            continue
        mapped_key = _PARAM_REMAP.get(key, key)
        model_kwargs[mapped_key] = value
    return model_kwargs


def dnn_validation_objective(
    trial: optuna.Trial,
    config: ExperimentConfig,
    search_space_fn: Callable[[optuna.Trial], Dict[str, Any]],
) -> float:
    """Train a DNN at each val day with TPE-suggested HPs; return mean MAE."""
    params = search_space_fn(trial)
    model_kwargs = _extract_model_kwargs(params)

    raw_df = clickhouse_loader.load_dataset(config)
    preprocessor = DataPreprocessor(config)
    features, targets = preprocessor.build_dataset(dataframe=raw_df)

    val_start = pd.Timestamp(config.val_start_date)
    val_end = pd.Timestamp(config.val_end_date)
    val_dates = features.index[
        (features.index >= val_start) & (features.index <= val_end)
    ]
    val_dates = val_dates.intersection(targets.index)

    if len(val_dates) == 0:
        return float("inf")

    engine = BacktestEngine(config)

    def factory() -> Any:
        return get_model(config.model_type, **model_kwargs)

    errors = []
    for day in val_dates:
        prediction = engine._ensemble_forecast(factory, features, targets, day)
        actual = targets.loc[day].values
        errors.append(calculate_mae(actual, prediction))
    return float(np.mean(errors))
