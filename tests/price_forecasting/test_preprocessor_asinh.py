import numpy as np
import pandas as pd

from price_forecasting.configs import ExperimentConfig
from price_forecasting.data.preprocessor import DataPreprocessor


def _make_df(n_days: int = 30) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    idx = pd.date_range("2025-01-01", periods=n_days * 24, freq="h")
    return pd.DataFrame({"price": rng.normal(50.0, 20.0, size=len(idx))}, index=idx)


class TestPreprocessorTargetScaler:
    def test_preprocessor_uses_asinh_when_configured(self):
        config = ExperimentConfig(
            experiment_name="t", area="DK1", results_dir="r",
            model_type="lear", target_scaler="asinh",
        )
        pre = DataPreprocessor(config)
        df = _make_df()
        targets_train = np.asarray(
            df["price"].values.reshape(-1, 24)[:20], dtype=float
        )
        targets_train_scaled = pre.target_scaler.fit_transform(targets_train)
        # asinh on price ~ N(50, 20) should compress range substantially
        assert abs(targets_train_scaled).max() < 10
        np.testing.assert_allclose(
            pre.target_scaler.inverse_transform(targets_train_scaled),
            targets_train,
            rtol=1e-10,
        )

    def test_preprocessor_defaults_to_standard_scaler(self):
        from sklearn.preprocessing import StandardScaler
        config = ExperimentConfig(
            experiment_name="t", area="DK1", results_dir="r", model_type="lear",
        )
        pre = DataPreprocessor(config)
        assert isinstance(pre.target_scaler, StandardScaler)

    def test_preprocessor_rejects_unknown_scaler(self):
        import pytest
        config = ExperimentConfig(
            experiment_name="t", area="DK1", results_dir="r",
            model_type="lear", target_scaler="zscore",
        )
        with pytest.raises(ValueError, match="Unknown target_scaler"):
            DataPreprocessor(config)
