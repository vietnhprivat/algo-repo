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

_PROD_PROJECT = "algo-prod"


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
        run = self._wandb.init(
            project=self._settings.default_project,
            entity=self._settings.entity,
            id=run_id,
            job_type="predict",
            tags=list(tags),
            config=dict(config),
        )
        try:
            for step, row in enumerate(prediction):
                run.log(dict(row), step=step)
        finally:
            run.finish()

    def log_prod_reconciled(
        self,
        *,
        area: str,
        config_name: str,
        target_date: str,
        metrics: Mapping[str, float],
        model_artifact_id: str | None = None,
    ) -> None:
        if not self._enabled:
            return None
        key = (area, config_name)
        run = self._prod_runs.get(key)
        if run is None:
            run = self._wandb.init(
                project=_PROD_PROJECT,
                entity=self._settings.entity,
                id=f"prod-{area.lower()}-{config_name}",
                resume="allow",
                job_type="prod-reconciled",
                tags=[area, config_name],
                config={"area": area, "config_name": config_name},
            )
            self._prod_runs[key] = run
        payload: dict[str, Any] = dict(metrics)
        payload["target_date"] = target_date
        if model_artifact_id is not None:
            payload["model_artifact_id"] = model_artifact_id
        run.log(payload)

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
        artifact = self._wandb.Artifact(
            name=artifact_id,
            type=artifact_type,
            metadata=dict(metadata),
        )
        artifact.add_file(local_path)
        run.log_artifact(artifact)

    def log_predict_run_with_artifact(
        self,
        *,
        run_id: str,
        config: Mapping[str, Any],
        prediction: Iterable[Mapping[str, Any]],
        tags: Iterable[str],
        artifact_id: str | None = None,
        artifact_blob_b64: str | None = None,
    ) -> None:
        if not self._enabled:
            return None
        from observability_wandb.artifacts import log_model_blob

        run = self._wandb.init(
            project=self._settings.default_project,
            entity=self._settings.entity,
            id=run_id,
            job_type="predict",
            tags=list(tags),
            config=dict(config),
        )
        try:
            for step, row in enumerate(prediction):
                run.log(dict(row), step=step)
            if artifact_id and artifact_blob_b64:
                log_model_blob(
                    tracker=self,
                    run=run,
                    artifact_id=artifact_id,
                    blob_b64=artifact_blob_b64,
                    metadata={
                        "area": config.get("area"),
                        "run_id": run_id,
                    },
                )
        finally:
            run.finish()

    def log_drift_event(
        self,
        *,
        area: str,
        curve_name: str,
        target_date: str,
        drift_score: float,
        drift_threshold: float,
        stat_test: str,
        drift_detected: bool,
    ) -> None:
        if not self._enabled:
            return None
        key = ("__drift__", area)
        run = self._prod_runs.get(key)
        if run is None:
            run = self._wandb.init(
                project=_PROD_PROJECT,
                entity=self._settings.entity,
                id=f"prod-drift-{area.lower()}",
                resume="allow",
                job_type="prod-drift",
                tags=[area, "drift"],
                config={"area": area},
            )
            self._prod_runs[key] = run
        run.log(
            {
                "target_date": target_date,
                "curve_name": curve_name,
                "drift_score": drift_score,
                "drift_threshold": drift_threshold,
                "stat_test": stat_test,
                "drift_detected": int(drift_detected),
            }
        )
