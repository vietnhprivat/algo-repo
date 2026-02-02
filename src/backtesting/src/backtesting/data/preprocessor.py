import pandas as pd
import numpy as np
from typing import Tuple


class DataPreprocessor:
    def __init__(self, data_path: str, date_column: str = 'Date', target_column: str = 'Price') -> None:
        self.data_path: str = data_path
        self.date_column: str = date_column
        self.target_column: str = target_column

    def load_and_prepare(self, train_test_split: float = 0.8) -> Tuple[pd.DataFrame, pd.DataFrame, list]:
        df = pd.read_csv(self.data_path)
        df[self.date_column] = pd.to_datetime(df.get(self.date_column, df.get('date')))
        df.sort_values(self.date_column, inplace=True)
        df.set_index(self.date_column, inplace=True)
        
        total_records = len(df)
        aligned_records = (total_records // 24) * 24
        df = df.iloc[:aligned_records]
        
        feature_cols = [col for col in df.columns if col != self.target_column.lower()]
        
        train_size = int(len(df) * train_test_split)
        train_size = (train_size // 24) * 24
        
        train_data = df.iloc[:train_size]
        test_data = df.iloc[train_size:]
        
        return train_data, test_data, feature_cols
