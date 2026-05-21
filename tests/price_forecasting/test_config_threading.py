"""Verify ExperimentConfig is attached to constructed models for WandbLogger."""

from __future__ import annotations

from price_forecasting.backtesting.runner import BacktestRunner, BaseRunner
from price_forecasting.configs.experiment import ExperimentConfig
from price_forecasting.live_runner import LiveRunner


def _make_cfg() -> ExperimentConfig:
    return ExperimentConfig(
        experiment_name="x",
        results_dir="results",
        area="DK1",
        model_type="lear",
        wandb_project="algo-research",
    )


class TestBacktestRunnerAttachesConfig:
    """The model factory produced by BaseRunner._get_model_factory must attach
    `_config` so that LightningModel.fit() can pick it up via build_lightning_logger."""

    def test_factory_attaches_config(self) -> None:
        cfg = _make_cfg()
        runner = BaseRunner(cfg)
        factory = runner._get_model_factory()
        model = factory()
        assert hasattr(model, "_config"), "model must have _config after factory call"
        assert model._config is cfg

    def test_backtest_runner_factory_attaches_config(self) -> None:
        cfg = _make_cfg()
        runner = BacktestRunner(cfg)
        factory = runner._get_model_factory()
        model = factory()
        assert hasattr(model, "_config"), "model must have _config after factory call"
        assert model._config is cfg


class TestLiveRunnerAttachesConfig:
    """Both factory methods on LiveRunner must attach `_config` to the model."""

    def test_get_model_factory_attaches_config(self) -> None:
        cfg = _make_cfg()
        runner = LiveRunner(cfg)
        factory = runner._get_model_factory()
        model = factory()
        assert hasattr(model, "_config"), "model must have _config after factory call"
        assert model._config is cfg

    def test_get_model_factory_with_seed_attaches_config(self) -> None:
        # The seeded factory is only exercised for DNN ensembles, so use dnn model_type.
        cfg = ExperimentConfig(
            experiment_name="x",
            results_dir="results",
            area="DK1",
            model_type="dnn",
            wandb_project="algo-research",
        )
        runner = LiveRunner(cfg)
        factory = runner._get_model_factory_with_seed(seed=7)
        model = factory()
        assert hasattr(model, "_config"), "model must have _config after seeded factory call"
        assert model._config is cfg
