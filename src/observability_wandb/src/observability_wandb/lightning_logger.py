"""Factory for the Lightning WandbLogger.

Returns ``None`` when W&B is disabled or the config has no
``wandb_project``. Callers (LightningModel) accept ``None`` as "no logger".
"""

from __future__ import annotations

from typing import Any, Protocol

from observability_wandb.client_factory import is_enabled, load_settings


class _CfgLike(Protocol):
    wandb_project: str | None
    wandb_tags: list[str]
    experiment_name: str


def build_lightning_logger(config: _CfgLike | None) -> Any | None:
    if not is_enabled():
        return None
    if config is None or not config.wandb_project:
        return None

    from lightning.pytorch.loggers import WandbLogger

    settings = load_settings()
    return WandbLogger(
        project=config.wandb_project,
        entity=settings.entity or None,
        name=config.experiment_name,
        tags=list(config.wandb_tags),
        job_type="train",
    )
