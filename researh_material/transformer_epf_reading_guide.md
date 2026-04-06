# Reading Guide: A Transformer Approach for Electricity Price Forecasting

**Paper:** Llorente & Portela (2025), arXiv:2403.16108v3
**Code:** https://github.com/osllogon/epf-transformers

---

## How to Read This Paper (Recommended Order)

| Priority | Section | Why it matters for you |
|----------|---------|----------------------|
| 1 | Section 2 (Model Architecture) | Core of what you'd implement — the Transformer Encoder structure, dual-input design, embeddings |
| 2 | Section 3.3 (Retraining & Renormalization) | Key design decision: paper trains once + renormalizes, your pipeline retrains daily. Read this to decide your approach |
| 3 | Section 3.2 (Train-Val-Test Split) | Confirms your existing date-based splitting is aligned with EPF best practices |
| 4 | Section 4 (Results) + Tables 2-5 | Benchmark numbers to target — Transformer beats DNN ensemble on 4/5 datasets |
| 5 | Section 3.5 (Statistical Testing) | Diebold-Mariano test — not yet in your codebase, needed for rigorous comparison |
| 6 | Section 3.1 (Datasets) | Context only — paper uses NP/PJM/EPEX datasets, you use ENTSOE DK1 |
| 7 | Appendix Tables 6-10 | Hyperparameter search results — useful reference when tuning your model |

---

## Paper Architecture at a Glance

```
                    +-----------------+
                    |   Exogenous     |   (24-dim: load/wind forecasts for day D+1)
                    |   Variables     |
                    +--------+--------+
                             |
                     Embedding Layer (Linear + ReLU)
                             |
                             v
                        [1 x n] ----+
                                    |
+-----------------+                 |  Concatenate  -->  MLP  -->  24h prices
|   Past Prices   |                 |                   (n+F -> 24)
|   (m x 24)      |                 |
+--------+--------+                 |
         |                          |
  Embedding Layer (Linear + ReLU)   |
         |                          |
  + Positional Encoding             |
         |                          |
  Transformer Encoder Stack         |
  (NL layers, NH heads)             |
         |                          |
  Select last day output [1 x F] ---+
```

**Key idea:** Two separate data flows — exogenous variables get a simple embedding, while price history goes through Transformer Encoders to capture temporal dynamics. Only the last element of the Transformer output sequence is used for the final prediction.

---

## Mapping Paper Concepts to Your Codebase

### Already Implemented

| Paper Concept | Your Implementation | File |
|--------------|-------------------|------|
| Day-ahead 24h prediction | `BaseModel.predict_day() -> np.ndarray` shape (24,) | `models/base.py` |
| LEAR benchmark model | `LearModel` — fully implemented with Lasso per hour | `models/lear.py` |
| DNN benchmark model | `DNNModel` — stub, `fit`/`predict_day` are `pass` | `models/dnn.py` |
| Model registry + factory | `MODEL_REGISTRY`, `get_model(name, **kwargs)` | `models/__init__.py` |
| Exogenous variables (load, generation) | `ExperimentConfig.exogenous_curve_types`, `ExogenousLagTransformer` | `configs/experiment.py`, `data/transformers.py` |
| Feature scaling (StandardScaler) | `DataPreprocessor.transform_data()` — fits on train, applies to test | `data/preprocessor.py` |
| Train/test date-based split | `split_by_dates()` — matches paper's explicit date ranges | `backtesting/splitting.py` |
| Calibration windows + ensemble | `BacktestEngine._ensemble_forecast()` — averages across windows | `backtesting/engine.py` |
| Daily refit logic | `BacktestEngine._fit_and_predict_window()` with `refit_interval_days` | `backtesting/engine.py` |
| MAE, RMSE, sMAPE metrics | `calculate_mae`, `calculate_rmse`, `calculate_smape` | `evaluation/metrics.py` |
| Weekly naive benchmark | `build_weekly_naive()` | `evaluation/summary.py` |
| Per-hour metric breakdown | `compute_metrics_per_hour()` | `evaluation/summary.py` |
| Experiment config with model params | `ExperimentConfig` dataclass | `configs/experiment.py` |
| Data loading from ClickHouse | `load_dataset()`, `load_price_series()`, `load_exogenous_series()` | `data/clickhouse_loader.py` |
| Experiment tracking in ClickHouse | `insert_experiment_run()`, `insert_experiment_predictions()` | `infrastructure_clickhouse/ingest.py` |

> **All file paths above are relative to** `src/price_forecasting/src/price_forecasting/`

### Not Yet Implemented

| Paper Concept | What's Missing | Complexity |
|--------------|---------------|------------|
| **Transformer model** | The core model: Embedding layers, Positional Encoding, Transformer Encoder stack, MLP head | High |
| **Dual-input architecture** | Paper uses two separate input flows (exogenous + price history) — current `BaseModel.fit(features, targets)` expects a single flat feature array | Medium |
| **Renormalization strategy** | Paper subtracts mean/std of recent data at test time instead of retraining — not in your pipeline | Medium |
| **Hyperparameter tuning framework** | Paper tunes: embedding dim, num heads, num layers, FF dim, dropout, sequence length, LR, scheduler, gradient clipping — no automated tuning exists | Medium |
| **Diebold-Mariano test** | Statistical significance test comparing two models' forecasts | Low |
| **Sequence length as input** | Paper feeds raw m-day price history (m x 24 matrix) to Transformer — different from your lag-based FeatureTransformers | Medium |
| **Learning rate scheduler** | StepLR with configurable step/gamma — standard PyTorch, but needs wiring | Low |
| **Gradient clipping** | `torch.nn.utils.clip_grad_norm_` — needs wiring in training loop | Low |

---

## Two Implementation Approaches

You need to decide between adapting the Transformer to your existing pipeline or implementing it faithfully to the paper. Here's the comparison:

### Approach A: Adapt to Existing Pipeline

Fit the Transformer into your current `BacktestEngine` with calibration windows and daily refitting.

**How it works:**
- Implement `TransformerModel(BaseModel)` with `fit(features, targets)` / `predict_day(features)`
- Use your existing `FeatureTransformer` pipeline to create the flat feature matrix (price lags + exogenous lags + calendar dummies)
- The Transformer sees the same features as LEAR — it's just a different model on the same data
- Keeps calibration window ensemble and refit interval

**Pros:**
- Minimal changes to pipeline — just add a new model class
- Direct apples-to-apples comparison with LEAR on your DK1 data
- Reuses all existing infrastructure (DataPreprocessor, BacktestEngine, evaluation)

**Cons:**
- Loses the paper's key insight: the Transformer sees raw temporal sequences, not pre-engineered lag features
- Calibration windows + daily refit is expensive for Transformer training (20 min/train vs 5 min for DNN)
- May not capture the temporal patterns as well since features are already flattened

**Config example:**
```python
ExperimentConfig(
    model_type="transformer",
    model_params={"embedding_dim": 256, "num_heads": 8, "num_layers": 6, "ff_dim": 1024, "dropout": 0.2},
    calibration_windows=[1092, 1456],  # larger windows for Transformer
    refit_interval_days=7,  # refit weekly, not daily
    feature_transformers=[CyclicalTimeTransformer(), MeanWeeklyForecastTransformer(["TotalLoad"])],
)
```

### Approach B: Faithful to Paper

Implement the dual-input architecture with train-once + renormalization.

**How it works:**
- New `TransformerEPFModel` with custom `fit()` that accepts structured inputs (price history matrix + exogenous vector)
- New `TransformerRunner(BaseRunner)` that bypasses `BacktestEngine` — trains once on full training data, evaluates with renormalization
- Renormalization: at each test day, subtract mean/std computed from all data up to that day
- No calibration windows, no daily refit

**Pros:**
- Faithful reproduction — can validate against paper's reported numbers
- Transformer sees raw temporal structure (m days x 24 hours)
- Much faster evaluation (train once vs. train every day)

**Cons:**
- Requires new runner class that doesn't use BacktestEngine
- Can't directly ensemble with LEAR (different pipeline)
- Renormalization logic is new code
- Harder to compare fairly with your LEAR results (different methodology)

**What you'd need:**
1. `TransformerEPFModel` — PyTorch model with dual embedding + encoder stack + MLP
2. `TransformerRunner` — train-once runner with renormalization loop
3. New config fields: `sequence_length`, `embedding_dim`, `num_heads`, etc.

### Recommendation

Start with **Approach A** to get a working Transformer in your pipeline quickly and compare against LEAR. Then explore **Approach B** if you want to reproduce the paper's results or if Approach A underperforms due to the flat feature structure.

---

## Key Paper Hyperparameters (from Appendix Tables 6-10)

| Hyperparameter | Symbol | Best values across datasets | Notes |
|---------------|--------|---------------------------|-------|
| Embedding dimension | n | 64-512 | 256-512 for larger datasets |
| Number of attention heads | NH | 4-8 | 8 most common in best configs |
| Number of encoder layers | NL | 4-6 | 6 for most datasets |
| Feed-forward dimension | FD | 256-2048 | Dataset-dependent |
| Dropout | P | 0.1-0.2 | 0.2 most common |
| Sequence length | SL | 336-672 | 336 = 14 days, 672 = 28 days (in hours) |
| Learning rate | Lr | 1e-5 to 1e-4 | 1e-5 most common best |
| Scheduler | Sch | StepLR(70, 0.1) or None | Step scheduler helps in some cases |
| Gradient clipping | CG | 0.1-0.5 | Prevents exploding gradients |
| Optimizer | Opt | Adam | Always Adam |

---

## Diebold-Mariano Test

### What it is (Section 3.5)
A statistical hypothesis test that determines whether one model's forecasts are **significantly** better than another's — not just numerically better. The paper uses a one-sided DM test with p < 0.05 threshold.

### Why you need it
Your current evaluation (`compute_metrics_summary`) tells you "Transformer MAE = 2.33, LEAR MAE = 2.89" but not whether that difference is statistically meaningful or could be due to chance.

### How to implement it

The DM test compares the loss differential series between two models:

```python
# Concept (would go in evaluation/metrics.py or evaluation/statistical_tests.py)
def diebold_mariano_test(errors_model_a: np.ndarray, errors_model_b: np.ndarray) -> float:
    """
    One-sided DM test. Returns p-value.
    H0: Model A is more accurate than Model B.
    If p < 0.05, Model B is significantly better.
    
    errors = |y_true - y_pred| for each model, flattened across all hours and dates.
    """
    d = errors_model_a - errors_model_b  # loss differential
    # Use Newey-West HAC estimator for autocorrelation-robust variance
    # Or use the epftoolbox implementation as reference
```

The `epftoolbox` library (referenced in the paper) has an implementation you can reference: `epftoolbox.evaluation.DM`.

### Where it fits in your codebase
- Add to `evaluation/metrics.py` or create `evaluation/statistical_tests.py`
- Call from `BacktestRunner` after computing forecasts for two models
- Store results alongside existing metrics in `_metrics.json`

---

## Implementation Roadmap

### Phase 1: Transformer Model (Approach A — fits existing pipeline)

1. **Create `models/transformer.py`** — implement `TransformerModel(BaseModel)`
   - Uses PyTorch (`nn.TransformerEncoder`)
   - `fit(features, targets)`: trains on flat feature matrix like LEAR
   - `predict_day(features)`: returns shape (n_periods,)
   - Training loop with Adam, optional LR scheduler, gradient clipping, early stopping

2. **Register in `models/__init__.py`** — add `"transformer": TransformerModel` to `MODEL_REGISTRY`

3. **Add Transformer-friendly feature transformers** — the paper only uses raw prices + exogenous
   - `CyclicalTimeTransformer` already exists (good for deep models)
   - `MeanWeeklyForecastTransformer` already exists (compressed exogenous)
   - Consider lower-dimensional features vs LEAR's 103+ columns

4. **Create config `configs/dk1_transformer.py`** with appropriate settings

5. **Run backtest**: `uv run python -m forecast_cli.main backtest dk1_transformer`

### Phase 2: Diebold-Mariano Test

1. Implement DM test in `evaluation/`
2. Add CLI command or utility to compare two experiment runs

### Phase 3 (Optional): Faithful Paper Reproduction (Approach B)

1. `TransformerEPFModel` with dual-input architecture
2. `TransformerRunner` with train-once + renormalization
3. New config fields for Transformer-specific hyperparameters

---

## Detailed Section-by-Section Notes

### Section 1 — Introduction (skip or skim)
Standard literature review. The key takeaway: most "Transformer" models in EPF actually combine attention with RNNs/LSTMs. This paper uses a **pure** Transformer Encoder (no recurrence).

### Section 2 — Proposed Model (read carefully)

**Figure 1** (p.3): High-level input/output. Two inputs (exogenous for D+1, past prices), one output (24h prices for D+1). This is the conceptual picture.

**Figure 2a** (p.4): Detailed architecture. Note the two parallel data flows:
- Top flow: exogenous → Embedding → [1 x n]
- Bottom flow: prices (m x 24) → Embedding → + Positional Encoding → Transformer Encoders → select last day → [1 x F]
- Concatenate → MLP → 24h output

**Figure 2b** (p.4): Standard Transformer Encoder block (Multi-Head Attention → LayerNorm → Feed-Forward → LayerNorm). This is `nn.TransformerEncoderLayer` in PyTorch.

**Figure 3** (p.5): Embeddings are just `Linear(24, n) + ReLU`. Not learned token embeddings like in NLP.

**Key dimensions:**
- Exogenous embedding output: [1 x n]
- Price embedding input: [m x 24] → output: [m x n]
- After Transformer stack: [m x F] → take last → [1 x F]
- MLP input: n + F → output: 24

### Section 3.2 — Train-Val-Test Split (skim)
Your `split_by_dates()` already does this. Paper uses last 42 weeks of training for validation (hyperparameter tuning). You could add a `validation_weeks` field to `ExperimentConfig` if needed.

### Section 3.3 — Retraining & Renormalization (read carefully)
**This is the key design decision.** The paper:
- Does NOT retrain daily (too expensive for Transformers: ~20 min/train)
- Instead uses **renormalization**: at test time, subtract mean/std of all past data
- This is different from your `DataPreprocessor.transform_data()` which fits scalers on the training window

If you go with Approach A, your existing `refit_interval_days=7` (weekly) is a reasonable compromise. If Approach B, you need to implement the renormalization step.

### Section 3.4 — Models to Compare (skim)
Benchmarks: DNN ensemble (your `DNNModel` stub) and Naive (your `build_weekly_naive()`). You already have both concepts.

### Section 3.5 — Statistical Testing (read for implementation)
Diebold-Mariano test — see the dedicated section above.

### Section 4 — Results (read for benchmarking targets)

**Table 5** is the key results table:
| Market | Transformer MAE | DNN MAE | Naive MAE |
|--------|----------------|---------|-----------|
| NordPool | 2.33 | 3.40 | 2.89 |
| PJM | 3.67 | 7.17 | 4.43 |
| EPEX-BE | 6.54 | 9.38 | 9.38 |
| EPEX-DE | 4.03 | 4.34 | 8.19 |

The Transformer achieves ~20-50% MAE reduction vs DNN on most datasets. DM test p-values are 0 (highly significant) for 4/5 datasets.

**Figure 4** (p.9): Visual comparison. The Transformer is notably more consistent — fewer extreme misses than DNN or Naive.

### Appendix — Validation Results (reference when tuning)
Tables 6-10 show hyperparameter search results per dataset. Use these as starting points for your DK1 experiments. NordPool (Table 6) is most relevant to your Nordic market data.

---

## Glossary: Paper Terms vs Your Code

| Paper term | Your codebase equivalent |
|-----------|------------------------|
| "Exogenous variables of day D+1" | `exogenous_curve_types` in config, loaded via `load_exogenous_series()` |
| "Past m days prices" | Price lags via `PriceLagTransformer` (Approach A) or raw price matrix (Approach B) |
| "Renormalization" | Closest: `DataPreprocessor.transform_data()` (but not identical — see Section 3.3) |
| "Calibration window" | `ExperimentConfig.calibration_windows` — paper doesn't use this concept |
| "Ensemble" | `BacktestEngine._ensemble_forecast()` — paper doesn't ensemble Transformers |
| "DNN Ensemble" | Your `DNNModel` stub — paper's benchmark, not the proposed model |
| "EPF toolbox" | External library `epftoolbox` — for DM test reference implementation |
| "Sequence length (SL)" | Number of past hours fed to Transformer: 336 = 14 days, 672 = 28 days |
| "Embedding dimension (n)" | `model_params={"embedding_dim": 256}` |
