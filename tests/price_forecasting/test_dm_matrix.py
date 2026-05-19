import numpy as np

from price_forecasting.evaluation.summary import build_dm_matrix


class TestDmMatrix:
    def test_shape_and_diagonal(self):
        rng = np.random.default_rng(0)
        errors = {
            "model_a": rng.normal(0.0, 3.0, size=(300, 24)),
            "model_b": rng.normal(0.0, 1.0, size=(300, 24)),
            "model_c": rng.normal(0.0, 2.0, size=(300, 24)),
        }
        matrix = build_dm_matrix(errors, norm=1)
        assert matrix.shape == (3, 3)
        assert list(matrix.index) == ["model_a", "model_b", "model_c"]
        assert list(matrix.columns) == ["model_a", "model_b", "model_c"]
        for name in matrix.index:
            assert np.isnan(matrix.loc[name, name])

    def test_better_model_in_column_yields_low_p(self):
        rng = np.random.default_rng(0)
        errors = {
            "weak": rng.normal(0.0, 5.0, size=(300, 24)),
            "strong": rng.normal(0.0, 1.0, size=(300, 24)),
        }
        matrix = build_dm_matrix(errors, norm=1)
        # H1: column model is better — strong > weak in column position
        assert matrix.loc["weak", "strong"] < 0.05

    def test_rejects_inconsistent_shapes(self):
        import pytest
        errors = {
            "a": np.zeros((100, 24)),
            "b": np.zeros((100, 25)),
        }
        with pytest.raises(ValueError, match="identical shape"):
            build_dm_matrix(errors, norm=1)
