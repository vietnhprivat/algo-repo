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


class TestBaseModelInterface:
    def test_stub_model_implements_interface(self):
        model = StubModel()
        assert isinstance(model, BaseModel)

    def test_stub_fit_and_predict(self):
        model = StubModel(prediction_value=99.0)
        features = np.random.randn(30, 10)
        targets = np.random.randn(30, 24)

        model.fit(features, targets)
        assert model.fit_called

        pred = model.predict_day(np.random.randn(1, 10))
        assert pred.shape == (24,)
        assert np.all(pred == 99.0)


class TestLearModelInterface:
    """Test LEAR model's interface without meaningful training."""

    def test_predict_before_fit_raises(self):
        model = LearModel(alpha=0.01)
        features = np.random.randn(1, 10)
        with pytest.raises(ValueError, match="must be fit"):
            model.predict_day(features)

    def test_fit_creates_24_hourly_models(self):
        model = LearModel(alpha=1.0, maximum_iterations=10)
        # Minimal data just to exercise fit path
        features = np.random.randn(50, 5)
        targets = np.random.randn(50, 24)
        model.fit(features, targets)
        assert len(model.hourly_models) == 24

    def test_predict_returns_24_values(self):
        model = LearModel(alpha=1.0, maximum_iterations=10)
        features = np.random.randn(50, 5)
        targets = np.random.randn(50, 24)
        model.fit(features, targets)

        pred = model.predict_day(np.random.randn(1, 5))
        assert pred.shape == (24,)
