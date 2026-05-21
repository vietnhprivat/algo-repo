"""WandbTracker — single owner of the W&B-side schema.

Every public method is a no-op when the tracker is disabled
(missing API key or ``WANDB_MODE=disabled``).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from typing import Any

from observability_wandb.client_factory import is_enabled, load_settings

LOGGER = logging.getLogger(__name__)


class WandbTracker:
    def __init__(self, *, wandb_module: Any | None = None) -> None:
        self._settings = load_settings()
        self._enabled = is_enabled()
        self._prod_runs: dict[tuple[str, str], Any] = {}
        if wandb_module is not None:
            self._wandb: Any = wandb_module
        elif self._enabled:
            import wandb as _wandb

            self._wandb = _wandb
        else:
            self._wandb = None

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def log_backtest_run(
        self,
        *,
        run_id: str,
        config: Mapping[str, Any],
        summary: Mapping[str, float],
        per_day: Iterable[Mapping[str, Any]],
        tags: Iterable[str],
    ) -> None:
        if not self._enabled:
            return None
        run = self._wandb.init(
            project=self._settings.default_project,
            entity=self._settings.entity,
            id=run_id,
            job_type="backtest",
            tags=list(tags),
            config=dict(config),
        )
        try:
            for step, row in enumerate(per_day):
                run.log(dict(row), step=step)
            for key, value in summary.items():
                run.summary[key] = value
        finally:
            run.finish()

    def log_predict_run(
        self,
        *,
        run_id: str,
        config: Mapping[str, Any],
        prediction: Iterable[Mapping[str, Any]],
        tags: Iterable[str],
    ) -> None:
        if not self._enabled:
            return None
        # Filled in by Task 5.
        raise NotImplementedError

    def log_prod_reconciled(
        self,
        *,
        area: str,
        config_name: str,
        target_date: str,
        metrics: Mapping[str, float],
    ) -> None:
        if not self._enabled:
            return None
        # Filled in by Task 6.
        raise NotImplementedError

    def log_artifact(
        self,
        *,
        run: Any,
        artifact_id: str,
        artifact_type: str,
        local_path: str,
        metadata: Mapping[str, Any],
    ) -> None:
        if not self._enabled:
            return None
        # Filled in by Task 7.
        raise NotImplementedError
