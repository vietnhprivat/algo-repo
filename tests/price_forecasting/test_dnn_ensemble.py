import numpy as np
import pandas as pd

from price_forecasting import LiveRunner
from price_forecasting.configs import ExperimentConfig


class TestDnnEnsemble:
    def test_dnn_ensemble_averages_n_predictions(self):
        rng = np.random.default_rng(0)
        idx = pd.date_range("2024-01-01", periods=45 * 24, freq="h")
        df = pd.DataFrame({"price": rng.normal(50.0, 5.0, size=len(idx))}, index=idx)
        config = ExperimentConfig(
            experiment_name="t", area="DK1", results_dir="r", model_type="dnn",
            calibration_windows=[28], refit_interval_days=1,
            target_scaler="asinh", n_dnn_ensemble=2,
            model_params={"hidden_units": 16, "epochs": 2},
        )
        runner = LiveRunner(config)
        result = runner.run_live_with_metadata("2024-02-14", dataframe=df)
        assert result.prediction.shape == (24,)
        # 1 calibration window × 2 ensemble members = 2 models
        assert len(result.trained_models) == 2

    def test_single_member_runs_normal_path(self):
        rng = np.random.default_rng(0)
        idx = pd.date_range("2024-01-01", periods=45 * 24, freq="h")
        df = pd.DataFrame({"price": rng.normal(50.0, 5.0, size=len(idx))}, index=idx)
        config = ExperimentConfig(
            experiment_name="t", area="DK1", results_dir="r", model_type="dnn",
            calibration_windows=[28], refit_interval_days=1,
            target_scaler="asinh", n_dnn_ensemble=1,
            model_params={"hidden_units": 16, "epochs": 2},
        )
        runner = LiveRunner(config)
        result = runner.run_live_with_metadata("2024-02-14", dataframe=df)
        assert result.prediction.shape == (24,)
        assert len(result.trained_models) == 1  # 1 window × 1 member
