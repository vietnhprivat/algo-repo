"""Smoke test: prove LEAR still fits and predicts end-to-end on synthetic data."""

import numpy as np

from price_forecasting.models.lear import LearModel

from tests.price_forecasting.conftest import make_synthetic_features_and_targets


class TestLearSmoke:
    def test_lear_hourly_fit_and_predict(self) -> None:
        features, targets = make_synthetic_features_and_targets(
            start_date="2019-01-01",
            end_date="2019-03-01",
            n_features=10,
            n_periods=24,
        )
        model = LearModel(alpha=0.01, maximum_iterations=500)
        model.fit(features.to_numpy(), targets.to_numpy())

        prediction = model.predict_day(features.iloc[[0]].to_numpy())

        assert prediction.shape == (24,)
        assert np.isfinite(prediction).all()
        assert len(model.hourly_models) == 24

    def test_lear_quarter_hourly_fit_and_predict(self) -> None:
        features, targets = make_synthetic_features_and_targets(
            start_date="2019-01-01",
            end_date="2019-03-01",
            n_features=10,
            n_periods=96,
        )
        model = LearModel(alpha=0.01, maximum_iterations=500)
        model.fit(features.to_numpy(), targets.to_numpy())

        prediction = model.predict_day(features.iloc[[0]].to_numpy())

        assert prediction.shape == (96,)
        assert np.isfinite(prediction).all()
        assert len(model.hourly_models) == 96
