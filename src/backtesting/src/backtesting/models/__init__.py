from backtesting.models.base import BaseModel
from backtesting.models.lear import LearModel
from backtesting.models.dnn import DNNModel

__all__ = ["BaseModel", "LearModel", "DNNModel", "get_model"]

MODEL_REGISTRY = {
    "lear": LearModel,
    "dnn": DNNModel,
}


def get_model(name: str, **kwargs) -> BaseModel:
    key = name.lower()
    if key not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model: {name}. Available: {list(MODEL_REGISTRY.keys())}"
        )
    return MODEL_REGISTRY[key](**kwargs)
