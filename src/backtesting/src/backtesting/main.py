import pandas as pd
import numpy as np
from typing import Tuple
from backtesting.data_loader import DataPreprocessor
from backtesting.baseline_models import LearModel
from backtesting.engine import BacktestEngine
from backtesting.metrics import calculate_mae, calculate_rmse, calculate_smape
from backtesting.configs.backtesting_configs import configs, Configurations
from backtesting.baseline_models import ModelWrapper

def main() -> Tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Main function to run backtesting with LearModel and calculate metrics."""
    
    print("=" * 60)
    print("Backtesting with LearModel")
    print("=" * 60)
    
    # Step 1: Load and preprocess data
    print("\n1. Loading and preprocessing data...")
    config = Configurations()
    data_preprocessor = DataPreprocessor(config, 'DE_data.csv')
    
    try:
        data_preprocessor.preprocess_data()
        print("   Data preprocessing completed.")
    except Exception as e:
        print(f"   Preprocessing error (data might already be processed): {e}")
    
    # Load the preprocessed data
    train_data, test_data = data_preprocessor.load_data()
    
    # Rename 'price' to 'Price' if needed for consistency
    if 'price' in train_data.columns:
        train_data.rename(columns={'price': 'Price'}, inplace=True)
    if 'price' in test_data.columns:
        test_data.rename(columns={'price': 'Price'}, inplace=True)
    
    print(f"   Training data shape: {train_data.shape}")
    print(f"   Test data shape: {test_data.shape}")
    print(f"\n   Training data columns: {train_data.columns.tolist()}")
    print(f"   Training data head:\n{train_data.head()}\n")
    
    # Step 2: Create and train the model
    print("2. Creating and training LearModel...")
    model_wrapper = ModelWrapper()
    
    # Prepare training data - create 24-hour windows
    price_col = 'Price'
    feature_cols = [col for col in train_data.columns if col != price_col and col != 'date']
    
    X_train = train_data[feature_cols].values
    y_train = train_data[price_col].values
    
    # Reshape into 24-hour windows
    num_windows = len(y_train) // 24
    if num_windows > 0:
        X_train_reshaped = X_train[:num_windows*24].reshape(num_windows, -1)
        y_train_reshaped = y_train[:num_windows*24].reshape(num_windows, 24)
        
        model_wrapper.model.fit(X_train_reshaped, y_train_reshaped)
        print(f"   Model training completed with {num_windows} windows")
    else:
        print("   Warning: Not enough training data for proper model training")
    
    # Step 3: Run backtest
    print("\n3. Running backtest engine...")
    calibration_window = 7 * 24  # Use last 7 days for calibration
    engine = BacktestEngine(calibration_window=calibration_window)
    
    forecast = engine.run(model_wrapper, train_data, test_data)
    print(f"\n   Forecast shape: {forecast.shape}")
    print(f"   Forecast head:\n{forecast.head()}\n")
    
    # Step 4: Calculate metrics
    print("4. Calculating metrics...")
    
    # Get real values and predicted values
    test_dates = test_data.index[::24]
    real_y = test_data[price_col].values.reshape(-1, 24)
    real_df = pd.DataFrame(real_y, index=test_dates, columns=forecast.columns)
    
    # Convert to numeric
    y_true = real_df.values.astype(float).flatten()
    y_pred = forecast.values.astype(float).flatten()
    
    # Remove NaN values
    mask = ~(np.isnan(y_true) | np.isnan(y_pred))
    y_true_clean = y_true[mask]
    y_pred_clean = y_pred[mask]
    
    if len(y_true_clean) > 0:
        mae = calculate_mae(y_true_clean, y_pred_clean)
        rmse = calculate_rmse(y_true_clean, y_pred_clean)
        smape = calculate_smape(y_true_clean, y_pred_clean)
        
        print(f"\n   Backtesting Metrics:")
        print(f"   {'─' * 40}")
        print(f"   Mean Absolute Error (MAE):        {mae:.4f}")
        print(f"   Root Mean Squared Error (RMSE):   {rmse:.4f}")
        print(f"   Symmetric MAPE (SMAPE):           {smape:.4f}%")
        print(f"   {'─' * 40}")
        print(f"   Number of valid predictions:      {len(y_pred_clean)}")
    else:
        print("   Error: No valid predictions to calculate metrics")
    
    # Step 5: Save results
    print("\n5. Saving results...")
    try:
        forecast.to_csv(f"{config.results_path}/forecast_results.csv")
        print(f"   Forecast saved to {config.results_path}/forecast_results.csv")
    except Exception as e:
        print(f"   Could not save results: {e}")
    
    print("\n" + "=" * 60)
    print("Backtesting completed successfully!")
    print("=" * 60)
    
    return forecast, y_true_clean, y_pred_clean


if __name__ == "__main__":
    forecast, y_true, y_pred = main()
