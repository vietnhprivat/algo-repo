# Forecasting Strategy & Pipeline Bottleneck Analysis

> Prepared 2026-04-21 based on codebase exploration and literature review.

---

## 1. Direct vs MIMO: Should GBT Train 24 Separate Models?

### 1.1 The academic framing

Multi-step forecasting has four canonical strategies (Ben Taieb et al., 2012, *Expert Systems with Applications*):

| Strategy | Description | Error accumulation | Inter-output correlation |
|----------|-------------|-------------------|------------------------|
| **Recursive** | One model, predictions fed back as inputs | Yes | N/A |
| **Direct** | N separate models, one per output period | No | Ignored at training |
| **MIMO** | One model, N simultaneous outputs | No | Captured at training |
| **DirRec / DirMO** | Hybrids | Partial | Partial |

Ben Taieb reviewed all four across 111 time series (NN5 competition): **no single strategy universally dominates**. MIMO wins when outputs are strongly correlated; Direct wins when per-output flexibility matters more.

### 1.2 Why LEAR's 24-model approach works despite ignoring correlations

LEAR uses the **Direct** strategy: 24 independent LASSO models, one per hour. This seems to lose inter-hour correlations (hour 3 and hour 18 prices often move together due to load patterns), but it works because **cross-hour information enters through the feature space**.

Each of the 24 models receives *all other hours' prices from d-1, d-2, d-3, d-7* as input features (~96 lag features for hourly data). So the model predicting hour 3 can learn "when hour 18 yesterday was high, hour 3 today tends to be high" — without being jointly trained with the hour-18 model. Confirmed directly in the [epftoolbox source code](https://github.com/jeslago/epftoolbox/blob/master/epftoolbox/models/_lear.py):

```python
for h in range(24):
    model = Lasso(...)
    model.fit(Xtrain, Ytrain[:, h])   # independent per hour
    self.models[h] = model
```

The Direct approach also gives LEAR a practical advantage: **each hourly model can select its own relevant features via LASSO sparsification**, rather than being constrained by a shared representation. Hour 3 AM and hour 6 PM have very different price drivers — a single joint model must compromise.

### 1.3 DNN's MIMO advantage (and why it's modest)

DNN uses **MIMO**: one MLP with 24 output neurons. From the [epftoolbox DNN source](https://github.com/jeslago/epftoolbox/blob/master/epftoolbox/models/_dnn.py):

```python
output = Dense(24, activation='linear')(hidden)
```

Shared hidden layers implicitly encode inter-hour structure. If hour 7 and hour 8 always move together, the network can learn a shared internal representation that helps predict both.

**Empirical result (Lago 2021, Nord Pool):**

| Model | rMAE |
|-------|------|
| DNN ensemble | 0.407 |
| LEAR ensemble | 0.420 |

DNN is better, but only marginally (~3% on rMAE). The gap is larger on volatile markets (EPEX-BE, EPEX-FR) and smaller on stable ones. This aligns with theory: when inter-hour correlations are stronger, MIMO's advantage grows.

**Why the gap isn't bigger:** the rich lag feature set (all hours' prices from d-1/d-2/d-3/d-7) already smuggles most cross-hour information into Direct models. MIMO's advantage is the *joint gradient signal* during training, not access to different data.

### 1.4 GBT native multi-output: current state of XGBoost/LightGBM/CatBoost

The honest answer is: **production-ready MIMO is not available for GBT frameworks today**.

**XGBoost 3.x** introduced `multi_strategy`:
- `one_output_per_tree` (default): builds N independent trees, one per target. This is what we do.
- `multi_output_tree`: trees where each leaf predicts all N targets jointly. Theoretically captures inter-target correlations during splitting.

However, the [official XGBoost documentation](https://xgboost.readthedocs.io/en/stable/tutorials/multioutput.html) states:

> "The feature is still working-in-progress, and most features are not yet implemented for `multi_output_tree`."

Missing features as of XGBoost 3.x: GPU support, SHAP values, column sampling (`colsample_bytree`), feature importance, model saving/loading in some formats, and more. **Cannot be used in production.**

**LightGBM:** No native multi-output support at all. The sklearn `MultiOutputRegressor` wrapper trains N fully independent models — Direct strategy.

**CatBoost:** Limited multi-output via `MultiRMSE` objective, but restricted to specific loss functions.

**Research prototype — GBDT-MO** (Zhang & Jung, IEEE TNNLS 2020): builds trees where each split maximises a combined objective over all targets. Shows accuracy gains over single-output GBT when targets are correlated. However, the [GitHub repository](https://github.com/zzd1992/GBDTMO) is a research prototype, not maintained, and not usable in production.

**Multivariate Boosted Trees** (Nespoli & Medici, JMLR 2022) confirms: "multivariate trees outperform univariate counterparts when predictions are correlated," and adds the ability to enforce smoothness constraints across outputs. Again, research-only.

### 1.5 Recommendation for this codebase

**Keep the 24-model per-period approach for GBT. It is correct.**

- It is the only production-viable option for XGBoost, LightGBM, and CatBoost today.
- It is academically justified: Direct strategy with cross-hour lag features is empirically competitive with MIMO on electricity price forecasting.
- The GBTModel base class (`gbt_base.py`) is already cleanly structured to switch to MIMO later when `multi_output_tree` matures — just override `fit()` in a `XGBoostMIMOModel` subclass.

**Watch:** XGBoost's multi-output roadmap ([issue #9043](https://github.com/dmlc/xgboost/issues/9043)). When GPU + column sampling are supported, a proper A/B test would be worthwhile.

---

## 2. Pipeline Bottlenecks

Based on analysis of `engine.py`, `preprocessor.py`, `transformers.py`, `gbt_base.py`, and `lightning_base.py`.

The backtest inner loop structure is:

```
for each test day (N):                          ← sequential, no parallelism
    for each calibration window (W):            ← sequential
        if needs_refit:
            slice training data                 ← O(n) DataFrame copy
            build new DataPreprocessor          ← new scaler instances
            generate feature matrix             ← O(n log n) pivots × transformers
            fit scalers                         ← StandardScaler.fit() × 2
            fit model                           ← expensive for Lightning
            predict                             ← fast
        else:
            transform features only             ← cheap
            predict                             ← fast
```

Total work: ~`N × W × refit_fraction × (feature_gen + scaler_fit + model_fit)`

### 2.1 Feature matrix regeneration per window — HIGH

**File:** `engine.py:90-98`, `preprocessor.py`, `transformers.py`

Every refit creates a new `DataPreprocessor` and regenerates the full feature matrix for the calibration window from the raw hourly DataFrame. For a 1092-day window with 2 exogenous curves, this means:

- `PriceLagTransformer.transform()` → pivot + 4 shifts
- `ExogenousLagTransformer.transform()` → pivot × 2 columns + 3 shifts each
- `CalendarDummyTransformer.transform()` → day-of-week dummies

All of this is recomputed `N × W` times even though the underlying hourly DataFrame **never changes**. The feature matrix for day `t` with a 1092-day window is 95%+ identical to the feature matrix for day `t+1`.

**Worsens with:** more exogenous columns, more transformers, more calibration windows.

### 2.2 Scaler refitted from scratch each refit — HIGH

**File:** `preprocessor.py:75-77`

```python
features_train_scaled = self.feature_scaler.fit_transform(features_train)
targets_train_scaled  = self.target_scaler.fit_transform(targets_train)
```

With `refit_interval_days=1` and a 1092-day window: the scaler is fit on [day 0…1091], then the next day on [day 1…1092] — 99.9% overlapping data, virtually identical statistics. StandardScaler's mean and std barely change, yet it's fully recomputed.

### 2.3 Sequential test date loop — HIGH (hardware-constrained)

**File:** `engine.py:150-157`

```python
for date in test_dates:           # purely sequential, N iterations
    forecast = self._ensemble_forecast(...)
```

Each test date is fully independent — no autoregressive dependencies between dates in the backtest. This loop is embarrassingly parallel **in theory**.

**Why it is not implementable on current hardware:**
- **XGBoost** already uses n_jobs=12. Running 4 dates in parallel would need 48 cores — doesn't help, just divides cores across more fits.
- **DNN/Transformer** use a single GPU. Two simultaneous Lightning `trainer.fit()` calls would queue for the same device or crash with OOM.

**When this becomes viable:** a second GPU, or a multi-GPU/multi-node setup (one date per GPU). At that point it is the single highest-leverage fix — a Transformer backtest at 20 min/fit × 81 days × 4 windows / 7 refit interval ≈ 17 hours would scale linearly with number of GPUs.

### 2.4 Exogenous pivot cost — HIGH

**File:** `transformers.py:104`

```python
for column in self.exogenous_columns:
    daily = pivot_to_daily(hourly_dataframe, column)   # O(n log n) per column
```

`pivot_to_daily()` calls `pd.DataFrame.pivot()` on datetime-indexed data. With 2 exogenous columns, 4 calibration windows, and 81 test days refitting every 7 days: `2 × 4 × 12 = 96` pivot operations on ~1092 rows each. Each operation reconstructs the same daily-format DataFrame from the same hourly data. The global feature matrix (all dates) could be pivoted once at startup and sliced.

### 2.5 GBT period loop is sequential — MEDIUM (hardware-constrained)

**File:** `gbt_base.py:49-52`

```python
for i in range(n_periods):    # 24 iterations, sequential
    estimator = self._build_estimator()
    self._fit_period(estimator, X_train, y_train[:, i], X_val, y_val[:, i])
```

The thread pool approach (24 models × n_jobs=1) is **not viable on current hardware** — it would need 24 cores but only 12 are available, causing thrashing. Current setup (1 model × n_jobs=12) already saturates the CPU.

**Becomes viable when:** CPU core count > n_periods (i.e. >24 cores). At that point: `ThreadPoolExecutor(max_workers=n_periods)` with `n_jobs=1` per estimator, same pattern as fix #2 in the implementation sketches below.

### 2.6 GBT prediction loop — MEDIUM

**File:** `gbt_base.py:57-60`

```python
return np.array([
    self._period_models[i].predict(features).item()
    for i in range(len(self._period_models))
])
```

24 separate `.predict(features)` calls where `features.shape = (1, n_features)`. Each call has overhead disproportionate to the work. Could be batched by stacking features and using XGBoost's batch predict.

---

## 3. Does Any of This Actually Matter?

**For production (live predictions):** No. The `LiveRunner` trains once overnight and runs one forward pass the next morning. That single training run is fast for all models — even XGBoost on 1092 days takes minutes, not hours. The bottlenecks above only apply to the backtest loop which simulates daily recalibration across 81 test dates.

**For research iteration:** Yes. Running 10 config variants means 10 overnight backtests. If each takes 4+ hours, experimentation slows significantly. The caching fixes (#1 and #2 below) reduce this without requiring new hardware.

**Practical rule:** don't optimise until the overnight backtest time actually blocks you. If you can kick it off before bed and have results in the morning, the current state is fine.

## 4. Priority Fixes Before Adding Complex Models

### Implementable now (current hardware)

| Priority | Fix | File | Impact | Effort |
|----------|-----|------|--------|--------|
| 1 | **Cache pivot results** in transformers — pivot each exogenous column once globally, not per window | `transformers.py` | High | Low |
| 2 | **Cache global feature matrix** — precompute once at backtest start, slice by date window | `engine.py` + `preprocessor.py` | High | Medium |
| 3 | **Increase `refit_interval_days`** — already implemented, biggest single lever | config | High | Zero |

**Recommended order:** #3 is already done. Do #1 first (lowest effort, measurable gain for all models with exogenous). Then #2 which requires careful refactoring.

### Requires hardware upgrade

| Fix | Requires | Impact |
|-----|----------|--------|
| **Parallelise test date loop** | ≥2 GPUs (one per date for DNN/Transformer) | Critical for Transformer backtests |
| **Parallelise GBT period loop** | CPU cores > 12 × n_periods (currently maxed at n_jobs=12 already) | Medium for XGBoost/LightGBM |
| **Multi-GPU DNN training** | ≥2 GPUs | Halves DNN fit time |

### Implementation sketches

**Fix #2 — cache pivots in transformers** (`transformers.py`):
```python
# ExogenousLagTransformer: pivot once at construction time or first call,
# store as self._daily_cache, reuse across windows
if self._daily_cache is None:
    self._daily_cache = {col: pivot_to_daily(hourly_df, col) for col in self.exogenous_columns}
daily = self._daily_cache[column]
```

**Fix #2 — cache global feature matrix** (`engine.py` + `DataPreprocessor`):
```python
# In BacktestRunner.run() — before the test loop:
full_feature_matrix = preprocessor.generate_full_feature_matrix(raw_data)
# Pass to engine; engine slices by date instead of regenerating
features_train = full_feature_matrix.loc[train_start:train_end]
```
Requires separating feature generation (done once) from scaling (done per window, since scaler is fit on training data only).

---

## References

- Ben Taieb, S., Bontempi, G., Atiya, A., & Sorjamaa, A. (2012). A review and comparison of strategies for multi-step ahead time series forecasting. *Expert Systems with Applications*, 39(8), 7067–7083. https://www.sciencedirect.com/article/pii/S0957417412000528
- Lago, J., Marcjasz, G., De Schutter, B., & Weron, R. (2021). Forecasting day-ahead electricity prices: A review of state-of-the-art algorithms, best practices and an open-access benchmark. *Applied Energy*, 293, 116983. https://www.sciencedirect.com/article/pii/S0306261921004529
- Zhang, Z. & Jung, C. (2020). GBDT-MO: Gradient-Boosted Decision Trees for Multiple Outputs. *IEEE Transactions on Neural Networks and Learning Systems*. https://arxiv.org/abs/1909.04373
- Nespoli, L. & Medici, V. (2022). Multivariate Boosted Trees and Applications to Forecasting and Control. *Journal of Machine Learning Research*, 23, 1–37. https://jmlr.org/papers/v23/21-0247.html
- XGBoost multi-output documentation: https://xgboost.readthedocs.io/en/stable/tutorials/multioutput.html
- epftoolbox LEAR source: https://github.com/jeslago/epftoolbox/blob/master/epftoolbox/models/_lear.py
- epftoolbox DNN source: https://github.com/jeslago/epftoolbox/blob/master/epftoolbox/models/_dnn.py
- Ben Taieb, S. (2014). Machine learning strategies for multi-step-ahead time series forecasting. PhD thesis. https://souhaib-bentaieb.com/papers/2014_phd.pdf
