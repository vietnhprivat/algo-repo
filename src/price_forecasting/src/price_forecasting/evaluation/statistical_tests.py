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


@dataclass
class GWResult:
    statistic: float
    p_value: float
    mean_loss_diff: float
    n_days: int


def giacomini_white_multivariate(
    errors_a: np.ndarray,
    errors_b: np.ndarray,
    norm: int = 1,
    alternative: Alternative = "two_sided",
) -> GWResult:
    """Multivariate GW test on the daily Lp-norm loss differential
    (Lago §5.5.2, eqs. 13 and 16).

    For p=1: d_t = sum_h |e^A_{t,h}| - sum_h |e^B_{t,h}|.
    For p=2: d_t = sum_h (e^A_{t,h})^2 - sum_h (e^B_{t,h})^2.

    The (unconditional) GW statistic is the t-statistic on the intercept in
    a regression of d_t on a constant, with Newey-West HAC standard errors
    (lag = floor(n^(1/4))).
    """
    errors_a = np.asarray(errors_a)
    errors_b = np.asarray(errors_b)
    if errors_a.shape != errors_b.shape:
        raise ValueError("errors_a and errors_b must have identical shape")
    if errors_a.ndim != 2:
        raise ValueError("errors_* must be 2-D (n_days, n_periods)")
    if norm == 1:
        d = np.abs(errors_a).sum(axis=1) - np.abs(errors_b).sum(axis=1)
    elif norm == 2:
        d = (errors_a**2).sum(axis=1) - (errors_b**2).sum(axis=1)
    else:
        raise ValueError("norm must be 1 or 2")

    n = d.size
    mean_d = float(d.mean())
    centered = d - mean_d
    lag = int(np.floor(n**0.25))
    # Newey-West HAC variance
    var = float((centered**2).mean())
    for k in range(1, lag + 1):
        weight = 1.0 - k / (lag + 1.0)
        cov = float((centered[k:] * centered[:-k]).mean())
        var += 2.0 * weight * cov
    se = float(np.sqrt(var / n))
    statistic = mean_d / se if se > 0 else 0.0
    p_two_sided = 2 * (1 - stats.norm.cdf(abs(statistic)))
    if alternative == "two_sided":
        p_value = p_two_sided
    elif alternative == "b_better":
        p_value = 1 - stats.norm.cdf(statistic)
    elif alternative == "a_better":
        p_value = stats.norm.cdf(statistic)
    else:
        raise ValueError(f"Unknown alternative: {alternative!r}")
    return GWResult(
        statistic=float(statistic),
        p_value=float(p_value),
        mean_loss_diff=mean_d,
        n_days=n,
    )
