# Quantitative System Metrics
_Window: last 90 days. Generated: 2026-05-24T12:48:49+00:00._

## Operational metrics

### Per-config training duration and run counts

| Area | Model | Runs | p50 train (s) | p95 train (s) |
|---|---|---|---|---|
| DK1 | lear | 7 | 0.6 | 33.8 |

### Reconciliation completeness

- Eligible runs (forecast day already in the past by ≥2 days): **7**
- Reconciled (at least one actual logged): **7**
- Reconciliation rate: **100.0%**

## Reproducibility coverage

- Total live runs in window: **7**
- With non-empty `git_sha`: **85.7%**
- With `data_start_utc` populated: **100.0%**
- With `data_end_utc` populated: **100.0%**
- With `model_artifact_id` populated: **100.0%**
- With the full provenance triple: **85.7%**

## Feedback loop

- Drift reports written: **27**
- Drift detections (`drift_detected = 1`): **27**
- Completed drift→retrain pairs: **0**
- p50 drift-to-completed latency: **N/A min**
- p95 drift-to-completed latency: **N/A min**

## DORA metrics

- Deployments in window: **20** (14 success / 6 failed)
- Deploy frequency: **1.09/week**
- Lead time PR-merge → cd_deploy start (p50): **0.1 min**
- Lead time (p95): **0.1 min**
- Change failure rate: **30.0%**

## System availability (Prometheus)

- ClickHouse uptime: **100.0%**
- Grafana uptime: **80.702%**
- Prometheus self-uptime: **100.0%**
- ClickHouse mean queries/sec: **0.02**
- ClickHouse peak resident memory: **1276919808.0 bytes**
