# System Health dashboard — Prometheus capabilities showcase

Date: 2026-06-17
Status: approved design, pending implementation

## Purpose

Replace the current System Health dashboard (seven panels of raw infra metrics:
container uptime, query rate, resident memory, merge backlog) with a dashboard
that **demonstrates what Prometheus is good at and justifies the decision to
use it**. The audience is the thesis / defense, so each panel maps to a named
Prometheus or PromQL capability that can be pointed at and explained.

This is a bachelor thesis, so the dashboard stays lean (one header note plus six
panels). It deliberately demonstrates capabilities rather than cataloguing every
available metric.

## Constraints

- Prometheus scrapes only three targets: `clickhouse`, `grafana`, `prometheus`
  itself (`prometheus.yml`). There is no node-exporter, cAdvisor, or Prefect
  exporter, so no host CPU/RAM/disk or container metrics are available. Panels
  use ClickHouse internals, Grafana's own metrics, and the `up` series.
- Do not duplicate the other dashboards: **Data Quality** owns ingestion
  freshness/gaps, **Operational** owns the Loki log stream.
- Datasource is the provisioned Prometheus datasource (`uid: prometheus`).
- The dashboard is auto-provisioned from `grafana/dashboards/system_health.json`
  (file provider, 30s reload). No new exporters or scrape config in scope.

## Design (Approach A: capabilities showcase)

Underlying logic borrows the RED method (Rate, Errors, Duration) for services
and USE (Utilization, Saturation, Errors) for resources, so every panel has a
named purpose.

A **"Why Prometheus" text panel** sits at the top: pull-based scraping,
multi-dimensional label model with PromQL, efficient time-series storage, and
native alerting.

| # | Panel | Capability demonstrated | Query (representative) | Viz |
|---|-------|-------------------------|------------------------|-----|
| 1 | Service availability / SLO | Pull-based `up` scraping; SLO over any window | `avg_over_time(up[$__range]) * 100` by job | stat row + target table |
| 2 | Query & insert throughput | Counters → `rate()` | `rate(ClickHouseProfileEvents_Query[5m])`, `rate(ClickHouseProfileEvents_InsertedRows[5m])` | timeseries |
| 3 | Error rate | `increase()` on error counters (E in RED) | `increase(ClickHouseProfileEvents_FailedQuery[1h])` | timeseries |
| 4 | Request latency p50/p95/p99 | `histogram_quantile()` on native histograms | `histogram_quantile(0.95, sum(rate(grafana_http_request_duration_seconds_bucket[5m])) by (le))` | timeseries |
| 5 | Disk-fill forecast | `predict_linear()` predictive alerting | `predict_linear(ClickHouseAsyncMetrics_DiskAvailable_default[6h], 7*24*3600)`; current used % from `DiskUsed/DiskTotal` | stat + timeseries |
| 6 | Resource saturation (USE) | Gauges for utilization/saturation | `ClickHouseAsyncMetrics_MemoryResident`, `ClickHouseMetrics_PartsActive`, `ClickHouseMetrics_BackgroundMergesAndMutationsPoolTask`, `*Connection` | timeseries |

Each panel description text names the capability so the dashboard is
self-explanatory in a defense setting.

## Implementation notes

- Edit `grafana/dashboards/system_health.json` in place (keep `uid: system-health`).
- Mirror the JSON conventions already used in the repo's dashboards.
- Validate every panel query through Grafana's datasource proxy
  (`POST /api/ds/query`) before claiming done, then confirm the file reloads.

## Out of scope

- New exporters (node-exporter, Prefect) or scrape-config changes.
- Alerting rule changes (`grafana/provisioning/alerting/rules.yaml`).
- Platform-liveness panels (last successful forecast, reconciliation lag) — that
  was a considered alternative but rejected in favour of the Prometheus-strengths
  framing.

## Success criteria

- Six panels plus the header note render with real data.
- Each panel is labelled with the Prometheus/PromQL capability it demonstrates.
- Dashboard auto-reloads and all queries return through Grafana's proxy.
