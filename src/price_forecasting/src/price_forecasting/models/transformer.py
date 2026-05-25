"""Pure-Transformer EPF model after Llorente & Portela (2025).

Architecture (paper Figure 2):

    Past prices (m × N)  ->  Embedding (Linear + ReLU)  ->  (m × n)
                          ->  + Positional Encoding
                          ->  Transformer Encoder stack  ->  (m × n)
                          ->  take last position         ->  (1 × n)

    Exogenous   (k × N)  ->  flatten (k·N,)
                          ->  Embedding (Linear + ReLU)  ->  (n,)

    concat(price_repr, exog_repr) -> MLP -> (N,) day-ahead prediction.

Where:
    m = sequence_length_days, N = n_periods (24 for hourly), n = embedding_dim,
    k = n_exog.

The model assumes the wide feature vector is laid out as
    [past_prices (m·N values, oldest day first), exogenous (k·N values)].
Use `default_transformers_for_transformer(...)` on the ExperimentConfig to
guarantee that layout.
"""

from __future__ import annotations

import torch
import torch.nn as nn

from price_forecasting.models.base import LightningModel


class TransformerNetwork(nn.Module):
    def __init__(
        self,
        seq_length_days: int,
        n_exog: int,
        n_periods: int,
        embedding_dim: int,
        n_heads: int,
        n_encoder_layers: int,
        ff_dim: int,
        dropout: float,
        mlp_hidden: int,
    ) -> None:
        super().__init__()
        if embedding_dim % n_heads != 0:
            raise ValueError(
                f"embedding_dim ({embedding_dim}) must be divisible by n_heads "
                f"({n_heads}) for nn.MultiheadAttention."
            )
        self.seq_length_days = seq_length_days
        self.n_exog = n_exog
        self.n_periods = n_periods
        self.embedding_dim = embedding_dim

        self.price_embedding = nn.Sequential(
            nn.Linear(n_periods, embedding_dim),
            nn.ReLU(),
        )
        self.exog_embedding = nn.Sequential(
            nn.Linear(n_exog * n_periods, embedding_dim),
            nn.ReLU(),
        )

        self.positional_encoding = nn.Parameter(
            torch.zeros(seq_length_days, embedding_dim)
        )
        nn.init.normal_(self.positional_encoding, std=0.02)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embedding_dim,
            nhead=n_heads,
            dim_feedforward=ff_dim,
            dropout=dropout,
            activation="relu",
            batch_first=True,
            norm_first=False,
        )
        self.transformer_encoder = nn.TransformerEncoder(
            encoder_layer, num_layers=n_encoder_layers
        )

        self.mlp = nn.Sequential(
            nn.Linear(2 * embedding_dim, mlp_hidden),
            nn.ReLU(),
            nn.Linear(mlp_hidden, n_periods),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        batch = x.shape[0]
        m, n_periods = self.seq_length_days, self.n_periods

        price_flat = x[:, : m * n_periods]
        exog_flat = x[:, m * n_periods :]

        price_seq = price_flat.view(batch, m, n_periods)
        price_emb = self.price_embedding(price_seq)
        price_emb = price_emb + self.positional_encoding.unsqueeze(0)
        encoded = self.transformer_encoder(price_emb)
        price_repr = encoded[:, -1, :]

        exog_repr = self.exog_embedding(exog_flat)

        combined = torch.cat([price_repr, exog_repr], dim=-1)
        return self.mlp(combined)


class TransformerModel(LightningModel):
    """Pure-Transformer EPF model wrapper.

    Plugs `TransformerNetwork` into the project's `LightningModel` base, which
    owns the Trainer loop, early stopping, in-memory best-weight restoration,
    and the seed-varied ensemble path used by `LiveRunner`.

    Feature-layout contract: the wide feature vector passed to `fit`/`predict_day`
    must be `[past_prices (seq_length_days * n_periods), exogenous (n_exog * n_periods)]`.
    Use `default_transformers_for_transformer(...)` on the ExperimentConfig.
    """

    def __init__(
        self,
        seq_length_days: int = 14,
        n_exog: int = 2,
        embedding_dim: int = 128,
        n_heads: int = 8,
        n_encoder_layers: int = 6,
        ff_dim: int = 1024,
        dropout: float = 0.2,
        mlp_hidden: int = 128,
        gradient_clip_val: float | None = None,
        lr_scheduler_step: int | None = None,
        lr_scheduler_gamma: float | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.seq_length_days = seq_length_days
        self.n_exog = n_exog
        self.embedding_dim = embedding_dim
        self.n_heads = n_heads
        self.n_encoder_layers = n_encoder_layers
        self.ff_dim = ff_dim
        self.dropout = dropout
        self.mlp_hidden = mlp_hidden
        self.gradient_clip_val = gradient_clip_val
        self.lr_scheduler_step = lr_scheduler_step
        self.lr_scheduler_gamma = lr_scheduler_gamma
        self.net: nn.Module | None = None

    def _build_network(self, n_features: int, n_periods: int) -> None:
        expected = self.seq_length_days * n_periods + self.n_exog * n_periods
        if n_features != expected:
            raise ValueError(
                f"TransformerModel expects {expected} features "
                f"({self.seq_length_days} days x {n_periods} periods + "
                f"{self.n_exog} exog x {n_periods} periods), got {n_features}. "
                "Use default_transformers_for_transformer(...) on the "
                "ExperimentConfig to produce the correct layout."
            )
        self.net = TransformerNetwork(
            seq_length_days=self.seq_length_days,
            n_exog=self.n_exog,
            n_periods=n_periods,
            embedding_dim=self.embedding_dim,
            n_heads=self.n_heads,
            n_encoder_layers=self.n_encoder_layers,
            ff_dim=self.ff_dim,
            dropout=self.dropout,
            mlp_hidden=self.mlp_hidden,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        assert self.net is not None, "_build_network must be called before forward()"
        # TransformerNetwork requires a batch dimension; add one if missing (inference path).
        unbatched = x.dim() == 1
        if unbatched:
            x = x.unsqueeze(0)
        out = self.net(x)
        if unbatched:
            out = out.squeeze(0)
        return out

    def configure_optimizers(self):
        optimizer = torch.optim.Adam(self.parameters(), lr=self.learning_rate)
        if self.lr_scheduler_step is not None and self.lr_scheduler_gamma is not None:
            scheduler = torch.optim.lr_scheduler.StepLR(
                optimizer,
                step_size=self.lr_scheduler_step,
                gamma=self.lr_scheduler_gamma,
            )
            return [optimizer], [scheduler]
        return optimizer

    def on_before_optimizer_step(self, optimizer) -> None:
        if self.gradient_clip_val is not None and self.gradient_clip_val > 0:
            torch.nn.utils.clip_grad_norm_(self.parameters(), self.gradient_clip_val)
