import numpy as np


def calculate_mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean Absolute Error (MAE). MAE = mean(|y - y_hat|)."""
    return np.mean(np.abs(y_true - y_pred))


def calculate_rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Root Mean Square Error (RMSE). RMSE = sqrt(mean((y - y_hat)^2))."""
    return np.sqrt(np.mean((y_true - y_pred) ** 2))


def calculate_smape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Symmetric MAPE (sMAPE). sMAPE = mean(2|y - y_hat|/(|y|+|y_hat|)) * 100."""
    denominator = (np.abs(y_true) + np.abs(y_pred)) / 2
    return np.mean(np.abs(y_pred - y_true) / denominator) * 100


def calculate_mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Mean Absolute Percentage Error (MAPE). MAPE = mean(|y - y_hat|/|y|) * 100."""
    denominator = np.abs(y_true)
    return np.mean(np.abs(y_true - y_pred) / denominator) * 100


def calculate_rmae(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_naive: np.ndarray,
) -> float:
    """Relative MAE (rMAE). rMAE = MAE(y, y_hat) / MAE(y, y_naive)."""
    denominator = calculate_mae(y_true, y_naive)
    if denominator == 0:
        return float("nan")
    return calculate_mae(y_true, y_pred) / denominator
