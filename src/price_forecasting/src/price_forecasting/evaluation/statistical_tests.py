from dataclasses import dataclass
from typing import Literal

import numpy as np
from scipy import stats


Loss = Literal["l1", "l2"]
Alternative = Literal["two_sided", "b_better", "a_better"]


@dataclass
class DMResult:
    statistic: float
    p_value: float
    mean_loss_diff: float
    n: int


def _loss(errors: np.ndarray, kind: Loss) -> np.ndarray:
    if kind == "l1":
        return np.abs(errors)
    if kind == "l2":
        return errors**2
    raise ValueError(f"Unknown loss: {kind!r}")


def diebold_mariano(
    errors_a: np.ndarray,
    errors_b: np.ndarray,
    loss: Loss = "l1",
    alternative: Alternative = "two_sided",
) -> DMResult:
    """Diebold-Mariano test on the loss-differential series d_t = L(e_a) - L(e_b).

    Null: E[d] = 0. Standardized statistic ~ N(0, 1) asymptotically.
    """
    errors_a = np.asarray(errors_a)
    errors_b = np.asarray(errors_b)
    if errors_a.shape != errors_b.shape:
        raise ValueError("errors_a and errors_b must have identical shape")
    d = _loss(errors_a, loss) - _loss(errors_b, loss)
    d = d.ravel()
    n = d.size
    mean_d = float(d.mean())
    std_d = float(d.std(ddof=1))
    if std_d == 0:
        statistic = 0.0
        p_two_sided = 1.0
    else:
        statistic = float(np.sqrt(n) * mean_d / std_d)
        p_two_sided = 2 * (1 - stats.norm.cdf(abs(statistic)))

    if alternative == "two_sided":
        p_value = p_two_sided
    elif alternative == "b_better":
        # H1: E[d] > 0  (model A's loss exceeds B's loss)
        p_value = 1 - stats.norm.cdf(statistic)
    elif alternative == "a_better":
        p_value = stats.norm.cdf(statistic)
    else:
        raise ValueError(f"Unknown alternative: {alternative!r}")

    return DMResult(
        statistic=statistic, p_value=float(p_value), mean_loss_diff=mean_d, n=n
    )
