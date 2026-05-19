import numpy as np
import pytest

from price_forecasting.evaluation.statistical_tests import (
    diebold_mariano,
    DMResult,
)


class TestDieboldMariano:
    def test_low_p_value_when_b_is_clearly_better(self):
        rng = np.random.default_rng(0)
        n = 500
        errors_a = rng.normal(0.0, 5.0, size=n)
        errors_b = rng.normal(0.0, 1.0, size=n)  # B much more accurate
        result = diebold_mariano(errors_a, errors_b, loss="l1", alternative="b_better")
        assert isinstance(result, DMResult)
        assert result.p_value < 0.01
        assert result.statistic > 0  # mean loss diff A - B > 0

    def test_high_p_value_when_models_equivalent(self):
        rng = np.random.default_rng(0)
        errors_a = rng.normal(0.0, 2.0, size=1000)
        errors_b = rng.normal(0.0, 2.0, size=1000)
        result = diebold_mariano(errors_a, errors_b, loss="l1", alternative="b_better")
        assert result.p_value > 0.1

    def test_l2_loss_supported(self):
        rng = np.random.default_rng(0)
        errors_a = rng.normal(0.0, 3.0, size=400)
        errors_b = rng.normal(0.0, 1.0, size=400)
        result = diebold_mariano(errors_a, errors_b, loss="l2", alternative="b_better")
        assert result.p_value < 0.01

    def test_shape_mismatch_raises(self):
        with pytest.raises(ValueError, match="identical shape"):
            diebold_mariano(np.zeros(10), np.zeros(11), loss="l1")

    def test_unknown_loss_raises(self):
        with pytest.raises(ValueError, match="Unknown loss"):
            diebold_mariano(np.zeros(10), np.zeros(10), loss="cube")

    def test_unknown_alternative_raises(self):
        with pytest.raises(ValueError, match="Unknown alternative"):
            diebold_mariano(np.zeros(10), np.zeros(10), loss="l1", alternative="weirder")
