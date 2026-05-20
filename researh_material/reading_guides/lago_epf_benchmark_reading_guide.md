# Reading Guide: Forecasting Day-Ahead Electricity Prices — Review, Best Practices & Benchmark

**Paper:** Lago, Marcjasz, De Schutter & Weron (2021), Applied Energy 293
**Toolbox:** https://github.com/jeslago/epftoolbox
**This is the foundational paper your codebase is built on.**

---

## How to Read This Paper (Recommended Order)

| Priority | Section | Why it matters |
|----------|---------|---------------|
| 1 | Section 4.1-4.2 (LEAR model + input features) | This is what your `LearModel` implements — verify you match the spec |
| 2 | Section 5.4-5.5 (Metrics + Statistical testing) | Your evaluation module is based on this — check completeness |
| 3 | Section 4.4 (Ensembles) | Your `BacktestEngine._ensemble_forecast()` implements this pattern |
| 4 | Section 5.6-5.7 (Recalibration + hyperparameters) | Your `refit_interval_days` and `LassoCV` are based on these guidelines |
| 5 | Section 7 (Checklist) | 13-point checklist — grade yourself against it |
| 6 | Section 6 (Results, Tables 2-4) | Benchmark numbers and statistical test visualizations |
| 7 | Section 4.3 (DNN model) | Reference for implementing your `DNNModel` stub |
| 8 | Sections 2-3 (Literature review + datasets) | Context and dataset descriptions — skim |
| 9 | Section 5.1-5.3, 5.8-5.12 (Other guidelines) | Test period length, open-access, computation time, reproducibility |

---

## The Paper's 13-Point Checklist vs Your Codebase

This is the paper's Section 7 checklist — the gold standard for rigorous EPF research. Here's how you score:

| # | Requirement | Your Status | Details |
|---|------------|-------------|---------|
| 1 | Test dataset >= 1 year | **PASS** | `ExperimentConfig.test_start_date/test_end_date` supports arbitrary ranges; your configs use multi-month periods |
| 2 | Test against state-of-the-art open-access models | **PARTIAL** | You have LEAR (the paper's recommended benchmark). DNN is a stub. No comparison against epftoolbox models directly |
| 3 | Computational cost evaluated | **FAIL** | No timing tracked. `BacktestEngine` doesn't log computation time per day/window |
| 4 | Datasets are open-access | **PASS** | ENTSOE data is freely available; your pipeline fetches from the public API |
| 5 | Multiple markets tested | **FAIL** | Only DK1 configured. Infrastructure supports other areas but no configs exist for DE, FR, etc. |
| 6 | rMAE is used as metric | **PASS** | `calculate_rmae()` in `metrics.py`, `build_weekly_naive()` in `summary.py`, included in `compute_metrics_summary()` |
| 7 | Statistical testing for significance | **FAIL** | No Diebold-Mariano or Giacomini-White test implemented |
| 8 | Models recalibrated daily | **PASS** | `BacktestEngine` supports `refit_interval_days=1` for daily recalibration |
| 9 | Hyperparameters estimated ex-ante (validation set) | **PARTIAL** | `LassoCV` with `TimeSeriesSplit` does ex-ante CV. But no separate validation set split; `SplitResult.validation` is empty when using `split_by_dates()` |
| 10 | Dataset split dates explicitly stated | **PASS** | `test_start_date`/`test_end_date` in `ExperimentConfig`; training = everything before test_start |
| 11 | All model inputs explicitly defined | **PASS** | `ExperimentConfig.exogenous_curve_types` + `FeatureTransformer` pipeline documents all inputs |
| 12 | No data contamination | **PASS** | `split_by_dates()` ensures chronological split; `BacktestEngine._slice_data()` uses only past data for training |
| 13 | State-of-the-art free toolboxes | **PASS** | scikit-learn for LEAR, Polars/Pandas for data, ClickHouse for storage |

### Score: 8 PASS, 2 PARTIAL, 3 FAIL out of 13

---

## Deep Comparison: Paper's LEAR Specification vs Your Implementation

### Input Features

The paper defines exactly 247 input features per hour (Section 4.1, Equation 3):

| Feature Group | Paper Spec | Your Implementation | Match? |
|--------------|-----------|-------------------|--------|
| Price lags: D-1, D-2, D-3, D-7 (4 x 24 = 96) | `p_{d-1,h}, p_{d-2,h}, p_{d-3,h}, p_{d-7,h}` for each of 24 hours | `PriceLagTransformer(lags=[1, 2, 3, 7])` → 4 x n_periods columns | **MATCH** |
| Exogenous day D+1 forecasts (2 x 24 = 48) | `X1_d, X2_d` for 24 hours | `ExogenousLagTransformer` with `d0` lag (shift=0) | **MATCH** |
| Exogenous D-1 lags (2 x 24 = 48) | `X1_{d-1}, X2_{d-1}` for 24 hours | `ExogenousLagTransformer` with `d1` lag (shift=1) | **MATCH** |
| Exogenous D-7 lags (2 x 24 = 48) | `X1_{d-7}, X2_{d-7}` for 24 hours | `ExogenousLagTransformer` with `d7` lag (shift=7) | **MATCH** |
| Day-of-week dummies (7) | Binary vector `[d1,...,d7]` | `CalendarDummyTransformer` → 7 one-hot columns | **MATCH** |
| **Total** | **247** | **4x24 + 3x2x24 + 7 = 247** (with 2 exogenous) | **MATCH** |

Your `default_transformers_for_model()` returns `[PriceLagTransformer, ExogenousLagTransformer, CalendarDummyTransformer]` — this is bit-identical to the paper's LEAR spec.

### Model Architecture

| Aspect | Paper Spec | Your Implementation | Match? |
|--------|-----------|-------------------|--------|
| One Lasso per hour (24 models) | Univariate: separate model for each `h` | `LearModel.hourly_models: Dict[int, Lasso]` — one per period | **MATCH** |
| LASSO regularization | L1 penalty with tunable `lambda` | `sklearn.linear_model.Lasso` or `LassoCV` | **MATCH** |
| Lambda selection | LARS + AIC (hybrid approach, Section 4.2.2) | `LassoCV` with `TimeSeriesSplit` (cross-validation approach) | **DIFFERENT** — paper uses LARS+AIC, you use CV. Both valid; CV is more standard |
| Variance stabilizing transform (asinh) | `asinh(price)` preprocessing (Section 4.2, Eq. 2) | `StandardScaler` in `DataPreprocessor` | **DIFFERENT** — paper uses asinh, you use z-score standardization |

### Calibration Windows & Ensemble

| Aspect | Paper Spec | Your Implementation | Match? |
|--------|-----------|-------------------|--------|
| Window sizes | 56, 84, 1092, 1456 days (8w, 12w, 3y, 4y) | `ExperimentConfig.calibration_windows` default: `[56, 84, 1092, 1456]` | **MATCH** |
| Ensemble method | Arithmetic average of forecasts across windows | `BacktestEngine._ensemble_forecast()` → `np.mean(window_forecasts)` | **MATCH** |
| Daily recalibration | Retrain model every day with new data | `refit_interval_days=1` in `BacktestEngine` | **MATCH** |

### Evaluation Metrics

| Metric | Paper Spec | Your Implementation | Match? |
|--------|-----------|-------------------|--------|
| MAE | `(1/24Nd) * sum(|p - p_hat|)` | `calculate_mae()` — `np.mean(np.abs(y_true - y_pred))` | **MATCH** |
| RMSE | `sqrt((1/24Nd) * sum((p - p_hat)^2))` | `calculate_rmse()` | **MATCH** |
| sMAPE | `(1/24Nd) * sum(2|p - p_hat|/(|p| + |p_hat|))` | `calculate_smape()` — formula uses `/ 2` in denominator, paper uses `2*` in numerator | **CHECK** — verify formula equivalence |
| MAPE | `(1/24Nd) * sum(|p - p_hat|/|p|)` | `calculate_mape()` | **MATCH** (but paper warns MAPE is unreliable) |
| rMAE | `MAE / MAE_naive` with naive = 7-day shift | `calculate_rmae()` + `build_weekly_naive()` | **MATCH** |
| DM test | Diebold-Mariano with loss differentials | Not implemented | **MISSING** |
| GW test | Giacomini-White conditional predictive ability | Not implemented | **MISSING** |

---

## What the Paper Recommends vs What You Have

### Metric Hierarchy (Section 6.4.2)

The paper establishes this reliability ranking:

| Rank | Metric | Paper's Verdict | Your Status |
|------|--------|----------------|-------------|
| 1 | **rMAE** | Best metric — always use it, enables cross-market comparison | **Implemented** and computed in `compute_metrics_summary()` |
| 2 | **MAE** | Reliable, agrees with rMAE, but can't compare across markets | **Implemented** |
| 3 | **sMAPE** | More reliable than MAPE, agrees with MAE/rMAE, but has undefined mean/infinite variance | **Implemented** |
| 4 | **RMSE** | More reliable than MAPE but doesn't represent EPF risks correctly (costs are linear, not quadratic) | **Implemented** |
| 5 | **MAPE** | **Unreliable** — dominated by near-zero prices, leads to wrong conclusions | **Implemented** but should be deprecated or flagged with a warning |

### Key Paper Findings That Affect Your Design

1. **DNN ensemble is the best model** (Table 3) — beats LEAR ensemble in all 5 markets on rMAE. Your `DNNModel` is still a stub.

2. **LEAR is the best low-compute model** — 1-10 seconds per daily recalibration vs 2-5 minutes for DNN (Table 4). Your LEAR implementation is the right first choice.

3. **Ensembles always help** — LEAR ensemble beats best individual LEAR in all markets. Your `BacktestEngine._ensemble_forecast()` correctly implements this.

4. **Short + long calibration windows together** — [56, 84, 1092, 1456] works best. Your default config matches exactly.

5. **MAPE is misleading** — German market MAPE is 10x higher than sMAPE due to near-zero prices. Consider removing MAPE from your default output or at least flagging it.

6. **Statistical testing is essential** — The paper shows that even when DNN has better MAE, the difference isn't always significant (e.g., NP market DNN ensemble vs LEAR ensemble). Without DM/GW tests, you can't make strong claims.

---

## Paper's DNN Specification (for implementing your stub)

From Section 4.3, the paper's DNN has:

| Component | Specification |
|-----------|--------------|
| Architecture | 4-layer feedforward (input → hidden1 → hidden2 → output) |
| Framework | Multivariate — single model, 24 outputs |
| Output | 24 hourly prices |
| Optimizer | Adam |
| Hyperparameter tuning | Tree Parzen Estimator (Bayesian optimization), 1500 iterations |
| Feature selection | 11 binary hyperparameters selecting groups of 24 features each |
| Calibration window | Fixed 4 years |
| Daily recalibration | Yes (weights retrained daily) |
| Validation | 42 weeks, randomly shuffled during testing (not last 42 weeks) |
| Early stopping | On validation set |
| Tunable hyperparameters | Neurons/layer, activation function, dropout rate, learning rate, batch normalization, preprocessing, weight initialization, L1 regularization |
| Ensemble | 4 DNNs with different random seeds → arithmetic average |

This is more complex than a simple `nn.Linear` stack — it requires Bayesian hyperparameter optimization via something like `optuna` or `hyperopt`.

---

## What's Missing: Gap Analysis

### Critical Gaps (blocking rigorous evaluation)

| Gap | Paper Section | Impact | Effort |
|-----|-------------|--------|--------|
| **No DM/GW statistical tests** | 5.5 | Can't claim significance of LEAR vs Transformer results | Low — ~50 lines of code |
| **No DNN implementation** | 4.3 | Can't benchmark against the paper's DL baseline | High — needs PyTorch + Bayesian HP tuning |
| **No computation time tracking** | 5.8 | Can't evaluate if new models are worth the compute cost | Low — add timing to `BacktestEngine.run()` |
| **No asinh variance stabilizing transform** | 4.2 | Your z-score scaling may underperform on markets with spikes/negative prices | Medium — add as preprocessing option |

### Moderate Gaps (improve rigor)

| Gap | Paper Section | Impact | Effort |
|-----|-------------|--------|--------|
| **Single market only (DK1)** | 5.1, checklist #5 | Results can't be generalized | Low — add configs for DE, FR, BE |
| **No MAPE deprecation warning** | 6.4.2 | Users might rely on misleading metric | Low — add warning in output |
| **No validation set for HP tuning** | 5.7 | `split_by_dates()` returns empty validation; LassoCV does internal CV which is fine, but DNN will need explicit validation | Medium — add validation split logic |
| **No LARS+AIC for lambda selection** | 4.2.2 | Your `LassoCV` is valid but slower than the paper's LARS approach | Low — optional optimization |

### Nice-to-Have

| Gap | Paper Section | Impact | Effort |
|-----|-------------|--------|--------|
| Asinh transform as preprocessing option | 4.2 | Better handling of spikes and negative prices | Medium |
| Giacomini-White test (in addition to DM) | 5.5.2 | More robust than DM for rolling windows | Medium |
| Per-hour DM test (univariate variant) | 5.5.1 | Shows which hours have significant differences | Low |
| Long-term seasonal decomposition | 4.2 | Paper mentions it helps but leaves for future work | Medium |

---

## Benchmark Numbers to Target

### Individual LEAR models (Table 2) — your direct comparison point

| Market | Window | rMAE | MAE | sMAPE |
|--------|--------|------|-----|-------|
| NordPool | 56 days | 0.475 | 1.964 | 5.66% |
| NordPool | 84 days | 0.472 | 1.952 | 5.62% |
| NordPool | 1092 days | 0.482 | 1.993 | 5.64% |
| NordPool | 1456 days | 0.481 | 1.990 | 5.66% |

### LEAR ensemble (Table 3) — your ensemble comparison point

| Market | rMAE | MAE | sMAPE |
|--------|------|-----|-------|
| NordPool | 0.420 | 1.738 | 5.01% |
| PJM | 0.476 | 3.013 | 11.98% |
| EPEX-BE | 0.604 | 6.140 | 14.55% |
| EPEX-FR | 0.543 | 3.980 | 11.57% |
| EPEX-DE | 0.433 | 3.955 | 15.75% |

### DNN ensemble (Table 3) — your target to beat

| Market | rMAE | MAE | sMAPE |
|--------|------|-----|-------|
| NordPool | 0.407 | 1.683 | 4.88% |
| PJM | 0.452 | 2.862 | 11.33% |
| EPEX-BE | 0.578 | 5.870 | 13.45% |
| EPEX-FR | 0.527 | 3.866 | 10.81% |
| EPEX-DE | 0.374 | 3.413 | 14.08% |

### Computation time (Table 4)

| Model | Time per daily recalibration |
|-------|------------------------------|
| LEAR (single) | 1-10 seconds |
| LEAR ensemble | 20-25 seconds |
| DNN (single) | 2-5 minutes |
| DNN ensemble | 8-20 minutes |

---

## Section-by-Section Reading Notes

### Section 1 — Introduction
Establishes the three problems in EPF: (1) contradictory comparisons, (2) short test periods, (3) lack of reproducibility. Your codebase addresses all three to varying degrees.

### Section 2 — Literature Review (skim)
Three model families: statistical (LEAR), deep learning (DNN), hybrid. Key insight: the most accurate known models are LEAR (statistical) and DNN (deep learning). Hybrid models are complex but unproven.

### Section 3 — Datasets (skim)
Five markets, 6 years each, 2 exogenous variables per market. Your DK1 data from ENTSOE is analogous to their NordPool dataset (both Nordic markets). Test periods are 2 years (104 weeks).

### Section 4.1 — Input Features (read carefully)
Defines the exact 247 features. **Your `default_transformers_for_model()` reproduces this exactly.** This is the core of why your LEAR implementation should produce comparable results to the paper.

### Section 4.2 — LEAR Model (read carefully)
Key details:
- Equation 3 is the full model specification — 247 parameters per hour
- LASSO sets many to zero (implicit feature selection)
- **Asinh variance stabilizing transform** (Equation 2) — you use StandardScaler instead
- **LARS + AIC** for lambda selection — you use `LassoCV` instead
- Calibration windows: 56, 84, 1092, 1456 days — matches your default

### Section 4.3 — DNN Model (read for future implementation)
More complex than a simple MLP. Key: Tree Parzen Estimator for joint hyperparameter + feature selection (1500 iterations). 42-week validation set. Daily recalibration with 4-year window.

### Section 4.4 — Ensembles (read)
LEAR ensemble = arithmetic average across 4 windows. DNN ensemble = average of 4 runs with different random seeds. **Your `BacktestEngine._ensemble_forecast()` matches the LEAR ensemble spec.**

### Section 5 — Guidelines (read Sections 5.4-5.7 carefully)
The 12 guidelines. Most critical for you:
- **5.4**: Use rMAE. Avoid MAPE. sMAPE is OK but inferior to rMAE.
- **5.5**: DM test is essential. Both univariate (per-hour) and multivariate (daily) variants recommended.
- **5.6**: Daily recalibration is mandatory for realistic evaluation.
- **5.7**: Hyperparameters must be estimated ex-ante (never on test data).

### Section 6 — Results (read Tables 2-4)
Key findings:
- DNN ensemble is best overall (rMAE)
- LEAR is best for low-compute applications (50-100x faster than DNN)
- Ensembles always help
- MAPE is unreliable (especially for German market)
- DNN ensemble significantly outperforms all others in 4/5 markets (GW test)

### Section 7 — Checklist (read and grade yourself)
13 requirements — see the scorecard above. You score 8/13 PASS.

---

## Glossary: Paper Terms vs Your Code

| Paper Term | Your Codebase |
|-----------|--------------|
| LEAR model | `LearModel` in `models/lear.py` |
| DNN model | `DNNModel` (stub) in `models/dnn.py` |
| Calibration window | `ExperimentConfig.calibration_windows` |
| Daily recalibration | `BacktestEngine` with `refit_interval_days=1` |
| Ensemble (arithmetic avg) | `BacktestEngine._ensemble_forecast()` → `np.mean()` |
| Input features (247) | `default_transformers_for_model()` output |
| fARX / LassoX | Same as LEAR — older names for the same model |
| asinh transform | Not implemented — you use `StandardScaler` |
| LARS + AIC | Not implemented — you use `LassoCV` with `TimeSeriesSplit` |
| Tree Parzen Estimator | Not implemented — needed for DNN hyperparameter tuning |
| epftoolbox | External library — reference implementation for metrics and DM test |
| rMAE with naive_2 | `calculate_rmae()` + `build_weekly_naive()` (7-day shift) |
| GW test | Not implemented |
| DM test | Not implemented |

---

## Overall Assessment: How Well Are You Doing?

### What you got right (strong alignment with the paper)

1. **LEAR feature specification** — Your `PriceLagTransformer([1,2,3,7])` + `ExogenousLagTransformer` + `CalendarDummyTransformer` exactly matches the paper's 247-feature LEAR input spec. This is the most important thing to get right.

2. **Calibration window ensemble** — Your `BacktestEngine._ensemble_forecast()` with default windows `[56, 84, 1092, 1456]` is an exact reproduction of the paper's LEAR ensemble method.

3. **Daily recalibration** — `refit_interval_days=1` matches the paper's recommendation for realistic evaluation.

4. **rMAE as primary metric** — You compute rMAE with a weekly naive baseline, exactly as the paper recommends (Section 5.4.2).

5. **No data contamination** — Your chronological `split_by_dates()` and `BacktestEngine._slice_data()` correctly prevent look-ahead bias.

6. **Reproducible configs** — `ExperimentConfig` with explicit dates, git-tracked config files, and ClickHouse experiment tracking satisfy the paper's reproducibility requirements.

7. **Open-access data** — ENTSOE public API as your data source.

### Where you diverge (acceptable differences)

1. **StandardScaler vs asinh transform** — The paper uses asinh (Equation 2) which handles spikes and negative prices better. Your StandardScaler is simpler but may underperform on volatile markets. Consider adding asinh as an option.

2. **LassoCV vs LARS+AIC** — Your cross-validation approach is more standard and well-understood. The paper's LARS+AIC is faster but the accuracy difference is small.

3. **Single market (DK1)** — Paper insists on multiple markets. Easy to fix: add configs for DE, FR.

### Where you fall short (needs work)

1. **No statistical testing** — This is the paper's strongest recommendation. Without DM/GW tests, you can't claim your Transformer is significantly better than LEAR. Priority: implement DM test.

2. **No DNN baseline** — The paper's DNN is the target to beat. Your stub means you can only compare against LEAR, which the paper considers the low-compute baseline.

3. **No computation time tracking** — The paper emphasizes that a model is only "better" if its accuracy gain justifies its compute cost. Add timing to `BacktestEngine.run()`.

4. **MAPE still in default output** — The paper explicitly warns against MAPE. Consider removing it from `compute_metrics_summary()` or adding a deprecation note.

### Maturity Score

Using the paper's 13-point checklist: **8/13 PASS (62%)**

The 3 fails (computation time, multiple markets, statistical testing) are all fixable with moderate effort. The 2 partials (DNN benchmark, validation set) require more work. Overall, your codebase is well-aligned with the paper's recommendations for the LEAR baseline — the main gaps are in evaluation rigor and model diversity.
