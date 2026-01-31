import numpy as np
import pandas as pd
from typing import Dict
from sklearn.linear_model import Lasso, LassoLarsIC
from sklearn.preprocessing import StandardScaler
from sklearn.exceptions import ConvergenceWarning
import warnings

from backtesting.models.base import BaseModel


class LearModel(BaseModel):
    def __init__(self) -> None:
        self.models: Dict[int, Lasso] = {}
        self.scaler_x: StandardScaler = StandardScaler()
        self.scaler_y: StandardScaler = StandardScaler()

    def _asinh_transform(self, data: np.ndarray, inverse: bool = False) -> np.ndarray:
        if inverse:
            return np.sinh(data)
        return np.arcsinh(data)

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        y_trans = self._asinh_transform(y)
        y_scaled = self.scaler_y.fit_transform(y_trans)

        X_trans = self._asinh_transform(X)
        X_scaled_values = self.scaler_x.fit_transform(X_trans[:, :-7])
        X_scaled = np.hstack([X_scaled_values, X_trans[:, -7:]])

        warnings.filterwarnings("ignore", category=ConvergenceWarning)
        
        n_samples, n_features = X_scaled.shape
        
        for h in range(24):
            if n_samples > n_features:
                selector = LassoLarsIC(criterion='aic', max_iter=2500)
                selector.fit(X_scaled, y_scaled[:, h])
                alpha = selector.alpha_
            else:
                alpha = 0.1
            
            model = Lasso(alpha=alpha, max_iter=2500)
            model.fit(X_scaled, y_scaled[:, h])
            self.models[h] = model

    def predict(self, X: np.ndarray) -> np.ndarray:
        X_trans = self._asinh_transform(X)
        X_scaled_values = self.scaler_x.transform(X_trans[:, :-7])
        X_scaled = np.hstack([X_scaled_values, X_trans[:, -7:]])

        y_pred_scaled = np.zeros((X.shape[0], 24))
        for h in range(24):
            y_pred_scaled[:, h] = self.models[h].predict(X_scaled)

        y_pred_trans = self.scaler_y.inverse_transform(y_pred_scaled)
        return self._asinh_transform(y_pred_trans, inverse=True)

    def recalibrate_and_forecast_next_day(
        self,
        df: pd.DataFrame,
        calibration_window: int | None,
        next_day_date: pd.Timestamp,
        target_column: str,
        feature_columns: list
    ) -> np.ndarray:
        calibration_data = df.dropna(subset=[target_column]).copy()
        
        if calibration_window:
            calibration_data = calibration_data.iloc[-calibration_window:].copy()
        
        if len(calibration_data) < 24:
            return np.zeros(24)
        
        X_train = calibration_data[feature_columns].values
        y_train = calibration_data[target_column].values.reshape(-1, 1)
        
        if len(X_train) < 24:
            pad_size = 24 - len(X_train)
            X_train = np.vstack([np.zeros((pad_size, X_train.shape[1])), X_train])
            y_train = np.vstack([np.zeros((pad_size, 1)), y_train])
        
        num_windows = len(y_train) // 24
        if num_windows > 0:
            X_reshaped = X_train[-num_windows*24:].reshape(num_windows, -1)
            y_reshaped = y_train[-num_windows*24:].reshape(num_windows, 24)
            
            self.fit(X_reshaped, y_reshaped)
            
            X_test = X_train[-24:].reshape(1, -1)
            forecast = self.predict(X_test)
            return forecast.flatten()
        else:
            return np.zeros(24)
