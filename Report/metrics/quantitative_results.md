# Quantitative System Metrics
_Window: last 90 days. Generated: 2026-06-04T15:07:16+00:00._

## Operational metrics

### Per-config training duration and run counts

| Area | Model | Runs | p50 train (s) | p95 train (s) |
|---|---|---|---|---|
| DE | dnn | 1 | 4.4 | 4.4 |
| DE | transformer | 1 | 9.1 | 9.1 |
| DK1 | dnn | 1 | 5.6 | 5.6 |
| DK1 | lear | 11 | 32.5 | 35.1 |
| DK1 | transformer | 1 | 11.3 | 11.3 |

### Reconciliation completeness

- Eligible runs (forecast day already in the past by ≥2 days): **15**
- Reconciled (at least one actual logged): **15**
- Reconciliation rate: **100.0%**

## Reproducibility coverage

- Total live runs in window: **15**
- With non-empty `git_sha`: **66.7%**
- With `data_start_utc` populated: **100.0%**
- With `data_end_utc` populated: **100.0%**
- With `model_artifact_id` populated: **100.0%**
- With the full provenance triple: **66.7%**

## Drift monitoring

- Drift reports written: **49**
- Drift detections (`drift_detected = 1`): **49**
