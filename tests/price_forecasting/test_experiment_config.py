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


class TestExogenousAggregates:
    def test_defaults_empty(self):
        config = ExperimentConfig(
            experiment_name="x", results_dir="r", area="DK1"
        )
        assert config.exogenous_aggregates == {}
        assert config.exogenous_columns == []

    def test_exogenous_columns_combines_types_and_aggregate_names(self):
        config = ExperimentConfig(
            experiment_name="x",
            results_dir="r",
            area="DK1",
            exogenous_curve_types=["TotalLoad"],
            exogenous_aggregates={"Wind": ["WindOnshore", "WindOffshore"]},
        )
        assert config.exogenous_columns == ["TotalLoad", "Wind"]
