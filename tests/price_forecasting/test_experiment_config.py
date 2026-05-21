"""ExperimentConfig wandb fields."""

from __future__ import annotations

from price_forecasting.configs.experiment import ExperimentConfig


def test_experiment_config_has_wandb_defaults() -> None:
    cfg = ExperimentConfig(
        experiment_name="x", results_dir="results", area="DK1"
    )
    assert cfg.wandb_project is None
    assert cfg.wandb_tags == []


def test_experiment_config_accepts_wandb_values() -> None:
    cfg = ExperimentConfig(
        experiment_name="x",
        results_dir="results",
        area="DK1",
        wandb_project="algo-research",
        wandb_tags=["DK1", "lear"],
    )
    assert cfg.wandb_project == "algo-research"
    assert cfg.wandb_tags == ["DK1", "lear"]
