from abc import ABC, abstractmethod
import numpy as np

class BaseModel(ABC):
    """Interface to ensure Engine can run any model (LEAR or DNN)."""
    
    @abstractmethod
    def fit(self, features: np.ndarray, targets: np.ndarray) -> None:
        pass

    @abstractmethod
    def predict_day(self, features: np.ndarray) -> np.ndarray:
        pass
