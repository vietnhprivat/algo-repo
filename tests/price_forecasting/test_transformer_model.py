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
