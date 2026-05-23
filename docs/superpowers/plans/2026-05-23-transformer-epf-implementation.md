# Transformer EPF Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Llorente & Portela (2025)'s pure-Transformer EPF model as a `"transformer"` entry in `MODEL_REGISTRY`, drivable through `forecast-cli backtest <config>` and `forecast-cli predict <config> -d <date>`. **No Prefect deployment** — the model is *implemented*, not *scheduled*.

**Architecture:** Two-flow Transformer per Figure 2a of the paper:
1. **Past-prices flow:** an `m × 24` matrix (the last `m` days of hourly prices) → per-day Embedding (`Linear → ReLU`) → learnable positional encoding → stack of `NL` standard `nn.TransformerEncoderLayer` blocks → take the last position's representation.
2. **Exogenous flow:** the day-ahead exogenous forecast for D+1, flattened to `n_exog × 24` → Embedding (`Linear → ReLU`).
3. The two outputs are concatenated and fed into a Multi-Layer Perceptron that emits the 24-period day-ahead prediction.

The model plugs into the existing `LightningModel` base class (which already owns the Lightning Trainer loop, early stopping, in-memory best-weight restoration, and the seed-varied ensemble path used by `LiveRunner`). Two new `FeatureTransformer`s produce the *exact* wide-format layout the model expects so that no contract changes are needed in `DataPreprocessor`, `BacktestEngine`, or `LiveRunner`.

**Tech Stack:** PyTorch + Lightning (already in the repo for `DNNModel`), pandas (feature transformers), pytest. No new third-party dependencies.

---

## Pre-flight reading (mandatory)

Before any task, the implementing agent reads, in order:

1. `CLAUDE.md` — project conventions (especially the *Models* and *Tests* sections).
2. `docs/REPO_OVERVIEW.md` §8 — the full price-forecasting pipeline.
3. `src/price_forecasting/src/price_forecasting/models/base.py` — the 2-method `BaseModel` interface.
4. `src/price_forecasting/src/price_forecasting/models/lightning_base.py` — owns `fit()`, `predict_day()`, and exposes `_build_network(n_features, n_periods)` + `forward(x)` as the two abstract hooks.
5. `src/price_forecasting/src/price_forecasting/models/dnn.py` — the canonical example of a `LightningModel` subclass.
6. `src/price_forecasting/src/price_forecasting/data/transformers.py` — the `FeatureTransformer` interface and the `pivot_to_daily` helper.
7. `tests/price_forecasting/test_models.py` and `tests/price_forecasting/test_transformers.py` — the test idiom (helpers in `conftest.py`, `make_hourly_dataframe`, `StubModel`).
8. `researh_material/A Transformer approach for Electricity Price Forecasting.pdf` §2 and Figures 2–3 — model definition.

Reads are cheap; assumptions cost rewrites. Do not skip.

---

## File Structure

**New files:**
- `src/price_forecasting/src/price_forecasting/models/transformer.py` — the `TransformerNetwork` (pure `nn.Module`) and the `TransformerModel(LightningModel)` wrapper.
- `tests/price_forecasting/test_transformer_model.py` — model-level unit tests.
- `configs/dk1_transformer.py` — example configuration (DK1, hourly, paper-grade defaults). **Intentionally not added to `FORECAST_CONFIGS`** in `src/schedules/src/schedules/deploy_forecast.py`.

**Modified files:**
- `src/price_forecasting/src/price_forecasting/data/transformers.py` — add `PastPriceSequenceTransformer`, `DayAheadExogTransformer`, and a `default_transformers_for_transformer(...)` helper.
- `src/price_forecasting/src/price_forecasting/models/__init__.py` — register `TransformerModel` in `MODEL_REGISTRY`.
- `tests/price_forecasting/test_transformers.py` — add tests for the two new transformers.

---

### Task 0: Verify baseline test suite is green

**Files:**
- No files modified.

- [ ] **Step 1: Run the existing test suite**

Run: `uv run python -m pytest tests/price_forecasting/ -q`
Expected: all tests pass on the current `main`. If anything is already red, stop and surface that to the human — do not pile new changes on top of a broken baseline.

---

### Task 1: Add `PastPriceSequenceTransformer` (TDD)

**Files:**
- Modify: `tests/price_forecasting/test_transformers.py` (append new test class)
- Modify: `src/price_forecasting/src/price_forecasting/data/transformers.py` (add new class)

- [ ] **Step 1: Write the failing test**

Append to `tests/price_forecasting/test_transformers.py`:

```python
class TestPastPriceSequenceTransformer:
    def test_outputs_m_days_of_n_periods_in_oldest_first_order(self):
        from price_forecasting.data.transformers import PastPriceSequenceTransformer

        hourly = make_hourly_dataframe(n_days=10, n_periods=24, columns=["price"])
        daily_prices = pivot_to_daily(hourly, "price")

        m = 3
        transformer = PastPriceSequenceTransformer(sequence_length_days=m)
        out = transformer.transform(hourly, daily_prices)

        # Column count = m * n_periods
        assert out.shape[1] == m * 24

        # Column ordering: oldest day (d{m}) first, yesterday (d1) last.
        expected_cols = (
            [f"seq_d{k}_p{p}" for k in range(m, 0, -1) for p in range(24)]
        )
        assert list(out.columns) == expected_cols

        # The "d1" block on row i equals daily_prices on row i-1 (yesterday).
        # The "d{m}" block on row i equals daily_prices on row i-m.
        # Skip rows where shift produces NaN.
        first_valid = m
        d1_block = out.iloc[first_valid][[f"seq_d1_p{p}" for p in range(24)]].values
        np.testing.assert_array_equal(d1_block, daily_prices.iloc[first_valid - 1].values)

        dm_block = out.iloc[first_valid][[f"seq_d{m}_p{p}" for p in range(24)]].values
        np.testing.assert_array_equal(dm_block, daily_prices.iloc[first_valid - m].values)

    def test_rejects_non_positive_sequence_length(self):
        import pytest
        from price_forecasting.data.transformers import PastPriceSequenceTransformer

        with pytest.raises(ValueError):
            PastPriceSequenceTransformer(sequence_length_days=0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/price_forecasting/test_transformers.py::TestPastPriceSequenceTransformer -v`
Expected: FAIL with `ImportError: cannot import name 'PastPriceSequenceTransformer'`.

- [ ] **Step 3: Implement the transformer**

Append to `src/price_forecasting/src/price_forecasting/data/transformers.py` (after the existing `MeanWeeklyForecastTransformer`):

```python
class PastPriceSequenceTransformer(FeatureTransformer):
    """Past `m` days of hourly prices, arranged oldest-day-first.

    Output columns, in order:
        seq_d{m}_p0..seq_d{m}_p{N-1},  # m days before D+1 (oldest)
        seq_d{m-1}_p0..,
        ...
        seq_d1_p0..seq_d1_p{N-1}       # yesterday

    For TransformerModel consumption: a row of length `m * N` that the model
    reshapes to `(m, N)` with row 0 = oldest day.
    """

    def __init__(self, sequence_length_days: int) -> None:
        if sequence_length_days < 1:
            raise ValueError("sequence_length_days must be >= 1")
        self.sequence_length_days = sequence_length_days

    def transform(
        self, hourly_df: pd.DataFrame, daily_prices: pd.DataFrame
    ) -> pd.DataFrame:
        n_periods = daily_prices.shape[1]
        blocks: list[pd.DataFrame] = []
        for k in range(self.sequence_length_days, 0, -1):
            shifted = daily_prices.shift(k).copy()
            shifted.columns = [f"seq_d{k}_p{p}" for p in range(n_periods)]
            blocks.append(shifted)
        return pd.concat(blocks, axis=1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/price_forecasting/test_transformers.py::TestPastPriceSequenceTransformer -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/price_forecasting/src/price_forecasting/data/transformers.py \
        tests/price_forecasting/test_transformers.py
git commit -m "feat(transformers): add PastPriceSequenceTransformer for the Transformer EPF model"
```

---

### Task 2: Add `DayAheadExogTransformer` (TDD)

**Files:**
- Modify: `tests/price_forecasting/test_transformers.py`
- Modify: `src/price_forecasting/src/price_forecasting/data/transformers.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/price_forecasting/test_transformers.py`:

```python
class TestDayAheadExogTransformer:
    def test_outputs_one_block_per_exog_column(self):
        from price_forecasting.data.transformers import DayAheadExogTransformer

        hourly = make_hourly_dataframe(
            n_days=5, n_periods=24, columns=["price", "load_forecast", "gen_forecast"]
        )
        daily_prices = pivot_to_daily(hourly, "price")

        transformer = DayAheadExogTransformer(
            exogenous_columns=["load_forecast", "gen_forecast"]
        )
        out = transformer.transform(hourly, daily_prices)

        assert out.shape[1] == 2 * 24
        expected_cols = (
            [f"exog_load_forecast_p{p}" for p in range(24)]
            + [f"exog_gen_forecast_p{p}" for p in range(24)]
        )
        assert list(out.columns) == expected_cols

        # The exog block equals the day-of pivot (lag 0) — the D+1 forecast
        # that is known at prediction time.
        load_daily = pivot_to_daily(hourly, "load_forecast")
        np.testing.assert_allclose(
            out[[f"exog_load_forecast_p{p}" for p in range(24)]].values,
            load_daily.values,
        )

    def test_rejects_empty_exogenous_columns(self):
        import pytest
        from price_forecasting.data.transformers import DayAheadExogTransformer

        with pytest.raises(ValueError):
            DayAheadExogTransformer(exogenous_columns=[])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/price_forecasting/test_transformers.py::TestDayAheadExogTransformer -v`
Expected: FAIL with `ImportError: cannot import name 'DayAheadExogTransformer'`.

- [ ] **Step 3: Implement the transformer**

Append to `src/price_forecasting/src/price_forecasting/data/transformers.py`:

```python
class DayAheadExogTransformer(FeatureTransformer):
    """Day-ahead exogenous forecast for D+1, one block of `n_periods` columns per variable.

    Output columns, in order:
        exog_{col_1}_p0..exog_{col_1}_p{N-1},
        exog_{col_2}_p0..,
        ...

    For TransformerModel consumption: a row of length `n_exog * N` that the
    model reshapes to `(n_exog, N)`.
    """

    def __init__(self, exogenous_columns: list[str]) -> None:
        if not exogenous_columns:
            raise ValueError("exogenous_columns must contain at least one entry")
        self.exogenous_columns = list(exogenous_columns)

    def transform(
        self, hourly_df: pd.DataFrame, daily_prices: pd.DataFrame
    ) -> pd.DataFrame:
        blocks: list[pd.DataFrame] = []
        for col in self.exogenous_columns:
            daily_col = pivot_to_daily(hourly_df, col)
            n_periods = daily_col.shape[1]
            daily_col = daily_col.copy()
            daily_col.columns = [f"exog_{col}_p{p}" for p in range(n_periods)]
            blocks.append(daily_col)
        return pd.concat(blocks, axis=1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/price_forecasting/test_transformers.py::TestDayAheadExogTransformer -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/price_forecasting/src/price_forecasting/data/transformers.py \
        tests/price_forecasting/test_transformers.py
git commit -m "feat(transformers): add DayAheadExogTransformer for the Transformer EPF model"
```

---

### Task 3: Add `default_transformers_for_transformer` factory (TDD)

**Files:**
- Modify: `tests/price_forecasting/test_transformers.py`
- Modify: `src/price_forecasting/src/price_forecasting/data/transformers.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/price_forecasting/test_transformers.py`:

```python
class TestDefaultTransformersForTransformer:
    def test_returns_sequence_then_exog_in_that_order(self):
        from price_forecasting.data.transformers import (
            PastPriceSequenceTransformer,
            DayAheadExogTransformer,
            default_transformers_for_transformer,
        )

        ts = default_transformers_for_transformer(
            exogenous_columns=["load_forecast"], sequence_length_days=7
        )
        assert len(ts) == 2
        assert isinstance(ts[0], PastPriceSequenceTransformer)
        assert ts[0].sequence_length_days == 7
        assert isinstance(ts[1], DayAheadExogTransformer)
        assert ts[1].exogenous_columns == ["load_forecast"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/price_forecasting/test_transformers.py::TestDefaultTransformersForTransformer -v`
Expected: FAIL with `ImportError: cannot import name 'default_transformers_for_transformer'`.

- [ ] **Step 3: Implement the factory**

Append to `src/price_forecasting/src/price_forecasting/data/transformers.py`:

```python
def default_transformers_for_transformer(
    exogenous_columns: list[str], sequence_length_days: int = 14
) -> list[FeatureTransformer]:
    """Feature pipeline for the Llorente & Portela (2025) Transformer EPF model.

    The order is load-bearing: TransformerModel reshapes the wide feature
    matrix by *position*, expecting `sequence_length_days * n_periods`
    past-price columns first, then `len(exogenous_columns) * n_periods`
    day-ahead exogenous columns.
    """
    return [
        PastPriceSequenceTransformer(sequence_length_days=sequence_length_days),
        DayAheadExogTransformer(exogenous_columns=exogenous_columns),
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/price_forecasting/test_transformers.py::TestDefaultTransformersForTransformer -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/price_forecasting/src/price_forecasting/data/transformers.py \
        tests/price_forecasting/test_transformers.py
git commit -m "feat(transformers): add default_transformers_for_transformer factory"
```

---

### Task 4: Implement the `TransformerNetwork` `nn.Module` (TDD)

**Files:**
- Create: `tests/price_forecasting/test_transformer_model.py`
- Create: `src/price_forecasting/src/price_forecasting/models/transformer.py`

- [ ] **Step 1: Write the failing test**

Create `tests/price_forecasting/test_transformer_model.py`:

```python
"""Tests for the Transformer EPF model (Llorente & Portela, 2025)."""

import numpy as np
import pytest
import torch


class TestTransformerNetwork:
    def test_forward_returns_batch_by_n_periods(self):
        from price_forecasting.models.transformer import TransformerNetwork

        torch.manual_seed(0)
        seq_length_days = 7
        n_exog = 2
        n_periods = 24
        embedding_dim = 32
        net = TransformerNetwork(
            seq_length_days=seq_length_days,
            n_exog=n_exog,
            n_periods=n_periods,
            embedding_dim=embedding_dim,
            n_heads=4,
            n_encoder_layers=2,
            ff_dim=64,
            dropout=0.1,
            mlp_hidden=32,
        )
        batch = 5
        n_features = seq_length_days * n_periods + n_exog * n_periods
        x = torch.randn(batch, n_features)
        y = net(x)
        assert y.shape == (batch, n_periods)
        assert torch.isfinite(y).all()

    def test_forward_uses_only_last_position_of_encoder_stack(self):
        """Changing any past-price day *other than* every day at once should still
        change the output (because the encoder mixes positions via attention),
        but changing only the exogenous block must change the output too —
        both flows must contribute. This guards against a bug where one flow
        is silently dropped."""
        from price_forecasting.models.transformer import TransformerNetwork

        torch.manual_seed(0)
        net = TransformerNetwork(
            seq_length_days=4, n_exog=1, n_periods=24,
            embedding_dim=16, n_heads=2, n_encoder_layers=1,
            ff_dim=32, dropout=0.0, mlp_hidden=16,
        )
        net.eval()
        n_features = 4 * 24 + 1 * 24
        x = torch.zeros(1, n_features)
        y0 = net(x).detach().clone()

        # Perturb only the past-price block.
        x_prices = x.clone()
        x_prices[0, : 4 * 24] = torch.randn(4 * 24)
        y_prices = net(x_prices).detach()
        assert not torch.allclose(y_prices, y0)

        # Perturb only the exog block.
        x_exog = x.clone()
        x_exog[0, 4 * 24 :] = torch.randn(1 * 24)
        y_exog = net(x_exog).detach()
        assert not torch.allclose(y_exog, y0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/price_forecasting/test_transformer_model.py::TestTransformerNetwork -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'price_forecasting.models.transformer'`.

- [ ] **Step 3: Implement `TransformerNetwork`**

Create `src/price_forecasting/src/price_forecasting/models/transformer.py`:

```python
"""Pure-Transformer EPF model after Llorente & Portela (2025).

The architecture matches Figure 2 of the paper:

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

from price_forecasting.models.lightning_base import LightningModel


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

        # Learnable positional encoding (one vector per day position).
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
        m, k, n_periods = self.seq_length_days, self.n_exog, self.n_periods

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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/price_forecasting/test_transformer_model.py::TestTransformerNetwork -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/price_forecasting/src/price_forecasting/models/transformer.py \
        tests/price_forecasting/test_transformer_model.py
git commit -m "feat(models): add TransformerNetwork nn.Module (paper Figure 2)"
```

---

### Task 5: Implement `TransformerModel(LightningModel)` wrapper (TDD)

**Files:**
- Modify: `tests/price_forecasting/test_transformer_model.py`
- Modify: `src/price_forecasting/src/price_forecasting/models/transformer.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/price_forecasting/test_transformer_model.py`:

```python
class TestTransformerModel:
    def _make_features_and_targets(
        self, n_samples: int, seq_length_days: int, n_exog: int, n_periods: int = 24
    ):
        rng = np.random.default_rng(0)
        n_features = seq_length_days * n_periods + n_exog * n_periods
        features = rng.normal(size=(n_samples, n_features)).astype(np.float32)
        targets = rng.normal(size=(n_samples, n_periods)).astype(np.float32)
        return features, targets

    def test_fit_then_predict_day_returns_n_periods_vector(self):
        from price_forecasting.models.transformer import TransformerModel

        seq_length_days = 4
        n_exog = 2
        n_periods = 24

        model = TransformerModel(
            seq_length_days=seq_length_days,
            n_exog=n_exog,
            embedding_dim=16,
            n_heads=2,
            n_encoder_layers=1,
            ff_dim=32,
            dropout=0.0,
            mlp_hidden=16,
            epochs=2,
            batch_size=4,
            validation_fraction=0.25,
            early_stopping_patience=100,
            random_seed=0,
        )

        features, targets = self._make_features_and_targets(
            n_samples=32, seq_length_days=seq_length_days, n_exog=n_exog,
            n_periods=n_periods,
        )
        model.fit(features, targets)

        single_day = features[0]
        prediction = model.predict_day(single_day)
        assert prediction.shape == (n_periods,)
        assert np.isfinite(prediction).all()

    def test_rejects_wrong_feature_count(self):
        from price_forecasting.models.transformer import TransformerModel

        model = TransformerModel(
            seq_length_days=4, n_exog=2,
            embedding_dim=16, n_heads=2, n_encoder_layers=1,
            ff_dim=32, dropout=0.0, mlp_hidden=16,
            epochs=1, batch_size=4, validation_fraction=0.25,
        )
        # Off-by-one feature count.
        bad_features = np.zeros((8, 4 * 24 + 2 * 24 + 1), dtype=np.float32)
        bad_targets = np.zeros((8, 24), dtype=np.float32)
        with pytest.raises(ValueError, match="TransformerModel expects"):
            model.fit(bad_features, bad_targets)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/price_forecasting/test_transformer_model.py::TestTransformerModel -v`
Expected: FAIL with `ImportError: cannot import name 'TransformerModel'`.

- [ ] **Step 3: Implement `TransformerModel`**

Append to `src/price_forecasting/src/price_forecasting/models/transformer.py`:

```python
class TransformerModel(LightningModel):
    """Pure-Transformer EPF model wrapper.

    Plugs `TransformerNetwork` into the project's `LightningModel` base, which
    owns the Trainer loop, early stopping, in-memory best-weight restoration,
    and the seed-varied ensemble path used by `LiveRunner`.

    Feature-layout contract: the wide feature vector passed to `fit`/`predict_day`
    must be `[past_prices (seq_length_days · n_periods), exogenous (n_exog · n_periods)]`.
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
                f"({self.seq_length_days} days × {n_periods} periods + "
                f"{self.n_exog} exog × {n_periods} periods), got {n_features}. "
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
        return self.net(x)

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/price_forecasting/test_transformer_model.py::TestTransformerModel -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/price_forecasting/src/price_forecasting/models/transformer.py \
        tests/price_forecasting/test_transformer_model.py
git commit -m "feat(models): add TransformerModel LightningModel wrapper"
```

---

### Task 6: Register in `MODEL_REGISTRY` (TDD)

**Files:**
- Modify: `tests/price_forecasting/test_models.py`
- Modify: `src/price_forecasting/src/price_forecasting/models/__init__.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/price_forecasting/test_models.py` (inside `class TestModelRegistry`):

```python
    def test_get_transformer_model(self):
        from price_forecasting.models.transformer import TransformerModel

        model = get_model(
            "transformer",
            seq_length_days=4,
            n_exog=1,
            embedding_dim=16,
            n_heads=2,
            n_encoder_layers=1,
            ff_dim=32,
            dropout=0.0,
            mlp_hidden=16,
        )
        assert isinstance(model, TransformerModel)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/price_forecasting/test_models.py::TestModelRegistry::test_get_transformer_model -v`
Expected: FAIL with `ValueError: Unknown model: transformer`.

- [ ] **Step 3: Add `TransformerModel` to the registry**

Edit `src/price_forecasting/src/price_forecasting/models/__init__.py`:

```python
from price_forecasting.models.base import BaseModel as BaseModel
from price_forecasting.models.lightning_base import LightningModel as LightningModel
from price_forecasting.models.gbt_base import GBTModel as GBTModel
from price_forecasting.models.sklearn_base import SklearnModel as SklearnModel
from price_forecasting.models.lear import LearModel as LearModel
from price_forecasting.models.dnn import DNNModel as DNNModel
from price_forecasting.models.random_forest import RandomForestModel as RandomForestModel
from price_forecasting.models.xgboost_model import XGBoostModel as XGBoostModel
from price_forecasting.models.transformer import TransformerModel as TransformerModel

__all__ = [
    "BaseModel",
    "LightningModel",
    "GBTModel",
    "SklearnModel",
    "LearModel",
    "DNNModel",
    "RandomForestModel",
    "XGBoostModel",
    "TransformerModel",
    "get_model",
]

MODEL_REGISTRY = {
    "lear": LearModel,
    "dnn": DNNModel,
    "rf": RandomForestModel,
    "xgboost": XGBoostModel,
    "transformer": TransformerModel,
}


def get_model(name: str, **kwargs) -> BaseModel:
    key = name.lower()
    if key not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model: {name}. Available: {list(MODEL_REGISTRY.keys())}"
        )
    return MODEL_REGISTRY[key](**kwargs)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/price_forecasting/test_models.py::TestModelRegistry::test_get_transformer_model -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/price_forecasting/src/price_forecasting/models/__init__.py \
        tests/price_forecasting/test_models.py
git commit -m "feat(models): register TransformerModel in MODEL_REGISTRY"
```

---

### Task 7: End-to-end smoke test via `BacktestEngine` (TDD)

**Files:**
- Modify: `tests/price_forecasting/test_transformer_model.py`

This test wires the new feature transformers, the new model, and the existing `DataPreprocessor` + `BacktestEngine` together and verifies the contract end-to-end on synthetic data — the same idiom as `tests/price_forecasting/test_smoke.py`.

- [ ] **Step 1: Write the failing test**

Append to `tests/price_forecasting/test_transformer_model.py`:

```python
import pandas as pd

from tests.price_forecasting.conftest import make_hourly_dataframe


class TestTransformerSmoke:
    def test_backtest_engine_produces_forecasts(self):
        from price_forecasting.configs.experiment import ExperimentConfig
        from price_forecasting.data.preprocessor import DataPreprocessor
        from price_forecasting.data.transformers import (
            default_transformers_for_transformer,
        )
        from price_forecasting.backtesting.engine import BacktestEngine
        from price_forecasting.models.transformer import TransformerModel

        # Synthetic 200 days of hourly data with two exogenous channels.
        hourly = make_hourly_dataframe(
            n_days=200,
            n_periods=24,
            columns=["price", "load_forecast", "gen_forecast"],
        )

        config = ExperimentConfig(
            experiment_name="smoke_transformer",
            results_dir="results",
            area="DK1",
            model_type="transformer",
            calibration_windows=[120],
            refit_interval_days=7,
            exogenous_curve_types=["load_forecast", "gen_forecast"],
            test_start_date=str(hourly.index[-5 * 24].date()),
            test_end_date=str(hourly.index[-24].date()),
            feature_transformers=default_transformers_for_transformer(
                exogenous_columns=["load_forecast", "gen_forecast"],
                sequence_length_days=7,
            ),
            model_params={
                "seq_length_days": 7,
                "n_exog": 2,
                "embedding_dim": 16,
                "n_heads": 2,
                "n_encoder_layers": 1,
                "ff_dim": 32,
                "dropout": 0.0,
                "mlp_hidden": 16,
                "epochs": 2,
                "batch_size": 8,
                "validation_fraction": 0.2,
                "early_stopping_patience": 100,
                "random_seed": 0,
            },
        )

        preprocessor = DataPreprocessor(config)
        features, targets = preprocessor.build_features(hourly)

        test_dates = pd.to_datetime(targets.index[-3:])

        engine = BacktestEngine(config=config)

        def model_factory():
            return TransformerModel(**config.model_params)

        forecasts, actuals = engine.run(
            model_factory=model_factory,
            features=features,
            targets=targets,
            test_dates=test_dates,
        )

        assert len(forecasts) == 3
        assert forecasts.shape[1] == 24
        assert np.isfinite(forecasts.values).all()
```

> **Note on `preprocessor.build_features`:** if the public helper on
> `DataPreprocessor` is named differently in the current codebase (e.g.
> `preprocess`, `transform`), substitute the correct method name — the
> Task 0 read of `preprocessor.py` is precisely to confirm this. Do *not*
> introduce a new method; reuse whatever LEAR/DNN already calls.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/price_forecasting/test_transformer_model.py::TestTransformerSmoke -v`
Expected: FAIL — either with an import error if helpers are misnamed, or with a runtime error indicating wiring is incomplete.

- [ ] **Step 3: Fix import / method-name discrepancies**

Adjust the test (only) so that it calls the *existing* preprocessor / engine API. Do not change `DataPreprocessor` or `BacktestEngine`. The model and transformers from Tasks 1–6 are the contract under test; the helpers in conftest.py and the engine API are fixed.

- [ ] **Step 4: Re-run until it passes**

Run: `uv run python -m pytest tests/price_forecasting/test_transformer_model.py::TestTransformerSmoke -v`
Expected: PASS. Forecasts should be a 3 × 24 finite-valued DataFrame.

- [ ] **Step 5: Run the full price-forecasting suite to confirm no regressions**

Run: `uv run python -m pytest tests/price_forecasting/ -q`
Expected: all tests pass (existing tests untouched, new tests green).

- [ ] **Step 6: Commit**

```bash
git add tests/price_forecasting/test_transformer_model.py
git commit -m "test(models): end-to-end smoke test for TransformerModel via BacktestEngine"
```

---

### Task 8: Add `configs/dk1_transformer.py` example config

**Files:**
- Create: `configs/dk1_transformer.py`

The config is intentionally *not* added to `FORECAST_CONFIGS` in
`src/schedules/src/schedules/deploy_forecast.py` — the user asked for an
implementation only, no scheduled deployment. The config exists so the
implementation is exercisable via `forecast-cli backtest dk1_transformer`
once historical data has been backfilled.

- [ ] **Step 1: Write the config**

Create `configs/dk1_transformer.py`:

```python
"""DK1 day-ahead forecasting config — pure-Transformer model
(Llorente & Portela, 2025).

NOT a production deployment: this config is not present in
src/schedules/src/schedules/deploy_forecast.py:FORECAST_CONFIGS. It exists so
the Transformer implementation can be exercised via:

    uv run python -m forecast_cli.main backtest dk1_transformer
    uv run python -m forecast_cli.main predict  dk1_transformer -d <YYYY-MM-DD>

Defaults below follow the paper's Nord Pool / EPEX search ranges.
After running `forecast-cli tune dk1_transformer` (if/when a Transformer
search space is added), paste study.best_params into `model_params`.
"""

from price_forecasting.configs.experiment import ExperimentConfig
from price_forecasting.data.transformers import (
    default_transformers_for_transformer,
)

_EXOG = ["TotalLoad", "Generation"]
_SEQ = 14  # m days of past prices (paper search: m ∈ {14, 28})

config = ExperimentConfig(
    experiment_name="dk1_transformer",
    area="DK1",
    model_type="transformer",
    results_dir="results",
    test_start_date="2026-01-01",
    test_end_date="2026-03-22",
    calibration_windows=[1092],
    refit_interval_days=7,
    exogenous_curve_types=_EXOG,
    target_scaler="asinh",
    feature_transformers=default_transformers_for_transformer(
        exogenous_columns=_EXOG, sequence_length_days=_SEQ,
    ),
    model_params={
        "seq_length_days": _SEQ,
        "n_exog": len(_EXOG),
        "embedding_dim": 128,
        "n_heads": 8,
        "n_encoder_layers": 6,
        "ff_dim": 1024,
        "dropout": 0.2,
        "mlp_hidden": 128,
        "gradient_clip_val": None,
        "lr_scheduler_step": 70,
        "lr_scheduler_gamma": 0.1,
        "epochs": 200,
        "batch_size": 32,
        "learning_rate": 1e-4,
        "validation_fraction": 0.16,  # ~ last 42 weeks of a 5-year training set
        "early_stopping_patience": 25,
        "random_seed": 42,
    },
)
```

- [ ] **Step 2: Verify the config loads**

Run:
```bash
uv run python -c "from forecast_cli.config_loader import load_config; \
  c = load_config('dk1_transformer'); print(c.experiment_name, c.model_type)"
```

Expected: `dk1_transformer transformer`. No exception.

- [ ] **Step 3: Commit**

```bash
git add configs/dk1_transformer.py
git commit -m "feat(configs): add dk1_transformer example config (not deployed)"
```

---

### Task 9: Update `CLAUDE.md` model-list snippet

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add a one-line entry under the "Price Forecasting" section**

Find the existing paragraph in `CLAUDE.md` that mentions LEAR / DNN model defaults. Append a single sentence (no new section):

```
- **Transformer model**: `TransformerModel` (Llorente & Portela, 2025) — pure Transformer encoder over the past m daily 24-vectors plus a day-ahead exogenous embedding, concatenated through an MLP. Requires `default_transformers_for_transformer(...)` as the feature pipeline; not registered in `FORECAST_CONFIGS` (run via `forecast-cli backtest dk1_transformer`).
```

Place it next to the LEAR / DNN bullets so future readers see all three models together. Do not edit `docs/REPO_OVERVIEW.md` — it is regenerated against the deployed surface area and the Transformer is not deployed.

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(CLAUDE): note the Transformer EPF model"
```

---

### Task 10: Final verification

**Files:**
- No files modified.

- [ ] **Step 1: Full test suite**

Run: `uv run python -m pytest tests/ -q`
Expected: all tests pass.

- [ ] **Step 2: Lint**

Run: `uv run ruff check src/price_forecasting tests/price_forecasting configs`
Expected: no errors. Fix any that surface (most likely unused-import on the two new transformer classes if you forgot to re-export — check `src/price_forecasting/src/price_forecasting/data/__init__.py` if it re-exports transformer symbols; if it does, add the two new ones there with `X as X` to satisfy `F401`).

- [ ] **Step 3: Smoke run via `forecast-cli` (optional, requires ClickHouse + backfilled data)**

This step is only runnable on a host with a populated ClickHouse. If unavailable, skip it and surface that in the handoff.

```bash
uv run python -m forecast_cli.main backtest dk1_transformer
```

Expected: completes without exception and prints MAE/RMSE/sMAPE/rMAE for the configured test window. The numbers are *not* the paper's numbers — calibration window, training length, and exogenous set are different. The check is that the wiring runs end-to-end on real data.

- [ ] **Step 4: Commit any lint fixes from step 2**

```bash
git add <files-touched-by-ruff-fix>
git commit -m "chore: ruff fixes for Transformer model surface"
```

---

## Out-of-band: dependencies between tasks

- Task 0 must precede every other task.
- Tasks 1, 2, 3 (feature transformers + factory) are independent of Tasks 4, 5 (model code) and can run in parallel under subagent-driven execution.
- Task 6 (registry) requires Task 5 (model exists).
- Task 7 (smoke test) requires Tasks 3, 5, 6 (factory, model, registry).
- Task 8 (config) requires Tasks 3, 6 (factory + registry name `"transformer"`).
- Tasks 9–10 are last.

## What is intentionally *not* in this plan

- **No Prefect deployment**: the model is callable, but the user explicitly excluded scheduling. `FORECAST_CONFIGS` in `deploy_forecast.py` is untouched, and no `daily-forecast-dk1_transformer` deployment will be created.
- **No Optuna search space for Transformer HPs**: the paper's 10-HP grid is not reproduced here. `forecast-cli tune` continues to reject non-DNN configs (per CLAUDE.md). Adding `tuning/transformer_search.py` is a sensible next plan, gated on the implementation here landing first.
- **No W&B project changes**: `LightningModel` already wires `build_lightning_logger(self._config)` automatically, so backtests via `forecast-cli backtest --track` will appear in `algo-research` without any explicit hookup.
- **No `n_dnn_ensemble`-style ensembling for the Transformer**: the paper notes "An Ensemble of Transformers could have been better, but it was out of the scope of this paper." We follow the paper. `LiveRunner` already keys the trained-models dict by `(seed, window_size)` when the config bumps `n_dnn_ensemble`, but exercising that for `"transformer"` would need a separate plan since the seed-ensemble code currently dispatches on `model_type == "dnn"`.

## Self-Review

**Spec coverage** — re-checked against the user request ("implement the model in the paper, no scheduling"):
- *Two-flow architecture (past prices + exog)* → Task 4 (`TransformerNetwork`). Covered.
- *Embedding (Linear + ReLU)* per flow → Task 4 (`price_embedding`, `exog_embedding`). Covered.
- *Positional encoding* → Task 4 (`self.positional_encoding` learnable parameter). Covered.
- *Transformer Encoder stack* (NL blocks, NH heads, FD feed-forward) → Task 4 (`nn.TransformerEncoder`). Covered.
- *Take last position of the encoder output* → Task 4 (`encoded[:, -1, :]`). Covered.
- *MLP over concatenated representations → 24-period prediction* → Task 4 (`self.mlp`). Covered.
- *Adam optimizer* → Task 5 (`configure_optimizers`). Covered.
- *Step LR scheduler (optional)* → Task 5 (`lr_scheduler_step`, `lr_scheduler_gamma`). Covered.
- *Gradient clipping (optional)* → Task 5 (`gradient_clip_val` + `on_before_optimizer_step`). Covered.
- *Trainable via the existing `BacktestEngine` and `LiveRunner` path* → Task 7 smoke test. Covered.
- *Drivable via `forecast-cli backtest/predict`* → Task 8 (`configs/dk1_transformer.py`) + Task 6 (registry). Covered.
- *No scheduling* → No edits to `deploy_forecast.py` anywhere in the plan. Covered.

**Placeholder scan** — searched the plan for "TBD", "TODO", "implement later", "fill in details", "similar to Task N". None present. The one note in Task 7 step 1 about `build_features` is a *contingency* on the existing preprocessor's public method name (Task 0 reads it); the contingency is bounded ("substitute the correct name — do not introduce a new method").

**Type consistency** — checked across tasks:
- `seq_length_days`, `n_exog`, `embedding_dim`, `n_heads`, `n_encoder_layers`, `ff_dim`, `dropout`, `mlp_hidden` are spelled identically in `TransformerNetwork.__init__`, `TransformerModel.__init__`, the smoke test's `model_params`, and the example config.
- Column naming `seq_d{k}_p{p}` and `exog_{col}_p{p}` is used identically across the two transformer tests, the docstrings, and the model's reshape contract (which never *parses* the names — it relies on positional ordering, which is what `default_transformers_for_transformer` guarantees).
- `n_periods` is *always* derived from `targets.shape[1]` at fit time inside `_build_network` (matching the CLAUDE.md invariant), never hardcoded to 24.
