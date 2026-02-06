from backtesting.models.base import BaseModel
import numpy as np
from sklearn.linear_model import Lasso
from typing import Dict

class LearModel(BaseModel):
    def __init__(self, **kwargs):
        self.sub_models: Dict[int, Lasso] = {}

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        pass

    def predict(self, X: np.ndarray) -> np.ndarray:
        pass