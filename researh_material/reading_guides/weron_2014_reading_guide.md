# Reading Guide: Electricity Price Forecasting — A Review of the State-of-the-Art with a Look into the Future

**Paper:** Weron (2014), International Journal of Forecasting 30, pp. 1030-1081
**Scope:** 52-page comprehensive review of EPF methods (2000-2014), 497+ papers surveyed
**Role:** This is THE foundational reference paper for your entire project. Lago et al. (2021) and Llorente & Portela (2025) both build directly on this work.

---

## How to Read This Paper (Recommended Order)

This is a 52-page review — don't read it cover to cover. Use it as a reference.

| Priority | Section | Pages | Why it matters |
|----------|---------|-------|---------------|
| 1 | 3.3 — Evaluating Point Forecasts | 1038-1039 | Defines MAE, MAPE, MASE, RMSE — the metrics your evaluation module implements |
| 2 | 3.8.2-3.8.4 — Regression & AR/ARX Models | 1050-1054 | Theoretical foundation of your LEAR model (parameter-rich ARX with LASSO) |
| 3 | 4.5 — The Need for an EPF Competition | 1073-1075 | Guidelines that Lago et al. (2021) later formalized — the genesis of your approach |
| 4 | 4.3 — Combining Forecasts | 1067-1071 | Theory behind your calibration window ensemble |
| 5 | 4.1 — Fundamental Price Drivers | 1061-1065 | Which input variables matter — validates your exogenous variable choices |
| 6 | 3.9 — Computational Intelligence Models | 1056-1060 | Neural networks for EPF — context for your DNN/Transformer work |
| 7 | 3.4 — Overview of Modeling Approaches (Fig. 6) | 1039-1040 | Taxonomy of ALL EPF methods — see where your models fit |
| 8 | 4.2 — Beyond Point Forecasts | 1065-1067 | Interval and density forecasts — future direction for your project |
| 9 | 4.4 — Multivariate Factor Models | 1071-1073 | Advanced approach relevant to your multi-curve data |
| 10 | Sections 2, 3.1, 3.5-3.7 | Various | Skim for context: bibliometrics, market mechanics, multi-agent/fundamental/reduced-form models |

---

## The Five Model Families (Section 3.4, Figure 6)

Weron classifies all EPF approaches into five families. Your codebase implements methods from family 4 (statistical) with elements from family 5 (CI):

| Family | Description | Your Relevance |
|--------|------------|---------------|
| 1. **Multi-agent models** | Simulate market participants, game theory, supply/demand equilibrium | Not relevant — you forecast prices, not simulate markets |
| 2. **Fundamental models** | Model physical/economic relationships (supply curves, fuel costs, weather) | Partially relevant — your exogenous variables (TotalLoad, Wind/Solar) are fundamental drivers |
| 3. **Reduced-form models** | Stochastic processes (jump-diffusion, regime-switching) for derivatives pricing | Not directly used — but regime-switching concepts inform spike handling |
| 4. **Statistical models** | Regression, AR/ARX time series, LASSO regularization | **Your LEAR model lives here** — parameter-rich ARX estimated with LASSO |
| 5. **Computational intelligence** | Neural networks, SVMs, fuzzy systems | **Your DNN/Transformer models live here** |

---

## Key Concepts Mapped to Your Codebase

### Metrics (Section 3.3)

| Paper Concept | Formula | Your Implementation | Notes |
|--------------|---------|-------------------|-------|
| MAE | `(1/T) * sum(|P - P_hat|)` | `calculate_mae()` in `evaluation/metrics.py` | Paper's preferred L1 metric |
| RMSE | `sqrt((1/T) * sum((P - P_hat)^2))` | `calculate_rmse()` | Paper notes L2 norms are less suitable for EPF |
| MAPE | `(1/T) * sum(|P - P_hat|/|P|)` | `calculate_mape()` | **Paper warns against MAPE** — misleading when prices near zero (Sec 3.3) |
| MASE (scaled error) | MAE / in-sample naive MAE | Not implemented | Weron advocates this; Lago et al. later proposed rMAE as better alternative |
| WMAE/DMAE | MAE / mean price | Not implemented | Weighted MAE normalized by average price |
| rMAE | MAE / out-of-sample naive MAE | `calculate_rmae()` | Lago et al.'s refinement of Weron's MASE recommendation |

**Key insight from the paper:** "There is no industry standard, and the error benchmarks used in the literature vary a lot... this may lead to confusion, since the names are not used consistently." Your codebase avoids this confusion by implementing the specific metrics Lago et al. (2021) later standardized.

### Statistical Models — The LEAR Foundation (Sections 3.8.2-3.8.4)

The paper describes the evolution of regression models for EPF that culminated in your LEAR model:

| Evolution Stage | Description | Your Implementation |
|----------------|------------|-------------------|
| Simple AR models | `P_{d,h} = f(P_{d-1,h}, P_{d-2,h}, P_{d-7,h})` | Captured by `PriceLagTransformer(lags=[1,2,3,7])` |
| ARX models | Add exogenous variables (load forecasts, generation) | `ExogenousLagTransformer` |
| Seasonal dummies | Day-of-week encoding | `CalendarDummyTransformer` |
| Parameter-rich models | Dozens/hundreds of regressors | Your 247-feature LEAR input |
| LASSO regularization | L1 penalty for automatic feature selection | `LearModel` using `sklearn.linear_model.Lasso` |
| Multi-model per hour | Separate model for each hour (24 models) | `LearModel.hourly_models: Dict[int, Lasso]` — one per period |

**Paper quote (Section 3.8.4):** "Recently, parameter-rich autoregressive models with exogenous variables, estimated using LASSO... have been shown to improve the forecasting results." This is exactly what your LEAR implements.

### Univariate vs Multivariate (Section 3.8.2)

Weron discusses a key design decision:
- **Univariate (24 separate models):** One model per hour. "Most EPF papers follow the tradition of load forecasting and use separate models for each hour."
- **Multivariate (single model, 24 outputs):** One model predicting all hours simultaneously.

Your LEAR follows the **univariate** approach (one Lasso per hour), which the paper notes is "marginally more accurate" for statistical models. Your planned DNN/Transformer would follow the **multivariate** approach (single model, 24 outputs), which is standard for neural networks.

### Combining Forecasts / Ensembles (Section 4.3)

Weron identifies forecast combination as a "forgotten art" in EPF and strongly advocates for it:

> "One of the key findings of the forecasting literature is that combining forecasts leads to improved forecast accuracy... This result has been confirmed by many studies across a wide range of areas."

Key points from the paper:

| Concept | Paper's Discussion | Your Implementation |
|---------|-------------------|-------------------|
| Calibration window ensemble | "Combining forecasts from models calibrated on different windows" — short windows adapt to changes, long windows have more data | `BacktestEngine._ensemble_forecast()` with windows [56, 84, 1092, 1456] |
| Simple average | "The arithmetic average is hard to beat" | `np.mean(window_forecasts)` — exactly this |
| Diverse forecasts | "Using different data or different models" | Different calibration windows = different training data |
| Optimal ensemble size | "4-10 models" — larger ensembles risk including outliers | 4 calibration windows = 4 models |

**Your ensemble is exactly what the paper recommends.** Short windows (56, 84 days) + long windows (1092, 1456 days) combined with arithmetic average.

### Neural Networks for EPF (Section 3.9)

Weron's assessment in 2014:

| Finding | Status in 2026 |
|---------|---------------|
| "Feed-forward NNs are the most popular CI tool for EPF" | Still true — your DNN stub is a feedforward network |
| "No sound evidence that NNs consistently outperform statistical models" | Lago et al. (2021) later showed DNN ensemble beats LEAR ensemble |
| "The pool of available CI tools is so diverse and rich that it is hard to find an optimal solution" | Still true — hence the Transformer paper exploring new architectures |
| "CI tools should provide better interval and density forecasts... not investigated extensively" | Still largely unexplored — probabilistic forecasting remains a gap |

### Input Variable Selection (Section 4.1)

The paper emphasizes that choosing the right inputs is critical:

| Driver | Paper's Assessment | Your Data |
|--------|-------------------|-----------|
| **System loads/demand** | "Fundamental driver" — always relevant | `TotalLoad` via ENTSOE — **included** |
| **Weather (temperature)** | Important for demand-driven markets | Not directly included — captured indirectly through load forecasts |
| **Wind/solar generation** | Increasingly important with renewables | `WindSolar` via ENTSOE — **included** |
| **Fuel costs (gas, oil)** | Important for thermal-dominant markets | Not included — DK1 is wind-heavy, less fuel-dependent |
| **Reserve margin** | "Huge potential for explaining spike probability" | Not included — could improve spike forecasting |
| **Day-of-week** | Standard seasonal feature | `CalendarDummyTransformer` — **included** |
| **Price lags (d-1, d-2, d-3, d-7)** | Core autoregressive structure | `PriceLagTransformer([1,2,3,7])` — **included** |

### The Seasonality Problem (Section 4.1.1)

Weron devotes significant attention to seasonal decomposition:

| Seasonality | Period | How Addressed in Your Code |
|------------|--------|--------------------------|
| **Daily** (hourly pattern) | 24 hours | Handled by separate model per hour (LEAR) or 24-output multivariate model (DNN) |
| **Weekly** (weekday/weekend) | 7 days | `CalendarDummyTransformer` (day-of-week one-hot) |
| **Annual** (summer/winter) | ~365 days | `CyclicalTimeTransformer` (sin/cos of day-of-year) — available but not in LEAR defaults |
| **Long-term trend** | Years | Not addressed — paper warns this can cause "critical flaw" for longer predictions |

**Paper's key warning:** "The issue of seasonality has been downplayed in the EPF literature. This is a serious shortcoming." Your LEAR handles daily and weekly well but lacks explicit annual seasonality modeling (the `CyclicalTimeTransformer` exists but isn't in the default pipeline).

---

## Section 4.5 — The EPF Competition Call (The Genesis of Your Approach)

This is arguably the most important section for your project. Weron calls for:

1. **A universal test ground** — common datasets, same test periods, same metrics
2. **Open-source benchmark methods** — reproducible, well-documented
3. **Statistical testing of significance** — not just "my MAE is lower"

> "The development of a commonly agreed upon set of benchmarks should be a priority for the EPF community."

**This call was answered by Lago et al. (2021)**, who created:
- The `epftoolbox` with 5 datasets, LEAR and DNN implementations
- The rMAE metric (improving on Weron's MASE recommendation)
- Integration of DM and GW statistical tests

**Your codebase is a direct descendant of this lineage:** Weron (2014) → Lago et al. (2021) → your implementation.

### Weron's Evaluation Guidelines (Section 4.5.2)

| Guideline | Your Status |
|-----------|-------------|
| "Test datasets should span at least a year" | **PASS** — configurable via `test_start_date/test_end_date` |
| "Compare with well-established benchmark models" | **PARTIAL** — LEAR implemented, DNN is stub |
| "Use same datasets for fair comparison" | **PASS** — all models run on same ClickHouse data |
| "Report MASE or scaled errors" | **PASS** — you use rMAE (Lago's refinement) |
| "Statistical testing of significance differences" | **FAIL** — no DM/GW tests |
| "Specify exact train/test split" | **PASS** — explicit dates in `ExperimentConfig` |
| "Recalibrate models with new data" | **PASS** — daily recalibration in `BacktestEngine` |
| "Multiple markets" | **FAIL** — only DK1 |

---

## Future Directions the Paper Predicted (Section 4) — What Happened Since

| 2014 Prediction | Did it happen? | Your Position |
|----------------|---------------|---------------|
| "Forecast combination will become more popular" | **Yes** — now standard (Lago et al. use it) | Implemented: calibration window ensemble |
| "Probabilistic forecasting will grow" | **Partially** — still underexplored | Not implemented — point forecasts only |
| "Reserve margin will play a significant role" | **Limited** — data availability remains an issue | Not included |
| "Multivariate factor models will be explored" | **Yes** — Transformer attention is related | Planned: Transformer model |
| "Neural networks need rigorous comparison with statistical models" | **Yes** — Lago et al. (2021) did this definitively | Your LEAR is the statistical baseline; DNN/Transformer are the CI comparisons |
| "An EPF competition/benchmark is needed" | **Yes** — epftoolbox was created | Your codebase implements the Lago et al. framework |
| "Seasonality handling needs improvement" | **Still true** — often neglected | Your `CyclicalTimeTransformer` exists but isn't default |

---

## Glossary: Paper Terms vs Your Code

| Weron's Term | Modern Equivalent | Your Implementation |
|-------------|-------------------|-------------------|
| Computational intelligence (CI) | Machine learning / deep learning | `DNNModel`, planned `TransformerModel` |
| Parameter-rich ARX with LASSO | LEAR model | `LearModel` in `models/lear.py` |
| Multi-model per hour (24 models) | Univariate approach | `LearModel.hourly_models` — one Lasso per period |
| Single model, 24 outputs | Multivariate approach | `DNNModel` (stub) — planned for DNN/Transformer |
| Calibration window | Training window | `ExperimentConfig.calibration_windows` |
| Recalibration | Refit/retrain | `BacktestEngine` with `refit_interval_days` |
| Forecast combination | Ensemble | `BacktestEngine._ensemble_forecast()` |
| MASE (mean absolute scaled error) | rMAE (relative MAE) | `calculate_rmae()` + `build_weekly_naive()` |
| LTSC (long-term seasonal component) | Annual seasonality | `CyclicalTimeTransformer` (sin/cos encoding) |
| STSC (short-term seasonal component) | Daily/weekly seasonality | `CalendarDummyTransformer` + price lags |
| Variance stabilizing transformation | Price preprocessing | `StandardScaler` (Lago uses asinh, you use z-score) |
| Exogenous variables | Fundamental drivers | `ExperimentConfig.exogenous_curve_types` |
| Day-ahead market | Spot market | Your ENTSOE day-ahead price data |
| Reserve margin | Demand-to-capacity ratio | Not included in your data pipeline |
| Prediction interval (PI) | Probabilistic forecast | Not implemented |

---

## How This Paper Connects to Your Other Reading Guides

```
Weron (2014)                          [THIS PAPER]
  "EPF needs benchmarks,              Foundational review
   better metrics, statistical         of ALL EPF methods
   testing, forecast combination"
         |
         v
Lago et al. (2021)                    [lago_epf_benchmark_reading_guide.md]
  Answers Weron's call:                LEAR + DNN benchmark,
  epftoolbox, rMAE, DM test,           open datasets, best practices
  open-access benchmark
         |
         v
Your codebase                         [Current implementation]
  Implements Lago's LEAR,              BacktestEngine, evaluation
  calibration window ensemble,          metrics, ClickHouse pipeline
  rMAE evaluation
         |
         v
Llorente & Portela (2025)             [transformer_epf_reading_guide.md]
  Proposes Transformer as              Pure Transformer encoder
  next step beyond DNN,                 for EPF, uses epftoolbox
  uses Lago's framework                 for fair comparison
         |
         v
Your next implementation              TransformerModel + DM test
```

The MLOps paper ([mlops_best_practices_reading_guide.md](mlops_best_practices_reading_guide.md)) is orthogonal — it addresses HOW you operationalize these models, not WHAT models to build.
