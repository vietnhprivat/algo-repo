import pandas as pd
import numpy as np
from typing import Any


class BacktestEngine:
    def __init__(self, calibration_window: int | None) -> None:
        self.calibration_window: int | None = calibration_window

    def run(
        self,
        model: Any,
        df_train: pd.DataFrame,
        df_test: pd.DataFrame,
        target_column: str,
        feature_columns: list,
    ) -> pd.DataFrame:
        num_days = len(df_test) // 24
        df_test = df_test.iloc[: num_days * 24].copy()

        test_dates = df_test.index[::24]
        forecast = pd.DataFrame(index=test_dates, columns=[f"h{i}" for i in range(24)])

        real_y = df_test[target_column].values.reshape(-1, 24)
        real_df = pd.DataFrame(real_y, index=test_dates, columns=forecast.columns)

        for date in test_dates:
            data_available = pd.concat(
                [df_train, df_test.loc[: date + pd.Timedelta(hours=23)]]
            ).copy()
            data_available.loc[date : date + pd.Timedelta(hours=23), target_column] = (
                np.nan
            )

            y_pred = model.recalibrate_and_forecast_next_day(
                df=data_available,
                calibration_window=self.calibration_window,
                next_day_date=date,
                target_column=target_column,
                feature_columns=feature_columns,
            )
            forecast.loc[date, :] = y_pred.flatten()

            error = forecast.loc[:date].values.astype(float) - real_df.loc[
                :date
            ].values.astype(float)
            current_mae = np.mean(np.abs(error))
            print(f"{str(date)[:10]} | Running MAE: {current_mae:.4f}")

        return forecast
