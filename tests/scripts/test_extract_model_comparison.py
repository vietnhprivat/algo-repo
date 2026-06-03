"""Tests for the pure table-building helpers of extract_model_comparison."""

import numpy as np
import pandas as pd

from scripts.report.extract_model_comparison import (
    NAIVE,
    build_gw_inputs,
    build_headline_table,
    common_index,
    errors_matrix,
    to_latex_booktabs,
)


def _wide(values, start="2026-01-01"):
    """Build a (n_days x n_periods) wide frame like the runner CSVs."""
    arr = np.asarray(values, dtype=float)
    index = pd.date_range(start, periods=arr.shape[0], freq="D")
    return pd.DataFrame(arr, index=index,
                        columns=[f"price_p{i}" for i in range(arr.shape[1])])


class TestCommonIndex:
    def test_intersection_of_unequal_indices(self) -> None:
        a = _wide(np.zeros((5, 2)))
        b = _wide(np.zeros((3, 2)))  # shorter
        idx = common_index([a, b])
        assert len(idx) == 3
        assert list(idx) == list(b.index)


class TestErrorsMatrix:
    def test_errors_are_actuals_minus_forecasts_aligned(self) -> None:
        actuals = _wide([[10.0, 20.0], [30.0, 40.0]])
        forecasts = _wide([[9.0, 22.0], [33.0, 39.0]])
        errors = errors_matrix(forecasts, actuals)
        assert errors.shape == (2, 2)
        np.testing.assert_allclose(errors, [[1.0, -2.0], [-3.0, 1.0]])

    def test_alignment_drops_unmatched_days(self) -> None:
        actuals = _wide(np.full((3, 2), 50.0))
        forecasts = _wide(np.full((2, 2), 49.0))  # one day fewer
        errors = errors_matrix(forecasts, actuals)
        assert errors.shape == (2, 2)


class TestBuildHeadlineTable:
    def test_one_row_per_model_plus_naive_with_metric_columns(self) -> None:
        actuals = _wide(np.full((14, 2), 50.0))
        runs = {
            "LEAR": _wide(np.full((14, 2), 49.0)),
            "DNN": _wide(np.full((14, 2), 48.0)),
        }
        table = build_headline_table(runs, actuals)
        assert list(table.index) == ["LEAR", "DNN", NAIVE]
        for col in ("MAE", "RMSE", "sMAPE", "rMAE"):
            assert col in table.columns
        # constant 1.0 absolute error for LEAR
        assert abs(table.loc["LEAR", "MAE"] - 1.0) < 1e-9
        # constant series: naive (shift-7) is exact after warmup
        assert table.loc[NAIVE, "MAE"] == 0.0


class TestBuildGwInputs:
    def test_identical_shapes_including_naive(self) -> None:
        rng = np.random.default_rng(0)
        actuals = _wide(rng.normal(size=(30, 4)))
        runs = {
            "LEAR": _wide(rng.normal(size=(30, 4))),
            "DNN": _wide(rng.normal(size=(30, 4))),
        }
        errors = build_gw_inputs(runs, actuals)
        shapes = {e.shape for e in errors.values()}
        assert shapes == {(23, 4)}  # 30 days minus 7-day naive warmup
        assert set(errors) == {"LEAR", "DNN", NAIVE}
        assert not any(np.isnan(e).any() for e in errors.values())


class TestToLatexBooktabs:
    def test_contains_booktabs_rules_and_label(self) -> None:
        df = pd.DataFrame({"MAE": [1.0]}, index=["LEAR"])
        out = to_latex_booktabs(df, caption="Cap", label="tab:x")
        assert "\\toprule" in out
        assert "\\label{tab:x}" in out
