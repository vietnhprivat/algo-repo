from backtesting.models.base import BaseModel
import numpy as np

class DnnModel(BaseModel):
    def __init__(self, **kwargs):
        self.network = None

    def _build_network(self) -> None:
        pass

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        pass

    def predict(self, X: np.ndarray) -> np.ndarray:
        pass