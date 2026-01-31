import pandas as pd
from typing import Tuple
from backtesting.configs.backtesting_configs import configs, Configurations


class DataPreprocessor:
    def __init__(self, config: Configurations, file_name: str) -> None:
        self.config: Configurations = config
        self.file_name: str = file_name

    def preprocess_data(self) -> None:
        df = pd.read_csv(self.config.data_directory + f"/{self.file_name}")
        df['Date'] = pd.to_datetime(df['date'])
        df.sort_values('Date', inplace=True)
        df.set_index('Date', inplace=True)
        
        total_records = len(df)
        aligned_records = (total_records // 24) * 24
        df = df.iloc[:aligned_records]
        
        train_size = int(len(df) * 0.8)
        train_size = (train_size // 24) * 24
        
        train_data = df.iloc[:train_size]
        test_data = df.iloc[train_size:]
        
        train_data.to_csv(f"{self.config.data_directory}/train_data.csv")
        test_data.to_csv(f"{self.config.data_directory}/test_data.csv")

    
    def load_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        train_data = pd.read_csv(f"{self.config.data_directory}/train_data.csv")
        test_data = pd.read_csv(f"{self.config.data_directory}/test_data.csv")
        train_data['Date'] = pd.to_datetime(train_data['Date'])
        test_data['Date'] = pd.to_datetime(test_data['Date'])
        train_data.set_index('Date', inplace=True)
        test_data.set_index('Date', inplace=True)

        return train_data, test_data