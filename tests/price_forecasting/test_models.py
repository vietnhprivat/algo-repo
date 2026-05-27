"""Integration tests for price forecasting models (no real training)."""

import pytest
import numpy as np

from price_forecasting.models import get_model, BaseModel
from price_forecasting.models.lear import LearModel
from price_forecasting.models.dnn import DNNModel
from tests.price_forecasting.conftest import StubModel


class TestModelRegistry:
    def test_get_lear_model(self):
        model = get_model("LEAR")
        assert isinstance(model, LearModel)

    def test_get_dnn_model(self):
        model = get_model("DNN")
        assert isinstance(model, DNNModel)

    def test_unknown_model_raises(self):
        with pytest.raises(ValueError, match="Unknown model"):
            get_model("NonExistent")

    def test_case_insensitive_lookup(self):
        assert isinstance(get_model("lear"), LearModel)
        assert isinstance(get_model("Lear"), LearModel)

    def test_model_params_forwarded(self):
        model = get_model("LEAR", alpha=0.5, maximum_iterations=100)
        assert isinstance(model, LearModel)
        assert model.alpha == 0.5
        assert model.maximum_iterations == 100

    def test_get_transformer_model(self):
        from price_forecasting.models.transformer import TransformerModel

        model = get_model(
            "transformer",
            seq_length_days=4,
            n_exog=1,
            embedding_dim=16,
            n_heads=2,
            n_encoder_layers=1,
            ff_dim=32,
            dropout=0.0,
            mlp_hidden=16,
        )
        assert isinstance(model, TransformerModel)


class TestBaseModelInterface:
    def test_stub_model_implements_interface(self):
        model = StubModel()
        assert isinstance(model, BaseModel)

    def test_stub_fit_and_predict(self):
        model = StubModel(prediction_value=99.0)
        n_periods = 24
        features = np.random.randn(30, 10)
        targets = np.random.randn(30, n_periods)

        model.fit(features, targets)
        assert model.fit_called

        pred = model.predict_day(np.random.randn(1, 10))
        assert pred.shape == (n_periods,)
        assert np.all(pred == 99.0)


class TestDNNModelInterface:
    """Test DNNModel interface — uses tiny epochs so tests run fast."""

    N_PERIODS = 24

    def _make_data(self, n_samples: int = 50, n_features: int = 10, n_periods: int = 24):
        rng = np.random.default_rng(0)
        return rng.standard_normal((n_samples, n_features)), rng.standard_normal((n_samples, n_periods))

    def test_predict_before_fit_raises(self):
        model = DNNModel()
        with pytest.raises(RuntimeError, match="must be fit"):
            model.predict_day(np.random.randn(1, 10))

    def test_fit_and_predict_shape(self):
        model = DNNModel(hidden_units=(32, 16), epochs=3)
        X, y = self._make_data()
        model.fit(X, y)
        pred = model.predict_day(X[:1])
        assert pred.shape == (self.N_PERIODS,)

    def test_resolution_aware_96_periods(self):
        n_periods = 96
        model = DNNModel(hidden_units=(32, 16), epochs=3)
        X, y = self._make_data(n_periods=n_periods)
        model.fit(X, y)
        pred = model.predict_day(X[:1])
        assert pred.shape == (n_periods,)

    def test_model_registry_params_forwarded(self):
        model = get_model("dnn", hidden_units=(64, 64), dropout=0.2)
        assert isinstance(model, DNNModel)
        assert model.hidden_units == (64, 64)
        assert model.dropout == 0.2

    def test_int_hidden_units_converted_to_tuple(self):
        model = DNNModel(hidden_units=128)
        assert model.hidden_units == (128, 128)

    @pytest.mark.parametrize("activation", ["relu", "tanh", "sigmoid", "elu", "softplus"])
    def test_all_search_space_activations_supported(self, activation):
        model = DNNModel(hidden_units=(8, 8), activation=activation, epochs=1)
        X, y = self._make_data(n_samples=20, n_features=6)
        model.fit(X, y)
        pred = model.predict_day(X[:1])
        assert pred.shape == (self.N_PERIODS,)

    def test_unknown_activation_raises(self):
        model = DNNModel(hidden_units=(8, 8), activation="not_a_real_activation", epochs=1)
        X, y = self._make_data(n_samples=20, n_features=6)
        with pytest.raises(ValueError, match="Unknown activation"):
            model.fit(X, y)


class TestLearModelInterface:
    """Test LEAR model's interface without meaningful training."""

    def test_predict_before_fit_raises(self):
        model = LearModel(alpha=0.01)
        features = np.random.randn(1, 10)
        with pytest.raises(ValueError, match="must be fit"):
            model.predict_day(features)

    def test_fit_creates_n_period_models(self):
        model = LearModel(alpha=1.0, maximum_iterations=10)
        n_periods = 24
        features = np.random.randn(50, 5)
        targets = np.random.randn(50, n_periods)
        model.fit(features, targets)
        assert len(model.hourly_models) == n_periods

    def test_predict_returns_correct_shape(self):
        model = LearModel(alpha=1.0, maximum_iterations=10)
        n_periods = 24
        features = np.random.randn(50, 5)
        targets = np.random.randn(50, n_periods)
        model.fit(features, targets)

        pred = model.predict_day(np.random.randn(1, 5))
        assert pred.shape == (n_periods,)
