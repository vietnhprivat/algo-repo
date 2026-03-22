"""Shared fixtures and helpers for price forecasting integration tests."""

import numpy as np
import pandas as pd

from price_forecasting.configs.experiment import ExperimentConfig
from price_forecasting.models.base import BaseModel


class StubModel(BaseModel):
    """A deterministic model that returns fixed predictions without real training.

    fit() is a no-op. predict_day() returns a fixed array.
    This lets us test the engine/runner pipeline without training overhead.
    """

    def __init__(self, prediction_value: float = 42.0):
        self.prediction_value = prediction_value
        self.fit_called = False
        self.fit_count = 0

    def fit(self, features: np.ndarray, targets: np.ndarray) -> None:
        self.fit_called = True
        self.fit_count += 1

    def predict_day(self, features: np.ndarray) -> np.ndarray:
        return np.full(24, self.prediction_value)


def make_test_config(
    tmp_path,
    windows: list[int] | None = None,
    train_ratio: float = 0.5,
    validation_ratio: float = 0.0,
    test_ratio: float = 0.5,
    refit_interval_days: int = 1,
) -> ExperimentConfig:
    """Build an ExperimentConfig pointing at a temporary results directory."""
    return ExperimentConfig(
        experiment_name="test_experiment",
        results_dir=str(tmp_path / "results"),
        area="DE",
        target_column="price",
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        test_ratio=test_ratio,
        calibration_windows=windows or [7],
        refit_interval_days=refit_interval_days,
        model_type="LEAR",
        exogenous_curve_types=[],
        model_params={},
    )


def make_synthetic_features_and_targets(
    start_date: str = "2019-01-01",
    end_date: str = "2019-02-28",
    n_features: int = 10,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Generate synthetic daily features and targets (24 hours).

    Returns DatetimeIndex-based DataFrames suitable for BacktestEngine.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start=start_date, end=end_date, freq="D")

    features = pd.DataFrame(
        rng.standard_normal((len(dates), n_features)),
        index=dates,
        columns=[f"feat_{i}" for i in range(n_features)],
    )
    targets = pd.DataFrame(
        rng.standard_normal((len(dates), 24)) * 20 + 50,
        index=dates,
        columns=[f"h{i}" for i in range(24)],
    )
    return features, targets
