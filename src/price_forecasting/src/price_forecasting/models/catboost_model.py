from price_forecasting.models.gbt_base import GBTModel


class CatBoostModel(GBTModel):
    """CatBoost — not yet implemented."""

    def _build_estimator(self) -> object:
        raise NotImplementedError("CatBoostModel is not yet implemented.")
