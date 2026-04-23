from price_forecasting.models.gbt_base import GBTModel


class LightGBMModel(GBTModel):
    """LightGBM — not yet implemented."""

    def _build_estimator(self) -> object:
        raise NotImplementedError("LightGBMModel is not yet implemented.")
