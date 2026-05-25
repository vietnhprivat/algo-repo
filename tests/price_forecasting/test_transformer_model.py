"""Tests for the Transformer EPF model (Llorente & Portela, 2025)."""

import numpy as np
import pytest
import torch


class TestTransformerNetwork:
    def test_forward_returns_batch_by_n_periods(self):
        from price_forecasting.models.transformer import TransformerNetwork

        torch.manual_seed(0)
        seq_length_days = 7
        n_exog = 2
        n_periods = 24
        embedding_dim = 32
        net = TransformerNetwork(
            seq_length_days=seq_length_days,
            n_exog=n_exog,
            n_periods=n_periods,
            embedding_dim=embedding_dim,
            n_heads=4,
            n_encoder_layers=2,
            ff_dim=64,
            dropout=0.1,
            mlp_hidden=32,
        )
        batch = 5
        n_features = seq_length_days * n_periods + n_exog * n_periods
        x = torch.randn(batch, n_features)
        y = net(x)
        assert y.shape == (batch, n_periods)
        assert torch.isfinite(y).all()

    def test_both_flows_contribute_to_output(self):
        """Perturbing only the past-price block or only the exog block must
        change the output — both flows must carry signal. Guards against a
        bug where one flow is silently dropped."""
        from price_forecasting.models.transformer import TransformerNetwork

        torch.manual_seed(0)
        net = TransformerNetwork(
            seq_length_days=4, n_exog=1, n_periods=24,
            embedding_dim=16, n_heads=2, n_encoder_layers=1,
            ff_dim=32, dropout=0.0, mlp_hidden=16,
        )
        net.eval()
        n_features = 4 * 24 + 1 * 24
        x = torch.zeros(1, n_features)
        y0 = net(x).detach().clone()

        x_prices = x.clone()
        x_prices[0, : 4 * 24] = torch.randn(4 * 24)
        y_prices = net(x_prices).detach()
        assert not torch.allclose(y_prices, y0)

        x_exog = x.clone()
        x_exog[0, 4 * 24 :] = torch.randn(1 * 24)
        y_exog = net(x_exog).detach()
        assert not torch.allclose(y_exog, y0)

    def test_rejects_embedding_dim_not_divisible_by_n_heads(self):
        from price_forecasting.models.transformer import TransformerNetwork

        with pytest.raises(ValueError, match="divisible"):
            TransformerNetwork(
                seq_length_days=4, n_exog=1, n_periods=24,
                embedding_dim=15,   # 15 % 4 != 0
                n_heads=4,
                n_encoder_layers=1, ff_dim=32, dropout=0.0, mlp_hidden=16,
            )


class TestTransformerModel:
    @staticmethod
    def _make_features_and_targets(
        n_samples: int, seq_length_days: int, n_exog: int, n_periods: int = 24
    ):
        rng = np.random.default_rng(0)
        n_features = seq_length_days * n_periods + n_exog * n_periods
        features = rng.normal(size=(n_samples, n_features)).astype(np.float32)
        targets = rng.normal(size=(n_samples, n_periods)).astype(np.float32)
        return features, targets

    def test_fit_then_predict_day_returns_n_periods_vector(self):
        from price_forecasting.models.transformer import TransformerModel

        seq_length_days = 4
        n_exog = 2
        n_periods = 24

        model = TransformerModel(
            seq_length_days=seq_length_days,
            n_exog=n_exog,
            embedding_dim=16,
            n_heads=2,
            n_encoder_layers=1,
            ff_dim=32,
            dropout=0.0,
            mlp_hidden=16,
            epochs=2,
            batch_size=4,
            validation_fraction=0.25,
            early_stopping_patience=100,
            random_seed=0,
        )

        features, targets = self._make_features_and_targets(
            n_samples=32, seq_length_days=seq_length_days, n_exog=n_exog,
            n_periods=n_periods,
        )
        model.fit(features, targets)

        single_day = features[0]
        prediction = model.predict_day(single_day)
        assert prediction.shape == (n_periods,)
        assert np.isfinite(prediction).all()

    def test_rejects_wrong_feature_count(self):
        from price_forecasting.models.transformer import TransformerModel

        model = TransformerModel(
            seq_length_days=4, n_exog=2,
            embedding_dim=16, n_heads=2, n_encoder_layers=1,
            ff_dim=32, dropout=0.0, mlp_hidden=16,
            epochs=1, batch_size=4, validation_fraction=0.25,
        )
        bad_features = np.zeros((8, 4 * 24 + 2 * 24 + 1), dtype=np.float32)
        bad_targets = np.zeros((8, 24), dtype=np.float32)
        with pytest.raises(ValueError, match="TransformerModel expects"):
            model.fit(bad_features, bad_targets)


class TestTransformerSmoke:
    """End-to-end smoke test: feature transformers -> DataPreprocessor -> BacktestEngine.

    Verifies that the wide-feature-vector layout contract is honoured across
    the entire pipeline and that BacktestEngine can drive TransformerModel
    through fit + predict for a small test window.

    Dataset: ~200 days of hourly synthetic data (large enough that the
    calibration window of 100 days fits comfortably before the 3-day test
    window).  Model is deliberately tiny (embedding_dim=16, n_heads=2,
    n_encoder_layers=1, ff_dim=32, epochs=2) to complete in a few seconds.
    """

    SEQ_LEN = 7
    N_EXOG_COLS = ["load_forecast", "gen_forecast"]
    N_TEST_DAYS = 3
    CALIBRATION_WINDOW = 100  # days of training data per window

    def test_engine_drives_transformer_end_to_end(self) -> None:
        import pandas as pd

        from price_forecasting.backtesting.engine import BacktestEngine
        from price_forecasting.configs import ExperimentConfig
        from price_forecasting.data.preprocessor import DataPreprocessor
        from price_forecasting.data.transformers import default_transformers_for_transformer
        from price_forecasting.models.transformer import TransformerModel
        from tests.price_forecasting.conftest import make_hourly_dataframe

        # ~200 days of hourly data (enough room for calibration_window=100 + 3 test days)
        hourly_df = make_hourly_dataframe(
            start_date="2023-01-01",
            end_date="2023-07-20",
            exogenous_columns=self.N_EXOG_COLS,
            seed=7,
        )

        seq_len = self.SEQ_LEN
        n_exog = len(self.N_EXOG_COLS)

        config = ExperimentConfig(
            experiment_name="transformer_smoke",
            area="DK1",
            results_dir="/tmp/transformer_smoke",
            model_type="transformer",
            calibration_windows=[self.CALIBRATION_WINDOW],
            refit_interval_days=self.N_TEST_DAYS,  # refit once for all 3 test days
            feature_transformers=default_transformers_for_transformer(
                exogenous_columns=self.N_EXOG_COLS,
                sequence_length_days=seq_len,
            ),
            model_params={
                "seq_length_days": seq_len,
                "n_exog": n_exog,
                "embedding_dim": 16,
                "n_heads": 2,
                "n_encoder_layers": 1,
                "ff_dim": 32,
                "mlp_hidden": 16,
                "dropout": 0.0,
                "epochs": 2,
                "batch_size": 16,
                "validation_fraction": 0.2,
                "early_stopping_patience": 100,
                "random_seed": 0,
            },
        )

        preprocessor = DataPreprocessor(config)
        features, targets = preprocessor.build_dataset(dataframe=hourly_df)

        # Sanity-check the feature width contract:
        #   seq_length_days * n_periods  +  n_exog * n_periods
        n_periods = targets.shape[1]
        expected_n_features = seq_len * n_periods + n_exog * n_periods
        assert features.shape[1] == expected_n_features, (
            f"Feature layout mismatch: got {features.shape[1]}, "
            f"expected {expected_n_features}"
        )

        # Last 3 valid days as test dates
        test_dates = pd.DatetimeIndex(targets.index[-self.N_TEST_DAYS :])

        engine = BacktestEngine(config)
        model_factory = lambda: TransformerModel(**config.model_params)  # noqa: E731

        forecast_df, actuals_df = engine.run(
            model_factory=model_factory,
            features=features,
            targets=targets,
            test_dates=test_dates,
        )

        assert len(forecast_df) == self.N_TEST_DAYS, (
            f"Expected {self.N_TEST_DAYS} forecast rows, got {len(forecast_df)}"
        )
        assert forecast_df.shape[1] == n_periods, (
            f"Expected {n_periods} forecast columns (hours), got {forecast_df.shape[1]}"
        )
        assert np.isfinite(forecast_df.values).all(), (
            "Forecast contains non-finite values (NaN or Inf)"
        )
