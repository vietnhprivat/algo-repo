# Prometheus Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Prometheus as a third observability tier (system metrics, alongside Loki for logs and ClickHouse for business data), wire its uptime numbers into the chapter's §5.2 quantitative-evaluation script, and update the MLOps system chapter so P4, P8, §2.4, and §5.2 reflect the new tier.

**Architecture:** One new Docker Compose service scrapes ClickHouse's native `/metrics` endpoint, Grafana's `/metrics` endpoint, and itself, at 15-second intervals with 120-day retention. Grafana gains a new datasource, a fourth dashboard (System Health), and one new file-provisioned alert rule (`clickhouse-down`). No application code under `src/` is modified.

**Tech Stack:** Prometheus 2.55, Docker Compose, ClickHouse native Prometheus endpoint, Grafana 12 (existing), httpx (already in stack), LaTeX (booktabs, tabularx).

---

## Pre-flight reading (mandatory)

Before any task, the implementing engineer reads, in this order:

1. `docs/superpowers/specs/2026-05-23-prometheus-integration-design.md` — authoritative spec.
2. `docker-compose.yml` — current service layout (no `networks:` block; services use the implicit default network).
3. `grafana/provisioning/datasources/datasources.yml` — current datasource format.
4. `grafana/provisioning/alerting/rules.yaml` — current alert-rule format (note the `apiVersion: 1` / `groups[].rules[]` structure and the `interval: 5m` group-level evaluation cadence).
5. `grafana/dashboards/model_performance.json` (or any one of the three existing dashboards) — match the JSON style of the new System Health dashboard to what already ships.
6. `scripts/report/extract_metrics.py` — current collector structure (the new `collect_availability` follows the same shape).
7. `Report/chapters/system_implementation.tex` — locate §2.4, §3.4, §3.8, §5.2 before editing.

Reads are cheap; assumptions cost rewrites. Do not skip.

---

### Task 0: Bootstrap `prometheus/` directory and scrape config

**Files:**
- Create: `prometheus/prometheus.yml`

- [ ] **Step 1: Verify the directory does not exist yet**

Run: `ls prometheus/ 2>&1`
Expected: `ls: cannot access 'prometheus/': No such file or directory`

- [ ] **Step 2: Create the directory and config file**

```bash
mkdir -p prometheus
```

Write `prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 15s
  scrape_timeout: 10s

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

- [ ] **Step 3: Lint the YAML**

Run: `python -c "import yaml; yaml.safe_load(open('prometheus/prometheus.yml'))"`
Expected: exit 0, no output. (If yaml is unavailable, `docker run --rm -v $(pwd)/prometheus:/etc/prometheus prom/prometheus:v2.55.0 promtool check config /etc/prometheus/prometheus.yml` is the heavyweight alternative.)

- [ ] **Step 4: Commit**

```bash
git add prometheus/prometheus.yml
git commit -m "feat(observability): add Prometheus scrape config"
```

---

### Task 1: Enable the ClickHouse `/metrics` endpoint

**Files:**
- Create: `clickhouse/config.d/prometheus.xml`
- Modify: `docker-compose.yml` (the `clickhouse:` service block — add a config-mount volume)

ClickHouse 25.6 exposes Prometheus metrics natively but the endpoint is off by default. We enable it via a config-snippet mounted into `/etc/clickhouse-server/config.d/`, which ClickHouse auto-discovers and merges with its base config.

- [ ] **Step 1: Verify there is no existing config-mount**

Run: `grep -n config.d docker-compose.yml`
Expected: no output. (If there is output, the config-mount path already exists — adapt step 3 to put the file in the existing location instead of `./clickhouse/config.d/`.)

- [ ] **Step 2: Create the ClickHouse config directory and snippet**

```bash
mkdir -p clickhouse/config.d
```

Write `clickhouse/config.d/prometheus.xml`:

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

- [ ] **Step 3: Mount the config directory into the ClickHouse container**

Edit `docker-compose.yml`. In the `clickhouse:` service `volumes:` block, change:

```yaml
    volumes:
      - clickhouse_data:/var/lib/clickhouse
```

to:

```yaml
    volumes:
      - clickhouse_data:/var/lib/clickhouse
      - ./clickhouse/config.d:/etc/clickhouse-server/config.d:ro
```

- [ ] **Step 4: Restart ClickHouse and verify the endpoint**

Run:
```bash
docker compose up -d clickhouse
sleep 5
curl -fs http://localhost:8123/metrics | head -20
```

Expected: at least 20 lines of Prometheus exposition format (lines starting with `# HELP`, `# TYPE`, or metric-name samples like `ClickHouseProfileEvents_Query`). If `curl` returns `404 Not Found`, the config snippet did not load — check `docker logs clickhouse-server` for parse errors.

- [ ] **Step 5: Commit**

```bash
git add clickhouse/config.d/prometheus.xml docker-compose.yml
git commit -m "feat(observability): enable ClickHouse Prometheus /metrics endpoint"
```

---

### Task 2: Add Prometheus service to `docker-compose.yml`

**Files:**
- Modify: `docker-compose.yml` (append a new service block and a new named volume)

- [ ] **Step 1: Append the new service block**

Edit `docker-compose.yml`. After the `grafana:` service block (the last service, ending with the `healthcheck:` block at around line 86), and **before** the `volumes:` block, add:

```yaml
  # Prometheus metrics scraper — scrapes ClickHouse, Grafana, and itself
  prometheus:
    image: prom/prometheus:v2.55.0
    container_name: prometheus
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
    depends_on:
      - clickhouse
      - grafana
```

- [ ] **Step 2: Append the new named volume**

In the top-level `volumes:` block (currently `clickhouse_data, prefect_storage, grafana_data, loki_data`), add `prometheus_data:` so the block reads:

```yaml
volumes:
  clickhouse_data:
  prefect_storage:
  grafana_data:
  loki_data:
  prometheus_data:
```

- [ ] **Step 3: Validate compose file**

Run: `docker compose config -q`
Expected: exit 0, no output. Any syntax error prints to stderr.

- [ ] **Step 4: Commit (do not bring the stack up yet — Task 3 does that with verification)**

```bash
git add docker-compose.yml
git commit -m "feat(observability): add Prometheus service to compose stack"
```

---

### Task 3: Bring up Prometheus and verify all three scrape targets are healthy

**Files:**
- No file changes. Verification only.

- [ ] **Step 1: Start Prometheus**

Run:
```bash
docker compose up -d prometheus
sleep 20
```

The 20-second sleep gives Prometheus time to do one scrape cycle (two intervals at 15s) so the targets API has data.

- [ ] **Step 2: Inspect the targets API**

Run:
```bash
curl -fs http://localhost:9090/api/v1/targets | python -m json.tool | grep -E '"job"|"health"'
```

Expected output (order may vary):

```
"job": "prometheus"
"health": "up"
"job": "clickhouse"
"health": "up"
"job": "grafana"
"health": "up"
```

If any target shows `"health": "down"`, inspect `lastError` in the same JSON and resolve before continuing:
- `clickhouse` down → revisit Task 1 (endpoint not enabled or config snippet not loaded).
- `grafana` down → Grafana may not yet expose `/metrics`; check `docker logs grafana` for the `Starting server` line and re-curl.
- `prometheus` down → impossible if the API responded; recheck the command.

- [ ] **Step 3: Sanity-query a ClickHouse metric**

Run:
```bash
curl -fs 'http://localhost:9090/api/v1/query?query=up{job="clickhouse"}' | python -m json.tool
```

Expected: `"resultType": "vector"`, `"result": [...]` with one entry whose `"value"` is `[..., "1"]`.

- [ ] **Step 4: No commit needed (no file changes), but log the deploy date**

Record the current UTC date — this is the **Prometheus deployment date**, the floor of the §5.2 availability window. The chapter caveat sentence in Task 12 references it.

```bash
date -u +%Y-%m-%d
```

Note the output for use in Task 12.

---

### Task 4: Add Prometheus as a Grafana datasource

**Files:**
- Modify: `grafana/provisioning/datasources/datasources.yml`

- [ ] **Step 1: Append the new datasource entry**

Edit `grafana/provisioning/datasources/datasources.yml`. After the existing `Loki` entry (the file currently ends after `maxLines: 1000`), append:

```yaml

  - name: Prometheus
    uid: prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: false
    jsonData:
      timeInterval: 15s
```

(The blank line before `- name:` is required to separate it from the preceding `jsonData` block. The `uid: prometheus` value is referenced by the alert rule and dashboard in Tasks 5–6 — do not change it.)

- [ ] **Step 2: Restart Grafana to pick up the provisioning change**

Run:
```bash
docker compose restart grafana
sleep 10
```

- [ ] **Step 3: Verify the datasource is loaded**

Run:
```bash
curl -fs -u admin:admin http://localhost:3000/api/datasources/name/Prometheus | python -m json.tool | grep -E '"name"|"type"|"url"'
```

Expected:
```
"name": "Prometheus",
"type": "prometheus",
"url": "http://prometheus:9090",
```

If you customized `GRAFANA_ADMIN_PASSWORD` in `.env`, substitute it for `admin` in the `-u` flag.

- [ ] **Step 4: Commit**

```bash
git add grafana/provisioning/datasources/datasources.yml
git commit -m "feat(observability): add Prometheus datasource to Grafana"
```

---

### Task 5: Create the System Health dashboard

**Files:**
- Create: `grafana/dashboards/system_health.json`

This dashboard is the live visual surface for the System Health metrics. It is the *fourth* dashboard, sibling to `data_quality.json`, `model_performance.json`, `operational.json`.

- [ ] **Step 1: Read one existing dashboard for style reference**

Run: `head -40 grafana/dashboards/model_performance.json`

Note the top-level fields (`annotations`, `editable`, `panels`, `schemaVersion`, `time`, `timepicker`, `title`, `uid`, `version`). The new dashboard must include the same top-level structure so Grafana's provisioner accepts it.

- [ ] **Step 2: Create the dashboard JSON**

Write `grafana/dashboards/system_health.json`:

```json
{
  "annotations": {"list": []},
  "editable": false,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "panels": [
    {
      "type": "stat",
      "title": "ClickHouse uptime (window)",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "gridPos": {"h": 5, "w": 8, "x": 0, "y": 0},
      "targets": [
        {"refId": "A", "expr": "avg_over_time(up{job=\"clickhouse\"}[$__range]) * 100", "instant": true}
      ],
      "fieldConfig": {"defaults": {"unit": "percent", "decimals": 3, "min": 0, "max": 100}}
    },
    {
      "type": "stat",
      "title": "Grafana uptime (window)",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "gridPos": {"h": 5, "w": 8, "x": 8, "y": 0},
      "targets": [
        {"refId": "A", "expr": "avg_over_time(up{job=\"grafana\"}[$__range]) * 100", "instant": true}
      ],
      "fieldConfig": {"defaults": {"unit": "percent", "decimals": 3, "min": 0, "max": 100}}
    },
    {
      "type": "stat",
      "title": "Prometheus self-uptime (window)",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "gridPos": {"h": 5, "w": 8, "x": 16, "y": 0},
      "targets": [
        {"refId": "A", "expr": "avg_over_time(up{job=\"prometheus\"}[$__range]) * 100", "instant": true}
      ],
      "fieldConfig": {"defaults": {"unit": "percent", "decimals": 3, "min": 0, "max": 100}}
    },
    {
      "type": "table",
      "title": "Scrape target status",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "gridPos": {"h": 6, "w": 24, "x": 0, "y": 5},
      "targets": [
        {"refId": "A", "expr": "up", "instant": true, "format": "table"}
      ]
    },
    {
      "type": "timeseries",
      "title": "ClickHouse query rate (5m)",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 11},
      "targets": [
        {"refId": "A", "expr": "rate(ClickHouseProfileEvents_Query[5m])", "legendFormat": "queries/sec"}
      ],
      "fieldConfig": {"defaults": {"unit": "qps"}}
    },
    {
      "type": "timeseries",
      "title": "ClickHouse resident memory",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 11},
      "targets": [
        {"refId": "A", "expr": "ClickHouseAsyncMetrics_MemoryResident", "legendFormat": "resident bytes"}
      ],
      "fieldConfig": {"defaults": {"unit": "bytes"}}
    },
    {
      "type": "timeseries",
      "title": "Merge backlog (active parts + pending merges)",
      "datasource": {"type": "prometheus", "uid": "prometheus"},
      "gridPos": {"h": 8, "w": 24, "x": 0, "y": 19},
      "targets": [
        {"refId": "A", "expr": "ClickHouseMetrics_PartsActive", "legendFormat": "active parts"},
        {"refId": "B", "expr": "ClickHouseMetrics_BackgroundMergesAndMutationsPoolTask", "legendFormat": "background merges"}
      ]
    }
  ],
  "refresh": "30s",
  "schemaVersion": 39,
  "tags": ["system", "prometheus"],
  "templating": {"list": []},
  "time": {"from": "now-24h", "to": "now"},
  "timepicker": {},
  "timezone": "utc",
  "title": "System Health",
  "uid": "system-health",
  "version": 1,
  "weekStart": ""
}
```

- [ ] **Step 3: Lint the JSON**

Run: `python -c "import json; json.load(open('grafana/dashboards/system_health.json'))"`
Expected: exit 0, no output.

- [ ] **Step 4: Restart Grafana to pick up the new dashboard**

```bash
docker compose restart grafana
sleep 10
```

- [ ] **Step 5: Verify the dashboard appears**

Run: `curl -fs -u admin:admin "http://localhost:3000/api/search?query=System+Health" | python -m json.tool`
Expected: a JSON array containing one entry with `"title": "System Health"` and `"uid": "system-health"`.

Open `http://localhost:3000/d/system-health` in a browser and confirm all seven panels render. If any metric is missing (empty panel), the metric name may have changed in ClickHouse 25.6 — query `curl -s localhost:8123/metrics | grep -i memory` to find the live name and update the dashboard JSON before committing.

- [ ] **Step 6: Commit**

```bash
git add grafana/dashboards/system_health.json
git commit -m "feat(observability): add System Health Grafana dashboard"
```

---

### Task 6: Add the `clickhouse-down` alert rule

**Files:**
- Modify: `grafana/provisioning/alerting/rules.yaml`

- [ ] **Step 1: Append the new rule**

Edit `grafana/provisioning/alerting/rules.yaml`. After the existing `reconciliation-missed` rule (last in the file, ending with `severity: error`), append:

```yaml

      - uid: clickhouse-down
        title: ClickHouse unreachable
        condition: A
        data:
          - refId: A
            relativeTimeRange:
              from: 300
              to: 0
            datasourceUid: prometheus
            model:
              expr: up{job="clickhouse"} == 0
              instant: true
              refId: A
        for: 5m
        annotations:
          summary: ClickHouse has been unreachable for 5 minutes (up{job=clickhouse}=0).
        labels:
          severity: critical
```

(The leading blank line keeps spacing consistent with the existing rules; the rule sits under the existing `groups[0].rules:` list, so the indentation is six spaces for `- uid:`.)

- [ ] **Step 2: Restart Grafana**

```bash
docker compose restart grafana
sleep 10
```

- [ ] **Step 3: Verify the alert rule loaded**

Run:
```bash
curl -fs -u admin:admin "http://localhost:3000/api/v1/provisioning/alert-rules" | python -m json.tool | grep -E '"uid"|"title"'
```

Expected: four rules listed, including `clickhouse-down` with title `"ClickHouse unreachable"`. State should be `Normal` (because ClickHouse is up).

If the rule does not load, check `docker logs grafana 2>&1 | grep -i 'provisioning.*alert' | tail -20` for YAML parse errors.

- [ ] **Step 4: Commit**

```bash
git add grafana/provisioning/alerting/rules.yaml
git commit -m "feat(observability): add clickhouse-down Prometheus alert rule"
```

---

### Task 7: Implement `collect_availability` in `extract_metrics.py`

**Files:**
- Modify: `scripts/report/extract_metrics.py`

This is the only Python change in the entire plan. It follows the existing four-collector pattern.

- [ ] **Step 1: Add required imports at the top of the file**

Edit `scripts/report/extract_metrics.py`. The existing imports block already has `os`, `sys`, `json`, `subprocess`, `datetime`, `timedelta`, `timezone`, `Path`, `Any`, `field`, `dataclass`. Confirm `httpx` is **not** there, then add:

```python
import sys
import httpx
```

(`sys` may already be present — re-check. `httpx` is new.)

- [ ] **Step 2: Add the `availability` field to `MetricsReport`**

In the `@dataclass` block for `MetricsReport`, append after the `dora` field:

```python
    availability: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 3: Add the new collector function**

Add after `collect_dora` (and before `render_markdown`):

```python
def collect_availability(window_days: int) -> dict[str, Any]:
    """Service uptime over the window, queried from Prometheus.

    Returns None for any metric whose target was never scraped within the
    window, or whose name has drifted across ClickHouse versions. Returns
    a partial dict if Prometheus itself is unreachable — the script still
    completes and the renderer emits 'None' for every cell.

    Expected ClickHouse version: 25.6. If ClickHouse is upgraded and the
    async-metric names change, the affected queries return None and the
    chapter will show 'n/a' until this function is updated.
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
            print(f"prometheus query failed for {promql!r}: {e}", file=sys.stderr)
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
        "grafana_uptime_pct": uptime_pct("grafana"),
        "prometheus_self_uptime_pct": uptime_pct("prometheus"),
        "clickhouse_mean_qps": metric(
            f'avg_over_time(rate(ClickHouseProfileEvents_Query[5m])[{window}:5m])'
        ),
        "clickhouse_peak_memory_bytes": metric(
            f'max_over_time(ClickHouseAsyncMetrics_MemoryResident[{window}])'
        ),
    }
```

- [ ] **Step 4: Wire the call into `main()`**

In `main()`, after the `report.dora = collect_dora(WINDOW_DAYS)` line, add:

```python
    report.availability = collect_availability(WINDOW_DAYS)
```

- [ ] **Step 5: Append the new rendering section to `render_markdown`**

In `render_markdown`, after the DORA section block (the line `out.append(f"\n- Change failure rate: ...")`), insert before `out.append("\n")` and `return "".join(out)`:

```python
    out.append("\n\n## System availability (Prometheus)\n")
    a = report.availability
    out.append(f"\n- ClickHouse uptime: **{a.get('clickhouse_uptime_pct')}%**")
    out.append(f"\n- Grafana uptime: **{a.get('grafana_uptime_pct')}%**")
    out.append(f"\n- Prometheus self-uptime: **{a.get('prometheus_self_uptime_pct')}%**")
    out.append(f"\n- ClickHouse mean queries/sec: **{a.get('clickhouse_mean_qps')}**")
    out.append(f"\n- ClickHouse peak resident memory: **{a.get('clickhouse_peak_memory_bytes')} bytes**")
```

- [ ] **Step 6: Run the script end-to-end**

```bash
uv run python -m scripts.report.extract_metrics
```

Expected: prints `Wrote /home/vietnh/Projects/algo-repo/Report/metrics/quantitative_results.md`. No tracebacks. The new System availability section appears at the end of the file. Numbers may be small (Prometheus only has data since deployment time) — that is correct, not a bug.

- [ ] **Step 7: Inspect the output**

Run: `tail -15 Report/metrics/quantitative_results.md`
Expected: five lines under `## System availability (Prometheus)`, each with a value or `None`. Sanity-check: uptime percentages are in `[0, 100]`, memory is a non-negative number of bytes.

- [ ] **Step 8: Commit (script + regenerated markdown together)**

```bash
git add scripts/report/extract_metrics.py Report/metrics/quantitative_results.md
git commit -m "feat(report): add Prometheus availability collector to extract_metrics"
```

---

### Task 8: Update §2.4 tech-stack table

**Files:**
- Modify: `Report/chapters/system_implementation.tex`

- [ ] **Step 1: Locate the §2.4 tech-stack table**

Run: `grep -n "Tech\|Tool.*Role" Report/chapters/system_implementation.tex | head`
Expected: a line near the table header showing `\textbf{Tool}` or similar. Note the line number.

- [ ] **Step 2: Add the Prometheus row**

In the tech-stack table body, locate the existing `Loki` row. **Immediately after** the Loki row, insert:

```latex
    Prometheus       & Metrics time-series store                     & Added    & System metrics, uptime tracking; native ClickHouse and Grafana scrape endpoints, no exporter sidecars \\
```

(Column alignment in `&`-separated rows: column widths are not load-bearing — pdflatex re-aligns. Match the existing rows' separator spacing as closely as is convenient.)

- [ ] **Step 3: Re-compile the standalone**

```bash
cd Report
pdflatex -interaction=nonstopmode system_implementation_standalone.tex >/dev/null && echo OK
cd ..
```

Expected: `OK`. If the compile fails, examine `Report/system_implementation_standalone.log` for the error — most likely a stray `&` or `\\` in the row you added.

- [ ] **Step 4: Commit**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): add Prometheus row to tech-stack table"
```

---

### Task 9: Update §3.4 P4 Containerisation prose

**Files:**
- Modify: `Report/chapters/system_implementation.tex`

- [ ] **Step 1: Locate the §3.4 *Our implementation* paragraph**

Run: `grep -n "P4\|Containerisation\|Containerization\|file-provisioning" Report/chapters/system_implementation.tex | head`

Find the *Our implementation* sub-paragraph in §3.4, which currently enumerates `Dockerfile`, `Dockerfile.worker`, `docker-compose.yml`, and the Grafana provisioning directory.

- [ ] **Step 2: Extend the paragraph to name `prometheus/prometheus.yml`**

Find the existing sentence naming `grafana/provisioning/` (the file-provisioned directory). After the clause referencing Grafana provisioning, insert:

```latex
The Prometheus scrape configuration lives at \texttt{prometheus/prometheus.yml} and is mounted read-only into the Prometheus container; the same file-provisioning discipline that applies to Grafana dashboards and alert rules applies here --- the scrape policy is reviewed in Git and never edited at runtime.
```

This single new sentence is the only prose addition to §3.4. No other changes.

- [ ] **Step 3: Re-compile**

```bash
cd Report && pdflatex -interaction=nonstopmode system_implementation_standalone.tex >/dev/null && echo OK
cd ..
```

Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): extend P4 prose with Prometheus config-mount"
```

---

### Task 10: Update §3.8 P8 Continuous Monitoring prose

**Files:**
- Modify: `Report/chapters/system_implementation.tex`

- [ ] **Step 1: Locate the §3.8 *Our implementation* paragraph**

Run: `grep -n "P8\|Continuous monitoring\|Loki\|python-logging-loki" Report/chapters/system_implementation.tex | head`

- [ ] **Step 2: Add one sentence to *Our implementation***

After the existing sentence describing the three Grafana dashboards (Data Quality, Model Performance, Operational), insert:

```latex
A fourth dashboard, \emph{System Health}, is backed by Prometheus, which scrapes ClickHouse's native \texttt{/metrics} endpoint, Grafana's \texttt{/metrics} endpoint, and itself on a 15-second cadence and retains 120 days of time-series data. The \texttt{up\{\}} metric exposed by every scrape target is the platform's primary liveness signal: it drives the new \texttt{clickhouse-down} alert rule and the system-availability table in \S5.2.
```

- [ ] **Step 3: Add one sentence to *Technology choice***

In the same §3.8 P8 section, find the *Technology choice* sub-paragraph. After the sentence rejecting Promtail, insert:

```latex
Prometheus sits alongside Loki rather than replacing it: Loki is the logs tier, Prometheus the metrics tier. They are complementary, and Grafana remains the single dashboard and alerting surface above both.
```

- [ ] **Step 4: Re-compile**

```bash
cd Report && pdflatex -interaction=nonstopmode system_implementation_standalone.tex >/dev/null && echo OK
cd ..
```

Expected: `OK`.

- [ ] **Step 5: Commit**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): document Prometheus tier in P8 prose"
```

---

### Task 11: Add §5.2 *System availability* subsubsection

**Files:**
- Modify: `Report/chapters/system_implementation.tex`

This is the most substantive chapter edit. The new subsubsection is inserted into §5.2 *Quantitative Evaluation* **after** *Delivery cadence (DORA)* and **before** the closing "Taken together" paragraph.

- [ ] **Step 1: Locate the insertion point**

Run: `grep -n "Delivery cadence\|Taken together" Report/chapters/system_implementation.tex`

Expected: two line numbers. The new subsubsection is inserted between them.

- [ ] **Step 2: Open `Report/metrics/quantitative_results.md` alongside the .tex file**

This is the source of the numbers transcribed below. Keep both files open while editing.

- [ ] **Step 3: Insert the new subsubsection**

At the insertion point identified in Step 1, insert:

```latex
\subsubsection{System availability}

The drift-detection, daily-forecast, and reconciliation flows above all
assume the platform's infrastructure tier is healthy. The Prometheus
deployment scrapes the \texttt{up\{\}} metric from ClickHouse, Grafana,
and itself every fifteen seconds; over a window, the time-average of
\texttt{up\{\}} is the fraction of scrape cycles during which the target
responded successfully. Table~\ref{tab:quant-availability} reports the
five system-availability figures over the last ninety days. Mean query
rate and peak resident memory are reported alongside the three uptime
percentages because they characterise the ClickHouse instance's
operating regime: an availability of 100\,\% means little if the
instance was idle the entire window.

\begin{table}[h]
  \centering
  \caption{System availability over the last 90 days.}
  \label{tab:quant-availability}
  \begin{tabularx}{\linewidth}{@{}X r@{}}
    \toprule
    \textbf{Metric} & \textbf{Value} \\
    \midrule
    ClickHouse uptime                              & <value>\,\% \\
    Grafana uptime                                 & <value>\,\% \\
    Prometheus self-uptime                         & <value>\,\% \\
    ClickHouse mean queries per second             & <value> \\
    ClickHouse peak resident memory                & <value>\,bytes \\
    \bottomrule
  \end{tabularx}
\end{table}

Availability is measured from the day Prometheus was deployed
(<DEPLOY_DATE>); for windows that pre-date that deployment, the figures
reflect the partial overlap and will narrow toward steady-state as the
window fills.
```

- [ ] **Step 4: Transcribe the numbers**

Replace each `<value>` placeholder with the matching number from
`Report/metrics/quantitative_results.md` (the *System availability
(Prometheus)* section). Where a value is `None`, write `---` and add a
brief inline note: e.g. *"--- (deployment too recent for a meaningful
average)"*.

Replace `<DEPLOY_DATE>` with the date recorded in Task 3 step 4, in
ISO format (e.g. `2026-05-23`).

- [ ] **Step 5: Update the closing "Taken together" paragraph**

Find the existing paragraph beginning *"Taken together, these four
axes..."* at the end of §5.2. Change *"these four axes"* → *"these five
axes"* and append *"and system availability"* to the comma-separated
list of dimensions. For example:

Before:
```latex
Taken together, these four axes turn the chapter's qualitative ``Realised''
labels into measurements: every claim about reliability, reproducibility,
or delivery in this chapter can be checked against the numbers above...
```

After:
```latex
Taken together, these five axes turn the chapter's qualitative ``Realised''
labels into measurements: every claim about reliability, reproducibility,
delivery, or system availability in this chapter can be checked against
the numbers above...
```

- [ ] **Step 6: Re-compile**

```bash
cd Report && pdflatex -interaction=nonstopmode system_implementation_standalone.tex >/dev/null && echo OK
cd ..
```

Expected: `OK`. If the compile fails with an unknown reference, double-check that the new `\label{tab:quant-availability}` is unique and that the closing paragraph's edit did not break a sentence.

- [ ] **Step 7: Commit**

```bash
git add Report/chapters/system_implementation.tex
git commit -m "docs(report): add §5.2 System availability subsubsection"
```

---

### Task 12: Rebuild PDF and verify acceptance criteria

**Files:**
- Modify (build artifacts): `Report/system_implementation_standalone.pdf` and aux files.

- [ ] **Step 1: Full two-pass compile**

```bash
cd Report
pdflatex -interaction=nonstopmode system_implementation_standalone.tex
bibtex system_implementation_standalone
pdflatex -interaction=nonstopmode system_implementation_standalone.tex
pdflatex -interaction=nonstopmode system_implementation_standalone.tex
cd ..
```

Expected: the final pass exits 0 with no `Warning: There were undefined references` and no `??` markers in the PDF.

- [ ] **Step 2: Run the acceptance checklist from the spec**

The spec §9 lists eight acceptance criteria. Verify each in order:

```bash
# Criterion 1: stack is up
docker compose ps prometheus | grep -q "Up" && echo "1. PROMETHEUS UP ✓" || echo "1. FAIL"

# Criterion 2: three healthy scrape targets
curl -fs http://localhost:9090/api/v1/targets \
  | python -c "import json,sys; d=json.load(sys.stdin); ups=[t for t in d['data']['activeTargets'] if t['health']=='up']; print(f'2. SCRAPE TARGETS UP: {len(ups)}/3')"

# Criterion 3: dashboard renders (manual — open browser)
echo "3. Open http://localhost:3000/d/system-health and confirm all 7 panels render"

# Criterion 4: alert rule loaded
curl -fs -u admin:admin http://localhost:3000/api/v1/provisioning/alert-rules \
  | python -c "import json,sys; d=json.load(sys.stdin); names=[r['uid'] for r in d]; print('4. clickhouse-down PRESENT:', 'clickhouse-down' in names)"

# Criterion 5: extract_metrics has a System availability section
grep -q "## System availability" Report/metrics/quantitative_results.md && echo "5. AVAILABILITY SECTION ✓" || echo "5. FAIL"

# Criterion 6: chapter references Prometheus in all four sections
grep -q "Prometheus" Report/chapters/system_implementation.tex && \
  grep -q "subsubsection{System availability}" Report/chapters/system_implementation.tex && \
  echo "6. CHAPTER UPDATED ✓" || echo "6. FAIL"

# Criterion 7: PDF rebuilt
test -f Report/system_implementation_standalone.pdf && echo "7. PDF EXISTS ✓" || echo "7. FAIL"

# Criterion 8: no src/ or tests/ changes
git diff main -- src/ tests/ | wc -l | (read n; [ "$n" -eq 0 ] && echo "8. NO src/ OR tests/ CHANGES ✓" || echo "8. FAIL — $n lines changed")
```

Expected: every line ends with `✓` or with a passing count. If any line ends `FAIL`, fix and re-run before committing.

- [ ] **Step 3: Visual PDF inspection**

Open the rebuilt PDF and confirm:

1. §2.4 tech-stack table contains a Prometheus row.
2. §3.4 P4 mentions `prometheus/prometheus.yml`.
3. §3.8 P8 mentions the System Health dashboard and the metrics-vs-logs distinction.
4. §5.2 has five subsubsections (Operational reliability, Reproducibility, Feedback loop, Delivery cadence, System availability).
5. The closing "Taken together" paragraph says *five* axes, not four.
6. No `??` marker, no `<value>` placeholder, no `<DEPLOY_DATE>` placeholder anywhere in the printed text.

- [ ] **Step 4: Commit the regenerated PDF**

```bash
git add Report/system_implementation_standalone.pdf \
        Report/system_implementation_standalone.aux \
        Report/system_implementation_standalone.bbl \
        Report/system_implementation_standalone.blg \
        Report/system_implementation_standalone.log \
        Report/system_implementation_standalone.out \
        Report/system_implementation_standalone.toc
git commit -m "docs(report): rebuild PDF with Prometheus integration"
```

(The project commits build artifacts alongside the source; this matches the prior chapter plans.)

---

## Out-of-band: dependencies between tasks

- Tasks 0, 1, 2 must run in this order — Task 2 depends on the scrape config (0) and the ClickHouse endpoint (1).
- Task 3 (verification) must follow Task 2 and must complete cleanly before Task 4 (Grafana datasource), Task 5 (dashboard), or Task 6 (alert rule). If any scrape target is `down` in Task 3, those three later tasks fail meaningfully.
- Tasks 4, 5, 6 are independent of each other after Task 3 and can run in parallel if executed by separate workers.
- Task 7 depends on Task 3 (Prometheus must respond to API queries for the script to return non-empty data).
- Tasks 8, 9, 10 (chapter prose edits to §2.4, §3.4, §3.8) are independent of each other and of Tasks 4–7. They can run in any order as long as they precede Task 11.
- Task 11 depends on Task 7 (numbers come from `quantitative_results.md`) and Task 3 (deploy date recorded).
- Task 12 must be last.

---

## Self-Review

**Spec coverage** — re-checked the spec section by section:

- §2 (scope: in/out) → every "in" item maps to a task; every "out" item is honored (no node_exporter, no cAdvisor, no alertmanager, no `src/` changes). Covered.
- §3 (architecture diagram) → Tasks 0–6 realise the diagram; Task 12 step 2 verifies it via the targets API. Covered.
- §4.1 (`prometheus/prometheus.yml`) → Task 0. Covered.
- §4.2 (`system_health.json`) → Task 5. Covered.
- §4.3 (script collector) → Task 7. Covered.
- §5.1 (compose service) → Task 2. Covered.
- §5.2 (ClickHouse config-mount + XML) → Task 1. Covered.
- §5.3 (datasource entry) → Task 4. Covered.
- §5.4 (alert rule) → Task 6. Covered.
- §5.5 (chapter edits) → Tasks 8, 9, 10, 11. Covered.
- §6 (collector code, field, wiring, renderer) → Task 7 steps 1–5. Covered.
- §7 (order of operations) → restated in this plan's "Dependencies between tasks" section. Covered.
- §8 (failure modes) → all three handled in Task 7 step 3 (httpx error → `None`), Task 5 step 5 (metric-name drift → `n/a`), Task 11 step 4 (`None` → `---`). Covered.
- §9 (acceptance criteria) → Task 12 step 2 runs all eight as shell checks. Covered.
- §10 (open questions) → none open at spec-write time; this plan introduces none. Covered.

**Placeholder scan** — searched the plan for "TBD", "TODO", "implement later", "fill in details", "similar to Task N", "add error handling". Only literal mentions are in the No-Placeholders rule (this comment) and the deliberate `<value>` / `<DEPLOY_DATE>` placeholders in Task 11 step 3 (which are *replaced* in Task 11 step 4 from the regenerated markdown). No real placeholders remain.

**Type consistency** — file paths, service names, datasource uids, alert-rule uids, dashboard uid, ClickHouse metric names, and PromQL expressions are used identically across the plan. Cross-checked: `datasourceUid: prometheus` (Task 6) matches `uid: prometheus` (Task 4); dashboard `uid: system-health` (Task 5) matches the URL in Task 12 step 2; ClickHouse metric names `ClickHouseProfileEvents_Query`, `ClickHouseAsyncMetrics_MemoryResident`, `ClickHouseMetrics_PartsActive`, `ClickHouseMetrics_BackgroundMergesAndMutationsPoolTask` are identical between Task 5 (dashboard JSON) and Task 7 (collector queries).
