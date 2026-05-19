import numpy as np
import pytest

from price_forecasting.data.asinh_scaler import AsinhScaler


def test_asinh_scaler_roundtrip_preserves_values():
    rng = np.random.default_rng(0)
    prices = rng.normal(50.0, 10.0, size=(500, 24))
    scaler = AsinhScaler()
    transformed = scaler.fit_transform(prices)
    restored = scaler.inverse_transform(transformed)
    np.testing.assert_allclose(restored, prices, rtol=1e-10, atol=1e-10)


def test_asinh_scaler_handles_zeros_and_negatives():
    prices = np.array([[-10.0, 0.0, 5.0, 100.0]])
    scaler = AsinhScaler()
    transformed = scaler.fit_transform(prices)
    assert np.all(np.isfinite(transformed))
    np.testing.assert_allclose(scaler.inverse_transform(transformed), prices, rtol=1e-10)


def test_asinh_scaler_centers_on_median_not_mean():
    prices = np.array([[1.0, 2.0, 3.0, 4.0, 100.0]]).T
    scaler = AsinhScaler()
    transformed = scaler.fit_transform(prices)
    # median (3.0) maps closer to 0 than mean (22.0) would
    assert abs(transformed[2, 0]) < abs(transformed[1, 0]) + 1e-6
