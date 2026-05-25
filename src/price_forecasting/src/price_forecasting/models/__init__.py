from price_forecasting.models.base import BaseModel as BaseModel
from price_forecasting.models.base import LightningModel as LightningModel
from price_forecasting.models.lear import LearModel as LearModel
from price_forecasting.models.dnn import DNNModel as DNNModel
from price_forecasting.models.transformer import TransformerModel as TransformerModel

__all__ = [
    "BaseModel",
    "LightningModel",
    "LearModel",
    "DNNModel",
    "TransformerModel",
    "get_model",
]

MODEL_REGISTRY = {
    "lear": LearModel,
    "dnn": DNNModel,
    "transformer": TransformerModel,
}


def get_model(name: str, **kwargs) -> BaseModel:
    key = name.lower()
    if key not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model: {name}. Available: {list(MODEL_REGISTRY.keys())}"
        )
    return MODEL_REGISTRY[key](**kwargs)
