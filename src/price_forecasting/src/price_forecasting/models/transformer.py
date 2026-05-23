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
