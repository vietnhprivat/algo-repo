"""Optuna study callback that mirrors each trial as a W&B run."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from observability_wandb.client_factory import is_enabled, load_settings


def build_wandb_sweep_callback(
    *,
    wandb_module: Any | None = None,
    study_name: str,
    area: str,
    model_type: str,
    config_name: str,
) -> Callable[[Any, Any], None]:
    enabled = is_enabled()

    # When disabled and no injected module, return a no-op without ever
    # importing wandb — preserves the deferred-import guarantee.
    if not enabled and wandb_module is None:
        def _noop(study: Any, trial: Any) -> None:
            return None
        return _noop

    if wandb_module is None:
        import wandb as wandb_module  # type: ignore[no-redef]

    settings = load_settings()

    def _callback(study: Any, trial: Any) -> None:
        if not enabled:
            return None
        run = wandb_module.init(
            project=settings.default_project,
            entity=settings.entity,
            group=study_name,
            job_type="sweep-trial",
            tags=[area, model_type, config_name],
            config={
                **dict(trial.params),
                "trial_number": trial.number,
                "area": area,
                "model_type": model_type,
                "config_name": config_name,
            },
        )
        try:
            run.summary["value"] = float(trial.value)
            run.summary["state"] = str(trial.state)
        finally:
            run.finish()

    return _callback
