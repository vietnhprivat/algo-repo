import pytest

from scripts.report.reproduce_run import max_abs_diff


def test_max_abs_diff_identical():
    assert max_abs_diff([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == 0.0


def test_max_abs_diff_picks_largest_gap():
    assert max_abs_diff([1.0, 2.0, 3.0], [1.0, 2.0, 3.5]) == pytest.approx(0.5)


def test_max_abs_diff_shape_mismatch_raises():
    with pytest.raises(ValueError):
        max_abs_diff([1.0, 2.0], [1.0, 2.0, 3.0])
