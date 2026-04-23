import torch
import torch.nn as nn

from price_forecasting.models.lightning_base import LightningModel

_ACTIVATIONS: dict[str, type[nn.Module]] = {
    "relu": nn.ReLU,
    "tanh": nn.Tanh,
    "sigmoid": nn.Sigmoid,
}


class DNNModel(LightningModel):
    """
    Deep feedforward neural network for day-ahead electricity price forecasting.

    Architecture: input → hidden1 → hidden2 → output(n_periods).
    Single multivariate model — one forward pass predicts all periods simultaneously.
    Reference: Lago et al. (2021), Applied Energy 293, Section 4.3.
    """

    def __init__(
        self,
        hidden_units: tuple[int, int] | int = (256, 256),
        activation: str = "relu",
        dropout: float = 0.0,
        batch_norm: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.hidden_units: tuple[int, int] = (
            (hidden_units, hidden_units) if isinstance(hidden_units, int) else tuple(hidden_units)  # type: ignore[assignment]
        )
        self.activation = activation
        self.dropout = dropout
        self.batch_norm = batch_norm
        self.net: nn.Module | None = None

    def _build_network(self, n_features: int, n_periods: int) -> None:
        act_cls = _ACTIVATIONS.get(self.activation, nn.ReLU)
        layers: list[nn.Module] = []
        in_dim = n_features
        for h in self.hidden_units:
            layers.append(nn.Linear(in_dim, h))
            if self.batch_norm:
                layers.append(nn.BatchNorm1d(h))
            layers.append(act_cls())
            if self.dropout > 0.0:
                layers.append(nn.Dropout(self.dropout))
            in_dim = h
        layers.append(nn.Linear(in_dim, n_periods))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        assert self.net is not None, "_build_network must be called before forward()"
        return self.net(x)
