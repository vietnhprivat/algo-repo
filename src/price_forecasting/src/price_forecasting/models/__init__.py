from price_forecasting.models.base import BaseModel as BaseModel
from price_forecasting.models.lightning_base import LightningModel as LightningModel
from price_forecasting.models.gbt_base import GBTModel as GBTModel
from price_forecasting.models.sklearn_base import SklearnModel as SklearnModel
from price_forecasting.models.lear import LearModel as LearModel
from price_forecasting.models.dnn import DNNModel as DNNModel
from price_forecasting.models.random_forest import RandomForestModel as RandomForestModel
from price_forecasting.models.xgboost_model import XGBoostModel as XGBoostModel
from price_forecasting.models.lightgbm_model import LightGBMModel as LightGBMModel
from price_forecasting.models.catboost_model import CatBoostModel as CatBoostModel

__all__ = [
    "BaseModel",
    "LightningModel",
    "GBTModel",
    "SklearnModel",
    "LearModel",
    "DNNModel",
    "RandomForestModel",
    "XGBoostModel",
    "LightGBMModel",
    "CatBoostModel",
    "get_model",
]

MODEL_REGISTRY = {
    "lear": LearModel,
    "dnn": DNNModel,
    "rf": RandomForestModel,
    "xgboost": XGBoostModel,
    "lightgbm": LightGBMModel,
    "catboost": CatBoostModel,
}


def get_model(name: str, **kwargs) -> BaseModel:
    key = name.lower()
    if key not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model: {name}. Available: {list(MODEL_REGISTRY.keys())}"
        )
    return MODEL_REGISTRY[key](**kwargs)
