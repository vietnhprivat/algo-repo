import numpy as np
import optuna
import pandas as pd

from price_forecasting.configs import ExperimentConfig
from price_forecasting.tuning.dnn_search import build_dnn_search_space
from price_forecasting.tuning.objective import dnn_validation_objective


class TestDnnValidationObjective:
    def test_returns_finite_mae(self, monkeypatch):
        rng = np.random.default_rng(0)
        idx = pd.date_range("2024-01-01", periods=60 * 24, freq="h")
        df = pd.DataFrame({"price": rng.normal(50.0, 5.0, size=len(idx))}, index=idx)

        config = ExperimentConfig(
            experiment_name="t", area="DK1", results_dir="r", model_type="dnn",
            val_start_date="2024-02-15", val_end_date="2024-02-22",
            test_start_date="2024-02-23", test_end_date="2024-02-29",
            calibration_windows=[14], refit_interval_days=1,
            target_scaler="asinh",
        )

        from price_forecasting.data import clickhouse_loader
        monkeypatch.setattr(clickhouse_loader, "load_dataset", lambda _: df)

        study = optuna.create_study(direction="minimize")
        trial = study.ask()
        value = dnn_validation_objective(trial, config, build_dnn_search_space)
        assert np.isfinite(value)
        assert value >= 0

    def test_returns_inf_when_val_window_empty(self, monkeypatch):
        rng = np.random.default_rng(0)
        idx = pd.date_range("2024-01-01", periods=14 * 24, freq="h")
        df = pd.DataFrame({"price": rng.normal(50.0, 5.0, size=len(idx))}, index=idx)

        config = ExperimentConfig(
            experiment_name="t", area="DK1", results_dir="r", model_type="dnn",
            val_start_date="2025-01-01", val_end_date="2025-01-07",
            test_start_date="2025-02-01", test_end_date="2025-02-07",
            calibration_windows=[7], refit_interval_days=1,
        )

        from price_forecasting.data import clickhouse_loader
        monkeypatch.setattr(clickhouse_loader, "load_dataset", lambda _: df)

        study = optuna.create_study(direction="minimize")
        trial = study.ask()
        value = dnn_validation_objective(trial, config, build_dnn_search_space)
        assert value == float("inf")
