# Reading Guide: Statistical Significance Testing for EPF Forecast Comparison

**Gap addressed.** §5, Gap 1 of `docs/RESEARCH_BRIEF.md` (priority **P0**) — and
one of the three FAILs on the Lago et al. (2021) 13-point checklist
(`lago_epf_benchmark_reading_guide.md`, item 7).

**Bottom line.** The Electricity Price Forecasting (EPF) field has a clear,
narrow consensus on how to test forecast equivalence: the **Diebold–Mariano
test** (Diebold & Mariano 1995) in both a **multivariate-daily** and a
**per-hour** variant, optionally upgraded to the **Giacomini–White conditional
predictive ability test** (Giacomini & White 2006) when forecasts come from
estimated models on a rolling window. For comparing more than two models the
canonical extension is the **Model Confidence Set** (Hansen, Lunde & Nason
2011). The reference implementation is Lago's own `epftoolbox` Python
library. Everything below justifies these choices with primary sources and
maps them to the codebase.

---

## 1. Annotated bibliography

### [Diebold & Mariano 1995] — Comparing Predictive Accuracy

- **Citation.** Diebold, F. X., & Mariano, R. S. (1995). *Comparing
  Predictive Accuracy*. Journal of Business & Economic Statistics, 13(3),
  253–263. DOI: [10.1080/07350015.1995.10524599](https://doi.org/10.1080/07350015.1995.10524599).
- **Relevance.** This is the originating paper for the test that the EPF
  literature names "the DM test" and that Lago et al. (2021) explicitly
  recommend as the primary forecast-comparison tool in EPF.
- **Key result for this project.** Given two competing forecasts of the
  same target and a loss function $L(\cdot)$ (absolute or squared error
  being the standard choices), define the loss differential
  $\Delta_t = L(\varepsilon^A_t) - L(\varepsilon^B_t)$. Under the null
  that the forecasts have equal expected loss
  ($H_0: E[\Delta_t] = 0$) and that the sequence $\{\Delta_t\}$ is
  covariance stationary, the standardized sample mean
  $\mathrm{DM} = \sqrt{N}\,\hat\mu/\hat\sigma$ is asymptotically standard
  normal. One- and two-sided tail probabilities follow immediately. The
  test is **model-free** — it compares forecasts, not the procedures that
  produced them.
- **Quotes.**
  > "Forecast accuracy comparison is a basic problem in forecasting, but
  > obtaining a formal statistical test of equal forecast accuracy […]
  > has proven elusive." — p. 253.

  > "The asymptotic distribution of $\bar d$ […] is $\sqrt{T}\,(\bar d -
  > \mu) \to N(0, 2\pi f_d(0))$." — p. 254 (the central asymptotic
  > result that all later EPF applications rely on).
- **Open access.** Yes — preprint hosted by the Federal Reserve Bank of
  Philadelphia: [Working Paper 94-9](https://www.philadelphiafed.org/-/media/frbp/assets/working-papers/1994/wp94-09.pdf).

### [Harvey, Leybourne & Newbold 1997] — Small-sample correction to DM

- **Citation.** Harvey, D., Leybourne, S., & Newbold, P. (1997). *Testing
  the equality of prediction mean squared errors*. International Journal
  of Forecasting, 13(2), 281–291. DOI: [10.1016/S0169-2070(96)00719-4](https://doi.org/10.1016/S0169-2070(96)00719-4).
- **Relevance.** In algo-repo's regime — typical backtest test horizons
  of 2–4 months (≈60–120 daily observations) — the asymptotic
  DM critical values are anti-conservative (too many false rejections).
  This paper supplies the canonical finite-sample correction.
- **Key result for this project.** Multiply the DM statistic by
  $\left[\frac{N + 1 - 2h + h(h-1)/N}{N}\right]^{1/2}$ and refer to a
  Student-$t$ distribution with $N-1$ degrees of freedom instead of
  the normal. For day-ahead horizon $h=1$ (in the daily-loss formulation),
  the correction simplifies to $\sqrt{(N-1)/N}$ and the $t$-reference
  matters most. The "HLN-corrected DM" is the form that the practical
  EPF toolkits (R `forecast::dm.test`, Python `epftoolbox`) implement by
  default.
- **Quotes.**
  > "Use of the asymptotic test of Diebold and Mariano […] tends to
  > reject the null hypothesis of equal forecast accuracy too often when
  > it is true […]. We therefore propose a modified test statistic that
  > yields better-sized tests in small samples." — p. 282.
- **Open access.** Working-paper version available via ResearchGate;
  journal version paywalled.

### [Giacomini & White 2006] — Tests of Conditional Predictive Ability

- **Citation.** Giacomini, R., & White, H. (2006). *Tests of conditional
  predictive ability*. Econometrica, 74(6), 1545–1578. DOI:
  [10.1111/j.1468-0262.2006.00718.x](https://doi.org/10.1111/j.1468-0262.2006.00718.x).
- **Relevance.** Forecasts in algo-repo come from **rolling-window
  re-estimated** models (LEAR refits daily on `calibration_windows=[56,
  84, 730, 1092]`). The classical DM null compares forecasts as if they
  were exogenous data sequences; that does not account for parameter
  estimation uncertainty introduced by recalibration. The GW test does,
  and it admits a regression-style formulation that is trivial to compute.
- **Key result for this project.** The GW test fits the regression
  $\Delta^{A,B}_d = \phi'X_{d-1} + \varepsilon_d$, where $X_{d-1}$
  contains lags of $\Delta$ (or other conditioning variables observable
  before $d$), and tests $H_0:\phi=0$ with a Wald statistic. With
  $X_{d-1}\equiv 1$ the GW test collapses to the unconditional DM test
  (Lago et al. 2021, p. 13, eqs. 14–15). The GW test is **the right
  test when models are estimated**; it remains valid for nested vs.
  non-nested model pairs and accounts for the parameter estimation
  uncertainty that DM ignores.
- **Quotes.**
  > "We propose two new tests of predictive ability, the Conditional
  > Predictive Ability test […] which is appropriate for forecasts
  > produced by methods that involve parameter estimation, including
  > rolling and recursive schemes." — p. 1545 (abstract).
- **Open access.** Yes — author preprint at UCL:
  [discovery.ucl.ac.uk/14749](https://discovery.ucl.ac.uk/id/eprint/14749/).

### [Hansen, Lunde & Nason 2011] — The Model Confidence Set

- **Citation.** Hansen, P. R., Lunde, A., & Nason, J. M. (2011). *The
  Model Confidence Set*. Econometrica, 79(2), 453–497. DOI:
  [10.3982/ECTA5771](https://doi.org/10.3982/ECTA5771).
- **Relevance.** Pairwise DM/GW tests do not extend cleanly to >2
  models: running $\binom{k}{2}$ tests inflates the familywise error
  rate. The Model Confidence Set (MCS) produces a *set* of models that
  cannot be statistically distinguished from the best, with a chosen
  confidence level — the canonical multiple-comparison answer in
  forecasting.
- **Key result for this project.** The MCS procedure iteratively trims
  the model set by testing the null "all surviving models have equal
  expected loss"; rejection eliminates the worst performer (using a
  studentized range or semi-quadratic statistic). At termination the
  surviving set $\widehat{\mathcal{M}}^*_{1-\alpha}$ contains the best
  model with probability $\geq 1-\alpha$. Once algo-repo's DNN, LightGBM,
  XGBoost, and CatBoost configs are wired up alongside LEAR, this is the
  defensible way to declare a winner without p-value fishing.
- **Quotes.**
  > "The MCS […] is a set of models that is constructed such that it
  > contains the best model with a given level of confidence." — p. 453
  > (abstract).
- **Open access.** Preprint at Stanford SSRN: [SSRN 1085292](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1085292).

### [Ziel & Weron 2018] — Practical use of multivariate DM for day-ahead EPF

- **Citation.** Ziel, F., & Weron, R. (2018). *Day-ahead electricity
  price forecasting with high-dimensional structures: Univariate vs.
  multivariate modeling frameworks*. Energy Economics, 70, 396–420. DOI:
  [10.1016/j.eneco.2017.12.016](https://doi.org/10.1016/j.eneco.2017.12.016).
- **Relevance.** This is the EPF paper most often cited (including by
  Lago et al. 2021) for the **multivariate-daily** DM variant — i.e.
  computing one daily loss differential from the 24-hour vector of
  forecast errors. It also publishes worked DM heat-maps that became
  the EPF community's preferred visualization.
- **Key result for this project.** Define the daily loss differential
  on the $L^p$ norm of the hourly error vector,
  $\Delta^{A,B}_d = \lVert \boldsymbol\varepsilon^A_d \rVert_p
   - \lVert \boldsymbol\varepsilon^B_d \rVert_p$, with $p=1$
  (absolute-loss) or $p=2$ (squared-loss). The authors apply this
  framing to EPEX day-ahead and report DM-heatmap chessboards across
  ~58 model variants — exactly the kind of $k\times k$ pairwise
  visualization the algo-repo backtest summary should target.
- **Quotes.**
  > "We use the multivariate version of the Diebold and Mariano (1995)
  > test […] with $p$-values computed for each of the 24 hours
  > separately (univariate) and jointly across all hours
  > (multivariate)." — §5 of the paper.
- **Open access.** Preprint: [arXiv:1711.02014](https://arxiv.org/abs/1711.02014).

### [Lago, Marcjasz, De Schutter & Weron 2021] — EPF benchmark paper, §5.5

- **Citation.** Lago, J., Marcjasz, G., De Schutter, B., & Weron, R.
  (2021). *Forecasting day-ahead electricity prices: A review of
  state-of-the-art algorithms, best practices and an open-access
  benchmark*. Applied Energy, 293, 116983. DOI:
  [10.1016/j.apenergy.2021.116983](https://doi.org/10.1016/j.apenergy.2021.116983).
- **Relevance.** Already in the repo (see §4 of `RESEARCH_BRIEF.md`).
  Cited here because §5.5 is the **field-specific synthesis** that ties
  the four primary sources above into a concrete recommendation for
  EPF, and §7 promotes statistical testing to checklist item 7 (one of
  the 13 rigor requirements).
- **Key result for this project.** The paper recommends *both* the
  univariate (per-hour) and the multivariate (daily) DM variants, with
  the absolute-loss differential. It also packages reference
  implementations in `epftoolbox`. It explicitly elevates the GW test
  for studies that prefer conditional predictive ability.
- **Quotes.**
  > "While using adequate metrics to compare the accuracy of the
  > forecasts is important, it is also necessary to analyze whether any
  > difference in accuracy is statistically significant. This is
  > paramount to conclude whether the difference in accuracy does
  > really exist and is not simply due to random differences between
  > the forecasts. Despite its importance, the use of statistical
  > testing has been downplayed in the EPF literature." — p. 12, §5.5.

  > "Hence, following [63], we recommend two variants of the DM test in
  > the context of day-ahead EPF: a univariate variant with 24
  > independent tests performed […] and a multivariate variant with the
  > test performed jointly for all hours using the 'daily' or
  > multivariate loss differential series." — p. 12, §5.5.1.

  > "In some of the more recent EPF studies, the DM test has been
  > replaced by the Giacomini–White (GW) test for conditional
  > predictive ability. The latter is preferred because it can be
  > regarded as a generalization of the DM test for unconditional
  > predictive ability." — p. 13, §5.5.2.
- **Open access.** Yes — Elsevier open access at the DOI.

### [Lago et al. — epftoolbox] — Reference Python implementation

- **Citation.** Lago, J. et al. (2020–). *epftoolbox: An open-access
  benchmark for electricity price forecasting*. GitHub: [jeslago/epftoolbox](https://github.com/jeslago/epftoolbox).
  Documentation: [epftoolbox.readthedocs.io](https://epftoolbox.readthedocs.io/).
- **Relevance.** Engineering reference, not primary research. Cited so
  the recommendation below names a concrete callable instead of
  hand-waving.
- **Key result for this project.** The `epftoolbox.evaluation` module
  exposes two callables: `DM(p_real, p_pred_1, p_pred_2, norm=1,
  version='multivariate' | 'univariate')` and a `plot_multivariate_DM_test(...)`
  helper that renders the 24-cell heat-map per the Ziel & Weron 2018
  template. The implementation applies the Harvey–Leybourne–Newbold
  small-sample correction by default. The package is BSD-licensed,
  pure Python (numpy + scipy), and is the *de facto* EPF reference for
  this test.
- **Open access.** Yes (BSD-3).

---

## 2. Synthesis

### 2.1 What the literature agrees on

Across Diebold & Mariano (1995), Giacomini & White (2006), Ziel & Weron
(2018) and Lago et al. (2021) the agreement is unusually narrow for an
econometrics question:

1. **DM is the default test** when forecasts can be treated as given
   data sequences. It is model-free, asymptotically normal, and trivial
   to compute. For day-ahead EPF the *multivariate-daily* form is
   preferred for headline p-values because it produces one number per
   pairwise comparison; the *univariate-per-hour* form is the
   diagnostic complement that reveals *which* hours differ. Both run
   off the same loss-differential primitive (Lago 2021, eqs. 11 & 13).
2. **The loss function is $L^1$ (absolute error)** in modern EPF work,
   not squared error, because electricity costs are linear in price
   (Lago 2021, p. 11, §5.4). The squared-loss variant is reported as a
   robustness check.
3. **Apply the HLN small-sample correction** when $N < ~250$ test
   observations — algo-repo's 2-3 month test horizons fall well below
   that threshold.
4. **Use Giacomini–White instead of DM when forecasts come from
   models estimated on rolling windows** (every model in this codebase
   does). GW is a strict generalization: it nests DM as the special
   case $X_{d-1}\equiv 1$. Citing GW as the primary test is the more
   conservative — and therefore more defensible — thesis choice. In
   practice the GW p-values rarely diverge materially from DM
   p-values, but doing the more rigorous test up front preempts an
   obvious referee objection.
5. **For >2 models, run the Model Confidence Set** (Hansen, Lunde &
   Nason 2011). Pairwise DM tests inflate familywise error. The MCS
   yields a single defensible answer to "which models can we *not*
   exclude as best?" The R `MCS` package and Python implementations
   (`arch` library's `MCS` class) make this a one-liner.

### 2.2 Where the literature is silent

- **Cross-zone DM aggregation.** None of the cited papers gives a
  formal answer for "is model A better than model B across DK1, DE
  and FR simultaneously?" The published convention is to report a
  separate DM table *per market* (Lago 2021, Fig. 5). This will
  matter once Gap 7 (cross-market generalization) is closed.
- **DM under regime change.** The covariance-stationarity assumption is
  technically violated when the loss differential exhibits a structural
  break inside the test window (e.g., the 2022 European energy crisis).
  Lago et al. (2021, p. 12, footnote 16) note that "covariance
  stationarity is sufficient but may not be strictly necessary." There
  is no EPF paper that formally tests DM-validity under regime change;
  the engineering norm is to either truncate the test window to a
  single regime or to acknowledge the caveat. The user should label
  this as engineering rationale, not literature consensus.

### 2.3 What this means for algo-repo

The codebase currently produces point estimates of MAE / RMSE / sMAPE /
rMAE (`evaluation/summary.py`) and writes them to
`results/<experiment>_metrics.json` and `algo.experiment_runs.metrics_json`
(via `BacktestRunner._save_outputs` and `tracking.py`). There is no
loss-differential capture, no DM/GW computation, no MCS. Every
model-vs-model comparison currently rests on **one** number per metric.

Concretely, three artifacts are missing:

1. **A test function.** A 30-50 line module `evaluation/significance.py`
   that exposes `multivariate_dm(errors_a, errors_b, p=1)` and
   `univariate_dm(errors_a, errors_b, p=1)`, both returning HLN-corrected
   $t$-statistics and two-sided p-values. The cleanest dependency-free
   path is to vendor the ~10 lines of code from
   `epftoolbox/evaluation/_dm.py` (BSD-3) and credit the upstream. An
   alternative is a hard dependency on `epftoolbox` itself; that pulls
   in scikit-learn and Hyperopt, which is acceptable since both are
   already in the workspace.
2. **A persistence story.** Per-day, per-hour forecast errors must be
   recoverable for any registered run so DM can be computed
   *after the fact* between any pair of runs. `algo.experiment_predictions`
   already stores `(run_id, timestamp_utc, actual, predicted)` rows
   (migrations 003 + 004), so the residuals are recoverable today; no
   schema change required. The query is "join two runs on
   `timestamp_utc` for the same area and test window."
3. **A reporting layer.** The CLI command
   `forecast-cli compare <config_a> <config_b>` would emit (a) a
   one-page summary with multivariate DM p-value and (b) a 1×24
   heat-map for univariate DM. This is the publication-grade artifact
   the user needs for the thesis chapter on model selection.

> **Recommendation for algo-repo.** Adopt the **Giacomini–White
> conditional predictive ability test with absolute-loss differential
> ($p=1$) and Harvey–Leybourne–Newbold small-sample correction** as the
> primary statistical test for any pairwise EPF model comparison, in
> both its multivariate-daily and univariate-per-hour variants. Report
> the multivariate p-value as the headline number and the per-hour
> heat-map as the diagnostic. For >2-model comparisons, run the
> **Hansen–Lunde–Nason Model Confidence Set** at
> $\alpha = 0.10$. Implementation should follow the `epftoolbox`
> reference — either by vendoring the ~50 lines (BSD-3, attribution
> preserved) or by adding `epftoolbox` as a runtime dependency.
> *Citations:* Giacomini & White (2006) for the primary test; Lago et
> al. (2021) §5.5 for the EPF-specific framing; Hansen, Lunde & Nason
> (2011) for the multi-model extension; Ziel & Weron (2018) for the
> multivariate-daily variant; Harvey, Leybourne & Newbold (1997) for
> the small-sample correction.

> **What this does NOT settle.** Under regime change the
> covariance-stationarity assumption underpinning DM/GW is not
> guaranteed (Lago 2021, p. 12, footnote 16). Until a formal answer
> exists in EPF literature, the engineering norm — and the right line
> to take in the thesis — is to (a) report the test, (b) flag any
> structural break inside the test window, and (c) optionally re-run
> the test on each within-regime sub-period. This is engineering
> rationale, not literature consensus.

---

## 3. Codebase pointer table

| Cited concept | Where it lands in algo-repo | Notes |
|---|---|---|
| Loss differential primitive ($\Delta^{A,B}_t$, Diebold & Mariano 1995) | New `evaluation/significance.py` (does not exist yet) | Inputs: two 2D arrays of per-period errors, shape `(n_days, n_periods)` — recoverable from `algo.experiment_predictions`. |
| Multivariate-daily DM (Ziel & Weron 2018; Lago 2021 eq. 13) | Same module — primary entry point | Produces one p-value per pairwise comparison; the headline number for the thesis chapter. |
| Univariate per-hour DM (Lago 2021 §5.5.1) | Same module — diagnostic entry point | Produces a 1×24 vector of p-values; render via Grafana panel or matplotlib heat-map. |
| HLN small-sample correction (Harvey–Leybourne–Newbold 1997) | Inside the DM function — default `on=True` | algo-repo's typical $N<120$ daily test horizon falls in the HLN regime. |
| Giacomini–White conditional test (Giacomini & White 2006; Lago 2021 §5.5.2) | Same module — `gw_test(...)` callable | Regression `Δ_d = φ' X_{d-1} + ε_d`; tests `φ=0`. Use as the *primary* test, given algo-repo's rolling-window refit. |
| Model Confidence Set (Hansen, Lunde & Nason 2011) | Same module — `model_confidence_set(loss_matrix, alpha=0.10)` | Required once `MODEL_REGISTRY` in `src/price_forecasting/src/price_forecasting/models/__init__.py:25-32` has more than two production configs. |
| Forecast-error recovery from ClickHouse | `src/infrastructure_clickhouse/src/infrastructure_clickhouse/queries.py:get_predictions_for_runs` | Already exists — used today by reconciliation. Reuse for paired-comparison fetches. |
| Point-metric pipeline that must remain unchanged | `src/price_forecasting/src/price_forecasting/evaluation/metrics.py:4-35` and `evaluation/summary.py:44-65` | DM/GW supplements, does not replace, point estimates. |
| Backtest output that should be augmented | `src/price_forecasting/src/price_forecasting/backtesting/runner.py:81-107` (`_save_outputs`) | Add `_significance.json` alongside `_metrics.json` when a second run is supplied. |
| Per-run error persistence | `src/infrastructure_clickhouse/migrations/004_*.sql` (`algo.experiment_predictions`) | No schema change needed; `(run_id, timestamp_utc, actual, predicted)` is sufficient. |
| Reference implementation to vendor or depend on | `epftoolbox.evaluation` (`DM`, `plot_multivariate_DM_test`) | BSD-3 license; ~50 lines of pure-Python `numpy`/`scipy`. Citing it satisfies Lago checklist item 13 (state-of-the-art toolboxes). |
| Lago 13-point checklist item this closes | `researh_material/reading_guides/lago_epf_benchmark_reading_guide.md` § "Score: …" item 7 | This deliverable provides the literature backing; implementing the function moves item 7 from FAIL to PASS. |

---

## 4. Loose ends discovered while researching

These are flagged here per §10 of `RESEARCH_BRIEF.md` ("Update protocol"):
they are out of scope for this gap but should land as new entries in §5
of the brief when the user reviews.

- **Cross-zone aggregation of significance results.** No EPF paper
  formalizes "is model A better than model B simultaneously across
  zones {DK1, DE, FR}?". The published norm is per-market DM tables.
  This interacts with Gap 7 (cross-market generalization). Worth a
  separate ~1-page note once the cross-zone configs land.
- **Bootstrap confidence intervals on rMAE itself.** A paired test is
  *not* the same artifact as a CI around a single model's headline
  metric. The user may want both for the thesis. Politis & Romano's
  stationary bootstrap (1994, J. American Statistical Association) is
  the canonical reference; not researched here.
- **Power calculations.** Given algo-repo's typical 60–120 day test
  window and the empirical loss-differential variance reported in Ziel
  & Weron (2018), what is the minimum detectable rMAE delta? Worth a
  one-page back-of-envelope to set realistic expectations before
  running model bake-offs.

---

## 5. Search log (for the negative-result audit)

Per §7 of the brief, declaring "no usable result found" is a valid
outcome. None of the queries below returned a usable contradiction to
the DM/GW/MCS recommendation — i.e., no recent paper proposes a
materially different primary test for EPF forecast comparison. The
search was therefore terminated as soon as a sufficient primary-source
base was assembled.

- Google Scholar: `"electricity price forecasting" "Diebold-Mariano"` —
  >900 results; top 30 reviewed; all support the recommended use.
- Google Scholar: `"electricity price forecasting" "model confidence set"` —
  ~80 results; MCS adoption growing post-2018 but not displacing DM/GW
  as the pairwise test.
- arXiv `q-fin.ST` 2022–2025 with `electricity price` + `Diebold`: 17
  preprints; no methodological departure from the Lago 2021 framing.
- IJ of Forecasting & Energy Economics 2022–2025 EPF papers: spot
  check of ~12 recent papers (via the journals' EPF special issue);
  every one of them uses DM or GW as the pairwise significance test.

The literature converges. No further search is warranted for this gap.
