# Prometheus Integration — Design Spec

**Date:** 2026-05-23
**Status:** Draft, awaiting user review.
**Related work:**
- `docs/superpowers/plans/2026-05-22-mlops-system-chapter.md` — adds the chapter that this work extends (P4 §3.4, P8 §3.8, §5.2 Quantitative Evaluation).
- `docs/superpowers/plans/2026-05-23-quantitative-system-metrics.md` — defines `scripts/report/extract_metrics.py` that this work adds a fifth collector to.

---

## 1. Goal

Add Prometheus as a third observability tier (logs via Loki, business data via
ClickHouse, *system metrics via Prometheus*) so that:

1. **Operational:** ClickHouse internals and service liveness are
   continuously measured, not only sampled when something logs an error.
2. **Chapter P4 (Containerisation):** the file-provisioned-everything claim
   gains a third infrastructure-as-code artefact (`prometheus/prometheus.yml`).
3. **Chapter P8 (Continuous Monitoring):** the chapter currently documents
   only log-based and business-data monitoring; Prometheus closes the
   infrastructure-monitoring axis that Zarour's P8 explicitly calls for.
4. **Chapter §5.2 (Quantitative Evaluation):** a fifth subsubsection
   *System availability* lands real availability percentages
   (ClickHouse, Grafana, Prometheus self) computed over the 90-day window,
   alongside the existing Operational / Reproducibility / Feedback Loop /
   DORA dimensions.

---

## 2. Scope

### In scope

- One new Docker Compose service: `prometheus`.
- One new config directory: `prometheus/` (mirrors the existing `grafana/`
  layout).
- Three Prometheus scrape jobs: ClickHouse, Grafana, Prometheus self.
- One ClickHouse config snippet enabling its native `/metrics` endpoint.
- One new Grafana datasource entry (Prometheus).
- One new Grafana dashboard JSON (`system_health.json`).
- One new Grafana alert rule (`clickhouse-down`).
- One new collector in `scripts/report/extract_metrics.py`
  (`collect_availability`), one new field on `MetricsReport`,
  one new section in the markdown renderer.
- Three chapter edits in `Report/chapters/system_implementation.tex`:
  P4 prose, P8 prose, §2.4 tech-stack table row, §5.2 new subsubsection.
- Possibly one new BibTeX entry if a Prometheus citation is wanted in
  P8 (optional — decided at chapter-edit time, no plan dependency).

### Out of scope (explicit non-decisions)

- **No `node_exporter`.** Single-host MVP; host CPU/RAM/disk are SSH-able
  on demand. Adds noise to the chapter without adding production value.
- **No `cAdvisor`.** Container OOM detection is desirable but not worth
  the maintenance surface at MVP scale.
- **No `alertmanager`.** Grafana file-provisioned alert rules remain the
  single alerting surface (preserves the P8 claim that alerting policy
  lives in Git, reviewed via PR, never UI-edited).
- **No `prometheus_client` in `src/`.** No application-level metrics, no
  pushgateway, no code changes inside `src/`. Flow runs remain observable
  via `experiment_runs.training_duration_seconds` (already in place).
- **No Loki replacement.** Loki keeps logs; Prometheus adds metrics.
  They are complementary tiers, not alternatives.
- **No retention beyond 120 days.** The 90-day quantitative window plus a
  30-day buffer is the design point. Long-term storage (Thanos, Mimir,
  remote-write) is deferred until a multi-host deployment justifies it.

---

## 3. Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│  docker compose (host)                                                 │
│                                                                        │
│  ┌────────────┐    scrapes    ┌──────────────┐                         │
│  │ Prometheus │◄──────────────│ ClickHouse   │ :8123/metrics (native)  │
│  │  :9090     │               └──────────────┘                         │
│  │  120d ret. │◄──────────────│  Grafana     │ :3000/metrics (native)  │
│  │            │◄──── self ────│  Prometheus  │                         │
│  └─────┬──────┘                                                        │
│        │ Prometheus datasource                                         │
│        ▼                                                               │
│  ┌──────────────┐  + System Health dashboard                           │
│  │   Grafana    │  + clickhouse-down alert rule                        │
│  │              │  (existing dashboards and alerts unchanged)          │
│  └──────────────┘                                                      │
│                                                                        │
│  ┌──────────────┐                                                      │
│  │  Loki        │  (unchanged — logs tier)                             │
│  └──────────────┘                                                      │
└────────────────────────────────────────────────────────────────────────┘
```

Three scrape targets, no exporters. Prometheus reaches the other services
by Docker service name on the existing default network.

---

## 4. New files

### 4.1 `prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  scrape_timeout:  10s

scrape_configs:
  - job_name: prometheus
    static_configs:
      - targets: ['localhost:9090']

  - job_name: clickhouse
    metrics_path: /metrics
    static_configs:
      - targets: ['clickhouse:8123']

  - job_name: grafana
    metrics_path: /metrics
    static_configs:
      - targets: ['grafana:3000']
```

### 4.2 `grafana/dashboards/system_health.json`

A new dashboard, sibling of the existing three. Five panels in this order:

1. **Service availability — stat row.**
   Three big single-value stat panels using
   `avg_over_time(up{job="<job>"}[$__range])`
   for `clickhouse`, `grafana`, `prometheus`. Source of truth for §5.2's
   uptime numbers when read interactively.
2. **Scrape target status — table.**
   `up{}` per job, red/green colored. One-glance "is everything
   reachable right now".
3. **ClickHouse queries/sec and p95 latency — two timeseries.**
   `rate(ClickHouseProfileEvents_Query[5m])` and the matching latency
   async-metric (exact name verified against live `/metrics` at
   implementation time; ClickHouse 25.6 metric names are authoritative).
4. **ClickHouse memory and disk — two timeseries.**
   `ClickHouseAsyncMetrics_MemoryResident`,
   `ClickHouseAsyncMetrics_DiskUsed_default`.
5. **Merge backlog — timeseries.**
   `ClickHouseMetrics_PartsActive`,
   `ClickHouseMetrics_BackgroundMergesAndMutationsPoolTask`.
   Diagnostic for "is `ReplacingMergeTree` keeping up".

The JSON is authored at implementation time; this spec only nails the
panel inventory. Existing dashboards (Data Quality, Model Performance,
Operational) are unchanged.

### 4.3 (script change, not a new file) — `scripts/report/extract_metrics.py`

A new fifth collector and a new `MetricsReport` field. See §6.

---

## 5. Modified files

### 5.1 `docker-compose.yml`

Append one service and one named volume:

```yaml
  prometheus:
    image: prom/prometheus:v2.55.0
    restart: unless-stopped
    command:
      - --config.file=/etc/prometheus/prometheus.yml
      - --storage.tsdb.path=/prometheus
      - --storage.tsdb.retention.time=120d
      - --web.enable-lifecycle
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus_data:/prometheus
    ports:
      - "9090:9090"
    networks:
      - default

volumes:
  prometheus_data:
```

(`networks: default` already exists; the new volume is appended to the
existing `volumes:` block.)

### 5.2 ClickHouse config — enable the `/metrics` endpoint

ClickHouse exposes Prometheus metrics natively but the endpoint is off by
default. Add the snippet via the existing ClickHouse config-mount
mechanism (location determined at implementation time by reading the
current `clickhouse:` service block — likely `./clickhouse/config.d/`
mounted into `/etc/clickhouse-server/config.d/`):

```xml
<clickhouse>
  <prometheus>
    <endpoint>/metrics</endpoint>
    <port>8123</port>
    <metrics>true</metrics>
    <events>true</events>
    <asynchronous_metrics>true</asynchronous_metrics>
  </prometheus>
</clickhouse>
```

If no config-mount currently exists, the implementation plan adds one and
documents it in `CLAUDE.md` § Containerisation.

### 5.3 `grafana/provisioning/datasources/<existing>.yaml`

Append one entry to the existing Loki + ClickHouse datasource file:

```yaml
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: false
```

### 5.4 `grafana/provisioning/alerting/rules.yaml`

Append one new alert rule:

```yaml
- uid: clickhouse-down
  title: ClickHouse unreachable
  condition: A
  data:
    - refId: A
      datasourceUid: prometheus
      model:
        expr: up{job="clickhouse"} == 0
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: ClickHouse has been unreachable for 5 minutes.
```

(Exact `datasourceUid` value matched to the provisioning UID at
implementation time.) Existing three rules (`data-staleness`,
`drift-detected-today`, `reconciliation-missed`) are unchanged.

### 5.5 `Report/chapters/system_implementation.tex`

Four edits:

1. **§2.4 tech-stack table** — one new row, placed after the Loki row to
   keep observability tools grouped:

   ```
   Prometheus       Metrics time-series store        Added    System metrics + uptime tracking; native ClickHouse and Grafana scrape endpoints, no exporter sidecars
   ```

2. **§3.4 P4 Containerisation** — extend the *Our implementation*
   sub-paragraph to mention `prometheus/prometheus.yml` alongside
   `grafana/provisioning/`. The "file-provisioning closes the loop with
   P1" point now applies to one more directory.

3. **§3.8 P8 Continuous Monitoring** — one new sentence in *Our
   implementation*: Prometheus scrapes ClickHouse, Grafana, and itself on
   a 15-second interval, with 120-day retention; the `up{}` metric is the
   primary liveness signal and backs both the
   `clickhouse-down` alert rule and the §5.2 availability table. Update
   *Technology choice* with one sentence on "metrics tier separate from
   logs tier: Prometheus complements Loki, does not replace it." No
   changes to the *Design rationale* paragraph.

4. **§5.2 Quantitative Evaluation** — add a fifth `\subsubsection{System
   availability}` after *Delivery cadence (DORA)*, before the closing
   "Taken together" paragraph. Structure:

   - One framing paragraph (~3 sentences) defining `up{}`, the 90-day
     window, and what counts as "available" (target scraped successfully
     at the 15-second cadence).
   - One `booktabs` table `tab:quant-availability`, two columns
     (`Metric`, `Value`), five rows: ClickHouse uptime %, Grafana uptime
     %, Prometheus self-uptime %, ClickHouse mean queries/sec, ClickHouse
     peak resident memory. Values transcribed from
     `Report/metrics/quantitative_results.md` after `collect_availability`
     has been run against the live system; `<value>` placeholders used
     during drafting, same convention as the existing DORA table.
   - One mandatory caveat sentence: *"Availability is measured from the
     day Prometheus was deployed; for windows that pre-date that
     deployment, the figures reflect the partial overlap and will narrow
     toward steady-state as the window fills."* Without this sentence
     the numbers misrepresent any window shorter than (today − deploy
     date).

   The closing "Taken together" paragraph at the end of §5.2 is updated
   to mention the fifth axis ("operational reliability, reproducibility,
   feedback responsiveness, delivery cadence, *and system availability*").

---

## 6. Quant-script collector

### 6.1 New function

Added to `scripts/report/extract_metrics.py`. Uses `httpx` (already a
transitive dependency via the ENTSO-E client — no new requirement).

```python
def collect_availability(window_days: int) -> dict[str, Any]:
    """Service uptime over the window, queried from Prometheus.

    Returns None for any metric whose target was never scraped within the
    window, or whose name has drifted across ClickHouse versions. Returns
    an empty dict if Prometheus itself is unreachable — the script still
    completes and the renderer emits 'n/a' for every cell.
    """
    base = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
    window = f"{window_days}d"

    def query(promql: str) -> float | None:
        try:
            r = httpx.get(
                f"{base}/api/v1/query",
                params={"query": promql},
                timeout=10.0,
            )
            r.raise_for_status()
        except httpx.HTTPError as e:
            print(f"prometheus query failed: {e}", file=sys.stderr)
            return None
        result = r.json()["data"]["result"]
        return float(result[0]["value"][1]) if result else None

    def uptime_pct(job: str) -> float | None:
        v = query(f'avg_over_time(up{{job="{job}"}}[{window}])')
        return round(100.0 * v, 3) if v is not None else None

    def metric(promql: str) -> float | None:
        v = query(promql)
        return round(v, 2) if v is not None else None

    return {
        "window_days": window_days,
        "clickhouse_uptime_pct": uptime_pct("clickhouse"),
        "grafana_uptime_pct":    uptime_pct("grafana"),
        "prometheus_self_uptime_pct": uptime_pct("prometheus"),
        "clickhouse_mean_qps": metric(
            f'avg_over_time(rate(ClickHouseProfileEvents_Query[5m])[{window}:5m])'
        ),
        "clickhouse_peak_memory_bytes": metric(
            f'max_over_time(ClickHouseAsyncMetrics_MemoryResident[{window}])'
        ),
    }
```

### 6.2 `MetricsReport` field

```python
availability: dict[str, Any] = field(default_factory=dict)
```

### 6.3 `main()` wiring

One new line after the `collect_dora` call:

```python
report.availability = collect_availability(WINDOW_DAYS)
```

### 6.4 `render_markdown` addition

Append after the DORA section:

```python
out.append("\n\n## System availability (Prometheus)\n")
a = report.availability
out.append(f"\n- ClickHouse uptime: **{a.get('clickhouse_uptime_pct')}%**")
out.append(f"\n- Grafana uptime: **{a.get('grafana_uptime_pct')}%**")
out.append(f"\n- Prometheus self-uptime: **{a.get('prometheus_self_uptime_pct')}%**")
out.append(f"\n- ClickHouse mean queries/sec: **{a.get('clickhouse_mean_qps')}**")
out.append(f"\n- ClickHouse peak resident memory: **{a.get('clickhouse_peak_memory_bytes')} bytes**")
```

---

## 7. Order of operations

The implementation plan must respect these dependencies:

1. ClickHouse `/metrics` endpoint enabled (XML config) **before**
   Prometheus is deployed — otherwise the `clickhouse` scrape job will
   fail and the dashboard will look broken on first paint.
2. Prometheus service deployed and a scrape cycle completed **before**
   the new Grafana datasource is added — otherwise the System Health
   dashboard renders with empty panels and the alert rule has nothing to
   evaluate against.
3. Dashboard and alert rule added **before** the chapter §5.2 edit —
   chapter prose references panel-level evidence and the alert rule by
   name; both must exist for the prose to be accurate.
4. `collect_availability` implemented and the script re-run **before**
   §5.2 prose is transcribed — `<value>` placeholders are filled from
   the regenerated `quantitative_results.md`, same pattern as the
   existing four collectors.
5. Chapter edits (§2.4 row, P4, P8, §5.2) — independent of each other,
   can be done in any order within their task, but all must precede the
   PDF rebuild.
6. PDF rebuilt and committed last (existing convention from the prior
   plans).

---

## 8. Failure modes and what the chapter must acknowledge

Three real failure modes, all surfaced in the spec rather than buried:

| Failure mode | Effect | Chapter handling |
|---|---|---|
| Prometheus reachable but no scrape data in window (first 90 days post-deploy) | `up` averages are partial | Mandatory caveat paragraph at the end of §5.2 *System availability* |
| ClickHouse metric name renamed in a future version (e.g. `ClickHouseAsyncMetrics_MemoryResident` → some other name) | `collect_availability` returns `None` for that field | Script comment pins expected ClickHouse version (25.6); renderer emits `n/a` |
| Prometheus container itself down at script-run time | `collect_availability` returns `{}` | All five rows in the §5.2 table become `n/a (no data)`; script still completes |

---

## 9. Acceptance criteria

The work is done when:

1. `docker compose up -d` brings up Prometheus alongside the existing
   stack with no error in any container log.
2. `curl localhost:9090/api/v1/targets` shows three jobs (`prometheus`,
   `clickhouse`, `grafana`), all `up=1`.
3. The Grafana *System Health* dashboard opens and the five panels render
   with non-empty data.
4. The `clickhouse-down` alert rule is visible in Grafana's alerting UI,
   in `Normal` state (because ClickHouse is up).
5. `uv run python -m scripts.report.extract_metrics` writes a
   `Report/metrics/quantitative_results.md` whose new *System
   availability* section contains five filled values (or `n/a` with the
   spec-§8 caveat in effect).
6. `Report/chapters/system_implementation.tex` references Prometheus in
   §2.4, §3.4, §3.8, and contains a `\subsubsection{System
   availability}` in §5.2 with all five `<value>`s transcribed.
7. The chapter PDF rebuilds with no undefined references and no `??`
   markers.
8. No file under `src/` has been modified. No test under `tests/` has
   been modified.

---

## 10. Open questions

None at spec-write time. All scope decisions resolved during
brainstorming:

- Depth: native exporters only, no node_exporter / cAdvisor / pushgateway
  (chosen by user).
- Quant script integration: full availability section (recommendation
  accepted by user).
- Alerting: single surface (Grafana), no alertmanager.
- Application metrics: deferred indefinitely; no `prometheus_client` in
  `src/`.

If any of these reopen during implementation, update this spec rather
than diverging silently.
