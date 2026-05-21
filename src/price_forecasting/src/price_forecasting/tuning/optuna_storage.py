import json
from datetime import datetime, timezone
from typing import Callable, Protocol

import optuna

from observability_wandb.optuna_callback import build_wandb_sweep_callback as build_wandb_callback  # noqa: F401 — re-exported for forecast_cli.tune


class _SupportsInsert(Protocol):
    def insert_hyperparam_trial(self, **kwargs) -> None: ...


def build_persistence_callback(
    *,
    client: _SupportsInsert,
    study_name: str,
    area: str,
    model_type: str,
    config_name: str,
    val_start_utc: datetime,
    val_end_utc: datetime,
) -> Callable[[optuna.Study, optuna.trial.FrozenTrial], None]:
    """Return an Optuna callback that writes each completed trial to ClickHouse."""

    def callback(study: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
        duration = None
        if trial.datetime_start and trial.datetime_complete:
            duration = (trial.datetime_complete - trial.datetime_start).total_seconds()
        client.insert_hyperparam_trial(
            study_name=study_name,
            trial_number=trial.number,
            created_utc=datetime.now(timezone.utc),
            area=area,
            model_type=model_type,
            config_name=config_name,
            state=trial.state.name,
            value=trial.value,
            params_json=json.dumps(trial.params, sort_keys=True),
            val_start_utc=val_start_utc,
            val_end_utc=val_end_utc,
            duration_seconds=duration,
        )

    return callback
