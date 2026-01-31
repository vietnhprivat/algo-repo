from backtesting.models.base import BaseModel
from backtesting.models.lear import LearModel

__all__ = ['BaseModel', 'LearModel', 'get_model']

MODEL_REGISTRY = {
    'lear': LearModel,
}


def get_model(name: str, **kwargs) -> BaseModel:
    if name not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model: {name}. Available: {list(MODEL_REGISTRY.keys())}")
    return MODEL_REGISTRY[name](**kwargs)
