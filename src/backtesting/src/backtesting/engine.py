import pandas as pd
import numpy as np
from typing import Any, Optional
from backtesting.baseline_models import ModelWrapper

class BacktestEngine:
    def __init__(self, calibration_window: Optional[int]) -> None:
        self.calibration_window: Optional[int] = calibration_window

    def run(self, model: ModelWrapper, df_train: pd.DataFrame, df_test: pd.DataFrame) -> pd.DataFrame:
        num_days = len(df_test) // 24
        df_test = df_test.iloc[:num_days * 24].copy()
        
        test_dates = df_test.index[::24]
        forecast = pd.DataFrame(index=test_dates, columns=[f'h{i}' for i in range(24)])
        
        real_y = df_test['Price'].values.reshape(-1, 24)
        real_df = pd.DataFrame(real_y, index=test_dates, columns=forecast.columns)

        for date in test_dates:
            data_available = pd.concat([df_train, df_test.loc[:date + pd.Timedelta(hours=23)]]).copy()
            data_available.loc[date:date + pd.Timedelta(hours=23), 'Price'] = np.nan

            y_pred = model.recalibrate_and_forecast_next_day(
                df=data_available, 
                calibration_window=self.calibration_window, 
                next_day_date=date
            )
            forecast.loc[date, :] = y_pred.flatten()
            
            error = forecast.loc[:date].values.astype(float) - real_df.loc[:date].values.astype(float)
            current_mae = np.mean(np.abs(error))
            print(f"{str(date)[:10]} | Running MAE: {current_mae:.4f}")

        return forecast    

