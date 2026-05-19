import numpy as np


class AsinhScaler:
    """Variance-stabilizing transform from Lago et al. 2021 (eq. 2).

    fit: stores median and median-absolute-deviation (MAD, with consistency
    factor 1.4826).
    transform: x' = asinh((x - median) / (1.4826 * MAD)).
    inverse_transform: x = sinh(x') * 1.4826 * MAD + median.
    """

    _MAD_CONSISTENCY = 1.4826

    def __init__(self) -> None:
        self.median_: np.ndarray | None = None
        self.scale_: np.ndarray | None = None

    def fit(self, x: np.ndarray) -> "AsinhScaler":
        self.median_ = np.median(x, axis=0, keepdims=True)
        mad = np.median(np.abs(x - self.median_), axis=0, keepdims=True)
        # Guard against zero MAD (constant column)
        self.scale_ = np.where(mad == 0, 1.0, mad) * self._MAD_CONSISTENCY
        return self

    def transform(self, x: np.ndarray) -> np.ndarray:
        if self.median_ is None or self.scale_ is None:
            raise RuntimeError("AsinhScaler must be fit before transform.")
        z = (x - self.median_) / self.scale_
        return np.arcsinh(z)

    def fit_transform(self, x: np.ndarray) -> np.ndarray:
        return self.fit(x).transform(x)

    def inverse_transform(self, x_scaled: np.ndarray) -> np.ndarray:
        if self.median_ is None or self.scale_ is None:
            raise RuntimeError("AsinhScaler must be fit before inverse_transform.")
        return np.sinh(x_scaled) * self.scale_ + self.median_
