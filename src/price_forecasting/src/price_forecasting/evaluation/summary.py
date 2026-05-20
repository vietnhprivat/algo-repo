from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import pandas as pd

from price_forecasting.evaluation.metrics import (
    calculate_mae,
    calculate_rmae,
    calculate_rmse,
    calculate_smape,
)
from price_forecasting.evaluation.statistical_tests import giacomini_white_multivariate


def build_weekly_naive(actuals: pd.DataFrame) -> pd.DataFrame:
    return actuals.shift(7)


def _flatten_values(data_frame: pd.DataFrame) -> np.ndarray:
    return data_frame.to_numpy().reshape(-1)


def _align_for_rmae(
    forecasts: pd.DataFrame,
    actuals: pd.DataFrame,
    naive_forecasts: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    aligned_actuals, aligned_forecasts = actuals.align(forecasts, join="inner", axis=0)
    aligned_naive, _ = naive_forecasts.align(aligned_actuals, join="right", axis=0)

    valid_mask = aligned_naive.notna().all(axis=1)
    aligned_actuals = aligned_actuals.loc[valid_mask]
    aligned_forecasts = aligned_forecasts.loc[valid_mask]
    aligned_naive = aligned_naive.loc[valid_mask]

    return (
        _flatten_values(aligned_actuals),
        _flatten_values(aligned_forecasts),
        _flatten_values(aligned_naive),
    )


def compute_metrics_summary(
    forecasts: pd.DataFrame,
    actuals: pd.DataFrame,
    naive_forecasts: pd.DataFrame | None = None,
) -> dict[str, Any]:
    aligned_actuals, aligned_forecasts = actuals.align(forecasts, join="inner", axis=0)
    actual_values = _flatten_values(aligned_actuals)
    forecast_values = _flatten_values(aligned_forecasts)

    summary = {
        "mae": calculate_mae(actual_values, forecast_values),
        "rmse": calculate_rmse(actual_values, forecast_values),
        "smape": calculate_smape(actual_values, forecast_values),
    }

    if naive_forecasts is not None:
        actual_values, forecast_values, naive_values = _align_for_rmae(
            forecasts, actuals, naive_forecasts
        )
        summary["rmae"] = calculate_rmae(actual_values, forecast_values, naive_values)

    return summary


def compute_metrics_per_hour(
    forecasts: pd.DataFrame,
    actuals: pd.DataFrame,
    naive_forecasts: pd.DataFrame | None = None,
) -> pd.DataFrame:
    aligned_actuals, aligned_forecasts = actuals.align(forecasts, join="inner", axis=0)
    metrics_rows = []

    for column in aligned_actuals.columns:
        actual_values = aligned_actuals[column].to_numpy()
        forecast_values = aligned_forecasts[column].to_numpy()

        row = {
            "hour": column,
            "mae": calculate_mae(actual_values, forecast_values),
            "rmse": calculate_rmse(actual_values, forecast_values),
            "smape": calculate_smape(actual_values, forecast_values),
        }

        if naive_forecasts is not None:
            naive_values = naive_forecasts[column].reindex(aligned_actuals.index)
            valid_mask = naive_values.notna()
            row["rmae"] = calculate_rmae(
                actual_values[valid_mask.to_numpy()],
                forecast_values[valid_mask.to_numpy()],
                naive_values[valid_mask].to_numpy(),
            )

        metrics_rows.append(row)

    return pd.DataFrame(metrics_rows)


def build_dm_matrix(
    errors_by_model: Mapping[str, np.ndarray],
    norm: int = 1,
) -> pd.DataFrame:
    """Pairwise GW-multivariate p-values, with H1 = "column model is better".

    matrix.loc[row, col] is the p-value of the one-sided test that the column
    model's forecasts are significantly more accurate than the row model's
    (Lago Fig. 5 convention).
    """
    names = list(errors_by_model.keys())
    shapes = {name: errors_by_model[name].shape for name in names}
    unique_shapes = set(shapes.values())
    if len(unique_shapes) > 1:
        raise ValueError(
            f"All error arrays must have identical shape; got {shapes}"
        )
    matrix = pd.DataFrame(
        np.full((len(names), len(names)), np.nan), index=names, columns=names
    )
    for row in names:
        for col in names:
            if row == col:
                continue
            result = giacomini_white_multivariate(
                errors_by_model[row],
                errors_by_model[col],
                norm=norm,
                alternative="b_better",
            )
            matrix.loc[row, col] = result.p_value
    return matrix
