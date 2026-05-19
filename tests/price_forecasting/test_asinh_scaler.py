import numpy as np

from price_forecasting.data.asinh_scaler import AsinhScaler


class TestAsinhScaler:
    def test_asinh_scaler_roundtrip_preserves_values(self):
        rng = np.random.default_rng(0)
        prices = rng.normal(50.0, 10.0, size=(500, 24))
        scaler = AsinhScaler()
        transformed = scaler.fit_transform(prices)
        restored = scaler.inverse_transform(transformed)
        np.testing.assert_allclose(restored, prices, rtol=1e-10, atol=1e-10)

    def test_asinh_scaler_handles_zeros_and_negatives(self):
        prices = np.array([
            [-10.0, 0.0, 5.0, 100.0],
            [-5.0, 1.0, 3.0, 80.0],
            [0.0, -2.0, 4.0, 60.0],
        ])
        scaler = AsinhScaler()
        transformed = scaler.fit_transform(prices)
        assert np.all(np.isfinite(transformed))
        np.testing.assert_allclose(scaler.inverse_transform(transformed), prices, rtol=1e-10)

    def test_asinh_scaler_centers_on_median_not_mean(self):
        prices = np.array([[1.0, 2.0, 3.0, 4.0, 100.0]]).T
        scaler = AsinhScaler()
        transformed = scaler.fit_transform(prices)
        # median (3.0) maps to exactly 0 after centering
        assert abs(transformed[2, 0]) < 1e-10
