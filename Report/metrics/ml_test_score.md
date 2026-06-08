# ML Test Score worksheet (Breck et al. 2017)

Score each item 0 (not done) / 0.5 (manual) / 1 (automated). Final score = min of the
four section sums. Evidence = one-line pointer into algo-repo.

## Section 1 — Data tests
| # | Test | Score | Evidence |
|---|---|---|---|
| 1 | Feature expectations captured in a schema | 1 | `enforce_schema()` in `src/domain/src/domain/curves.py`; raises `ValueError` on any dtype or column mismatch; tested in `tests/domain/` |
| 2 | All features are beneficial | 0 | No systematic ablation study documenting each feature's contribution; `forecast-cli ablate` CLI exists but was not used to document benefit of every default feature |
| 3 | No feature costs too much | 0 | No latency or compute-cost analysis of individual feature transformers; no documented cost threshold per feature |
| 4 | Features adhere to meta-level requirements | 0 | No documented meta-level feature requirements (regulatory, contractual, fairness) in this domain; wholesale market price data has no such constraints |
| 5 | Data pipeline has appropriate privacy controls | 0 | ENTSOE Transparency Platform data is public market data (no PII); no privacy controls needed or implemented — n/a domain, score 0 per rubric |
| 6 | New features can be added quickly | 0.5 | `FeatureTransformer` ABC in `src/price_forecasting/src/price_forecasting/data/transformers.py`; documented in `docs/CONTRIBUTING.md`; manual process (no automated scaffold or speed SLA) |
| 7 | All input feature code is tested | 1 | `tests/price_forecasting/test_transformers.py` covers all transformer classes (`PriceLagTransformer`, `ExogenousLagTransformer`, `CalendarDummyTransformer`, `CyclicalTimeTransformer`, `MeanWeeklyForecastTransformer`, `PastPriceSequenceTransformer`, `DayAheadExogTransformer`); runs in CI via `pr_test.yml` |

## Section 2 — Model development tests
| # | Test | Score | Evidence |
|---|---|---|---|
| 1 | Model specs are reviewed and submitted | 0.5 | `configs/*.py` files are first-class Git files subject to PR review (`docs/CONTRIBUTING.md`); no automated spec-schema validation gate |
| 2 | Offline and online metrics correlate | 0.5 | Reconciliation flow computes the same MAE/RMSE/sMAPE metrics on live predictions that backtest uses (`price_forecasting.evaluation`); W&B `algo-prod` project tracks both; no formal documented correlation study |
| 3 | All hyperparameters have been tuned | 0.5 | DNN: 6 HPs tuned via Optuna TPE (`forecast-cli tune`), persisted to `algo.hyperparam_trials`; LEAR: `alpha="auto"` (cross-validated); calibration windows from Lago et al. 2021 paper, not searched; Transformer HPs partially manual |
| 4 | The impact of model staleness is known | 0.5 | Daily refit at 06:00 UTC guarantees staleness < 24 h; no documented experiment measuring accuracy degradation at 48 h / 7-day staleness |
| 5 | A simpler model is not better | 0.5 | LEAR (linear Lasso) vs DNN vs Transformer backtests run and tracked in W&B `algo-research`; `rMAE` compares against weekly-naive baseline (`build_weekly_naive`); not an automated gating criterion |
| 6 | Model quality is sufficient on slices | 0.5 | Per-area backtests (DK1, DE) produce slice-level metrics; `compute_metrics_per_hour` gives per-period breakdowns; no automated pass/fail gate per slice |
| 7 | The model is tested for inclusion (fairness) | 0 | n/a domain — wholesale electricity price forecasting has no demographic groups or inclusion requirements; score 0 per rubric |

## Section 3 — ML infrastructure tests
| # | Test | Score | Evidence |
|---|---|---|---|
| 1 | Training is reproducible | 0.5 | `algo.experiment_runs` carries `git_sha`, `data_start_utc`, `data_end_utc`, `model_artifact_id`; `scripts/report/reproduce_run.py` re-runs a logged forecast and compares against stored prediction; LEAR is deterministic; DNN uses enumerated seeds but GPU non-determinism is not suppressed |
| 2 | Model specs are unit tested | 1 | `tests/price_forecasting/test_models.py`, `test_transformer_model.py`, `test_dnn_ensemble.py`; all run in CI via `pr_test.yml` |
| 3 | The full ML pipeline is integration tested | 1 | End-to-end LEAR smoke test in `tests/price_forecasting/test_smoke.py` and full Compose stack smoke in `.github/workflows/pr_smoke.yml` (daily-forecast + reconciliation against synthetic data) |
| 4 | Model quality validated before serving | 0 | No quality gate before predictions are written to `algo.experiment_predictions`; `daily_forecast_flow` trains and serves without checking output against a minimum-quality threshold |
| 5 | The model allows debugging by observing steps | 0.5 | Loki structured logging via `build_log_extra()` in all Prefect tasks; W&B per-epoch loss from `build_lightning_logger()`; no interactive or per-layer step-through instrumentation |
| 6 | Models are tested via a canary process | 0.5 | `cd_deploy.yml` `smoke_run` job triggers `daily-forecast-dk1_lear` and polls until completion after every deploy; checks flow completes but does not validate prediction quality against a threshold |
| 7 | Models can be quickly and safely rolled back | 0.5 | Trained model blobs stored in `algo.model_artifacts` (migration `005`); image rollback via `docker build + compose restart`; no automated rollback command or button |

## Section 4 — Monitoring tests
| # | Test | Score | Evidence |
|---|---|---|---|
| 1 | Dependency changes result in notification | 0 | `uv.lock` tracked in Git; no Dependabot, Renovate, or automated notification on library version changes |
| 2 | Data invariants hold in training and serving | 0.5 | `enforce_schema()` enforced at domain model construction; same `DataPreprocessor` used in both `BacktestRunner` and `LiveRunner`; schema enforcement raises exception but is not monitored/alerted independently |
| 3 | Training and serving features compute same values | 1 | `DataPreprocessor` is a single shared class used in both `BacktestRunner` (`backtesting/runner.py`) and `LiveRunner` (`live_runner.py`); structural guarantee — not two separate implementations |
| 4 | Models are not too stale | 0.5 | Daily refit means model staleness < 24 h; Grafana `data-staleness` alert monitors input data freshness (`grafana/provisioning/alerting/rules.yaml`) but no dedicated alert fires when a model has not been retrained within N hours |
| 5 | The model is numerically stable | 0.5 | `asinh` scaler (`price_forecasting/data/asinh_scaler.py`) handles price spikes/negatives; no automated numerical-stability test (e.g. NaN/inf assertion on prediction outputs) |
| 6 | Compute performance has not regressed | 0.5 | `training_duration_seconds` tracked per run in `algo.experiment_runs` (migration `006`) and logged to W&B `algo-prod`; no automated alert when training duration exceeds a threshold |
| 7 | Prediction quality has not regressed | 1 | `schedules/reconciliation.py::_maybe_alert_accuracy_degradation` posts Slack alert when MAE > 1.5× 30-day median; Grafana `reconciliation-missed` rule fires when no reconciled run in 36 h; both automated |

## Scores
- Section 1 (Data) sum: 2.5 / 7
- Section 2 (Model) sum: 3.0 / 7
- Section 3 (Infra) sum: 4.0 / 7
- Section 4 (Monitoring) sum: 4.0 / 7
- **ML Test Score = min(section sums) = 2.5**
