from backtesting.configs.experiment import ExperimentConfig
from backtesting.engine import BacktestEngine
from backtesting.models.base import BaseModel
import pandas as pd

class BacktestRunner:
    def __init__(self, config: ExperimentConfig):
        self.config: ExperimentConfig = config

    def _initialize_model(self) -> BaseModel:
        pass

    def execute(self) -> pd.DataFrame:
        pass