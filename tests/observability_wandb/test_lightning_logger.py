"""build_lightning_logger factory."""

from __future__ import annotations

import pytest

from observability_wandb.lightning_logger import build_lightning_logger


class _Cfg:
    wandb_project: str | None
    wandb_tags: list[str]
    experiment_name: str

    def __init__(
        self,
        wandb_project: str | None,
        wandb_tags: list[str] | None = None,
        experiment_name: str = "x",
    ) -> None:
        self.wandb_project = wandb_project
        self.wandb_tags = wandb_tags or []
        self.experiment_name = experiment_name


def test_returns_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WANDB_MODE", "disabled")
    assert build_lightning_logger(_Cfg(wandb_project="algo-research")) is None


def test_returns_none_when_config_has_no_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WANDB_API_KEY", "k")
    monkeypatch.setenv("WANDB_ENTITY", "e")
    monkeypatch.setenv("WANDB_MODE", "online")
    assert build_lightning_logger(_Cfg(wandb_project=None)) is None


def test_returns_wandb_logger_when_enabled_and_project_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WANDB_API_KEY", "k")
    monkeypatch.setenv("WANDB_ENTITY", "e")
    monkeypatch.setenv("WANDB_MODE", "online")

    from lightning.pytorch.loggers import WandbLogger

    logger = build_lightning_logger(
        _Cfg(wandb_project="algo-research", wandb_tags=["DK1", "dnn"])
    )
    assert isinstance(logger, WandbLogger)
