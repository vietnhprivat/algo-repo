"""LightningModel passes a WandbLogger to Trainer when enabled."""

from __future__ import annotations

import pytest

from price_forecasting.configs.experiment import ExperimentConfig


@pytest.fixture
def enabled_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WANDB_API_KEY", "k")
    monkeypatch.setenv("WANDB_ENTITY", "e")
    monkeypatch.setenv("WANDB_MODE", "online")


def test_trainer_logger_is_wandb_when_config_sets_project(
    enabled_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from observability_wandb.lightning_logger import build_lightning_logger
    from lightning.pytorch.loggers import WandbLogger

    cfg = ExperimentConfig(
        experiment_name="x",
        results_dir="results",
        area="DK1",
        wandb_project="algo-research",
        wandb_tags=["DK1", "dnn"],
    )
    logger = build_lightning_logger(cfg)
    assert isinstance(logger, WandbLogger)


def test_trainer_logger_is_none_when_config_has_no_project(
    enabled_env: None,
) -> None:
    from observability_wandb.lightning_logger import build_lightning_logger

    cfg = ExperimentConfig(experiment_name="x", results_dir="results", area="DK1")
    assert build_lightning_logger(cfg) is None
