import pandas as pd
import numpy as np
from typing import Dict, Any

from backtesting.configs.experiment import ExperimentConfig
from backtesting.data.preprocessor import DataPreprocessor
from backtesting.models import get_model
from backtesting.engine import BacktestEngine
from backtesting.metrics import calculate_mae, calculate_rmse, calculate_smape


class BacktestRunner:
    def __init__(self, config: ExperimentConfig) -> None:
        self.config = config

    def run(self) -> Dict[str, Any]:
        print("=" * 60)
        print(f"Running backtest: {self.config.model_name}")
        print("=" * 60)
        
        print("\n1. Loading and preprocessing data...")
        preprocessor = DataPreprocessor(
            self.config.data_path,
            self.config.date_column,
            self.config.target_column
        )
        train_data, test_data, auto_features = preprocessor.load_and_prepare(
            self.config.train_test_split
        )
        
        feature_cols = self.config.feature_columns if self.config.feature_columns else auto_features
        print(f"   Train shape: {train_data.shape}, Test shape: {test_data.shape}")
        print(f"   Features: {feature_cols}")
        
        print("\n2. Creating and training model...")
        model = get_model(self.config.model_name, **self.config.model_params)
        
        X_train = train_data[feature_cols].values
        y_train = train_data[self.config.target_column].values
        num_windows = len(y_train) // 24
        
        if num_windows > 0:
            X_train_reshaped = X_train[:num_windows*24].reshape(num_windows, -1)
            y_train_reshaped = y_train[:num_windows*24].reshape(num_windows, 24)
            model.fit(X_train_reshaped, y_train_reshaped)
            print(f"   Model training completed with {num_windows} windows")
        else:
            print("   Warning: Not enough training data")
        
        print("\n3. Running backtest...")
        engine = BacktestEngine(calibration_window=self.config.calibration_window)
        forecast = engine.run(
            model,
            train_data,
            test_data,
            self.config.target_column,
            feature_cols
        )
        print(f"   Forecast shape: {forecast.shape}")
        
        print("\n4. Calculating metrics...")
        test_dates = test_data.index[::24]
        real_y = test_data[self.config.target_column].values.reshape(-1, 24)
        real_df = pd.DataFrame(real_y, index=test_dates, columns=forecast.columns)
        
        y_true = real_df.values.astype(float).flatten()
        y_pred = forecast.values.astype(float).flatten()
        
        mask = ~(np.isnan(y_true) | np.isnan(y_pred))
        y_true_clean = y_true[mask]
        y_pred_clean = y_pred[mask]
        
        results = {}
        if len(y_true_clean) > 0:
            results['mae'] = calculate_mae(y_true_clean, y_pred_clean)
            results['rmse'] = calculate_rmse(y_true_clean, y_pred_clean)
            results['smape'] = calculate_smape(y_true_clean, y_pred_clean)
            results['num_predictions'] = len(y_pred_clean)
            
            print(f"\n   Backtesting Metrics:")
            print(f"   {'─' * 40}")
            print(f"   MAE:  {results['mae']:.4f}")
            print(f"   RMSE: {results['rmse']:.4f}")
            print(f"   SMAPE: {results['smape']:.4f}%")
            print(f"   {'─' * 40}")
            print(f"   Predictions: {results['num_predictions']}")
        else:
            print("   Error: No valid predictions")
        
        print("\n5. Saving results...")
        try:
            forecast.to_csv(f"{self.config.results_dir}/forecast.csv")
            print(f"   Forecast saved to {self.config.results_dir}/forecast.csv")
        except Exception as e:
            print(f"   Could not save results: {e}")
        
        print("\n" + "=" * 60)
        print("Backtest completed!")
        print("=" * 60)
        
        results['forecast'] = forecast
        results['y_true'] = y_true_clean
        results['y_pred'] = y_pred_clean
        
        return results
