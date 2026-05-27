"""Extract quantitative system metrics for the report.

Reads from:
  - ClickHouse (algo.experiment_runs, algo.experiment_predictions,
    algo.drift_reports, algo.retrain_events, algo.timeseries)
  - Local git history
  - GitHub Actions run history via `gh` CLI

Writes a markdown summary to Report/metrics/quantitative_results.md
that the LaTeX chapter transcribes by hand.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from infrastructure_clickhouse.client_factory import create_client

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = REPO_ROOT / "Report" / "metrics" / "quantitative_results.md"
WINDOW_DAYS = 90


@dataclass
class MetricsReport:
    window_days: int
    generated_at_utc: str
    operational: dict[str, Any] = field(default_factory=dict)
    reproducibility: dict[str, Any] = field(default_factory=dict)
    feedback_loop: dict[str, Any] = field(default_factory=dict)
    dora: dict[str, Any] = field(default_factory=dict)


def main() -> None:
    report = MetricsReport(
        window_days=WINDOW_DAYS,
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    client = create_client()
    try:
        report.operational = collect_operational(client, WINDOW_DAYS)
        report.reproducibility = collect_reproducibility(client, WINDOW_DAYS)
        report.feedback_loop = collect_feedback_loop(client, WINDOW_DAYS)
    finally:
        client.close()
    report.dora = collect_dora(WINDOW_DAYS)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(render_markdown(report))
    print(f"Wrote {OUTPUT_PATH}")


def collect_operational(client, window_days: int) -> dict[str, Any]:
    """Run-success, duration percentiles, prediction-actual coverage."""
    # Run counts and training-duration percentiles per (area, model_type)
    rows = client.query(
        """
        SELECT
            area,
            model_type,
            count() AS n_runs,
            quantile(0.50)(training_duration_seconds) AS p50_train_s,
            quantile(0.95)(training_duration_seconds) AS p95_train_s
        FROM algo.experiment_runs FINAL
        WHERE created_utc >= now() - INTERVAL %(d)s DAY
          AND model_artifact_id != ''
        GROUP BY area, model_type
        ORDER BY area, model_type
        """,
        parameters={"d": window_days},
    ).result_rows
    by_config = [
        {
            "area": r[0],
            "model_type": r[1],
            "n_runs": int(r[2]),
            "p50_train_seconds": round(float(r[3]), 1),
            "p95_train_seconds": round(float(r[4]), 1),
        }
        for r in rows
    ]

    # Reconciliation completeness: of live runs whose forecast day is
    # already in the past, what fraction has at least one actual logged
    # in experiment_predictions?
    recon = client.query(
        """
        WITH eligible AS (
            SELECT run_id, data_end_utc
            FROM algo.experiment_runs FINAL
            WHERE created_utc >= now() - INTERVAL %(d)s DAY
              AND model_artifact_id != ''
              -- 2-day buffer: actuals are published ~1 day after delivery; this ensures
              -- a fair denominator for the reconciliation rate.
              AND data_end_utc < now() - INTERVAL 2 DAY
        )
        SELECT
            count() AS eligible_runs,
            countIf(reconciled > 0) AS reconciled_runs
        FROM (
            SELECT
                e.run_id AS run_id,
                -- actual is Float32 (non-nullable); unmatched LEFT JOIN rows default to 0.0,
                -- so actual != 0 is a proxy for "reconciled". Small false-negative risk on
                -- legitimate zero-price hours, which are uncommon in the European day-ahead market.
                countIf(p.actual IS NOT NULL AND p.actual != 0) AS reconciled
            FROM eligible e
            LEFT JOIN algo.experiment_predictions p ON p.run_id = e.run_id
            GROUP BY e.run_id
        )
        """,
        parameters={"d": window_days},
    ).result_rows[0]
    eligible, reconciled = int(recon[0]), int(recon[1])
    return {
        "by_config": by_config,
        "reconciliation": {
            "eligible_runs": eligible,
            "reconciled_runs": reconciled,
            "reconciliation_rate_pct": round(100.0 * reconciled / eligible, 1) if eligible else None,
        },
    }


def collect_reproducibility(client, window_days: int) -> dict[str, Any]:
    """Coverage of the provenance triple (git_sha, data_window, artifact)."""
    row = client.query(
        """
        SELECT
            count() AS total,
            countIf(git_sha != '') AS with_sha,
            countIf(data_start_utc > toDateTime('1970-01-02', 'UTC')) AS with_data_start,
            countIf(data_end_utc > toDateTime('1970-01-02', 'UTC')) AS with_data_end,
            countIf(model_artifact_id != '') AS with_artifact,
            countIf(
                git_sha != ''
                AND data_start_utc > toDateTime('1970-01-02', 'UTC')
                AND data_end_utc > toDateTime('1970-01-02', 'UTC')
                AND model_artifact_id != ''
            ) AS with_full_triple
        FROM algo.experiment_runs FINAL
        WHERE created_utc >= now() - INTERVAL %(d)s DAY
          AND model_artifact_id != ''
        """,
        parameters={"d": window_days},
    ).result_rows[0]
    total = int(row[0])
    return {
        "total_runs": total,
        "with_git_sha_pct": round(100.0 * int(row[1]) / total, 1) if total else None,
        "with_data_start_pct": round(100.0 * int(row[2]) / total, 1) if total else None,
        "with_data_end_pct": round(100.0 * int(row[3]) / total, 1) if total else None,
        "with_artifact_pct": round(100.0 * int(row[4]) / total, 1) if total else None,
        "with_full_triple_pct": round(100.0 * int(row[5]) / total, 1) if total else None,
    }


def collect_feedback_loop(client, window_days: int) -> dict[str, Any]:
    """Drift event counts over the window (reports written + detections)."""
    drift_row = client.query(
        """
        SELECT
            count() AS reports,
            countIf(drift_detected = 1) AS detections
        FROM algo.drift_reports FINAL
        WHERE created_utc >= now() - INTERVAL %(d)s DAY
        """,
        parameters={"d": window_days},
    ).result_rows[0]
    return {
        "drift_reports": int(drift_row[0]),
        "drift_detections": int(drift_row[1]),
    }


def collect_dora(window_days: int) -> dict[str, Any]:
    """DORA delivery throughput: deployment frequency and lead time.

    Source of truth is the GitHub Actions cd_deploy.yml workflow history,
    treated as one deploy per successful run. Lead time approximated as
    the wall time between the PR merge commit and the cd_deploy run start.
    """
    # Definition: a "deployment" is a successful cd_deploy.yml run on main.
    # DORA THROUGHPUT ONLY: deployment frequency + lead time. Change failure
    # rate and MTTR are intentionally NOT computed — they require an incident
    # corpus the study window does not provide (see spec / chapter prose).
    since = (datetime.now(timezone.utc) - timedelta(days=window_days)).strftime("%Y-%m-%d")
    raw = subprocess.run(
        [
            "gh", "run", "list",
            "--workflow", "cd_deploy.yml",
            "--branch", "main",
            "--limit", "200",
            "--created", f">={since}",
            "--json", "conclusion,startedAt,createdAt,headSha",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    runs = json.loads(raw.stdout)
    if len(runs) == 200:
        print(
            "WARNING: gh run list returned exactly 200 rows — the limit may "
            "have been hit. DORA numbers below may be truncated.",
            file=sys.stderr,
        )
    successes = [r for r in runs if r["conclusion"] == "success"]
    deploy_freq_per_week = round(7 * len(successes) / window_days, 2) if window_days else None

    lead_times_minutes: list[float] = []
    for r in successes:
        sha = r["headSha"]
        try:
            ts = subprocess.run(
                ["git", "show", "-s", "--format=%cI", sha],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
        except subprocess.CalledProcessError:
            continue
        if not ts:
            continue
        commit_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        run_dt = datetime.fromisoformat(r["startedAt"].replace("Z", "+00:00"))
        lead_times_minutes.append((run_dt - commit_dt).total_seconds() / 60.0)
    lead_times_minutes.sort()

    def pct(xs: list[float], q: float) -> float | None:
        if not xs:
            return None
        idx = max(0, min(len(xs) - 1, int(round(q * (len(xs) - 1)))))
        return round(xs[idx], 1)

    return {
        "window_days": window_days,
        "deployments_success": len(successes),
        "deploy_frequency_per_week": deploy_freq_per_week,
        "lead_time_minutes_p50": pct(lead_times_minutes, 0.5),
        "lead_time_minutes_p95": pct(lead_times_minutes, 0.95),
    }


def render_markdown(report: MetricsReport) -> str:
    out: list[str] = []
    out.append("# Quantitative System Metrics\n")
    out.append(f"_Window: last {report.window_days} days. Generated: {report.generated_at_utc}._\n")

    out.append("\n## Operational metrics\n")
    out.append("\n### Per-config training duration and run counts\n")
    out.append("\n| Area | Model | Runs | p50 train (s) | p95 train (s) |")
    out.append("\n|---|---|---|---|---|")
    for c in report.operational.get("by_config", []):
        out.append(
            f"\n| {c['area']} | {c['model_type']} | {c['n_runs']} | "
            f"{c['p50_train_seconds']} | {c['p95_train_seconds']} |"
        )
    rec = report.operational.get("reconciliation", {})
    out.append("\n\n### Reconciliation completeness\n")
    out.append(
        f"\n- Eligible runs (forecast day already in the past by ≥2 days): **{rec.get('eligible_runs')}**"
    )
    out.append(f"\n- Reconciled (at least one actual logged): **{rec.get('reconciled_runs')}**")
    out.append(f"\n- Reconciliation rate: **{rec.get('reconciliation_rate_pct')}%**")

    out.append("\n\n## Reproducibility coverage\n")
    r = report.reproducibility
    out.append(f"\n- Total live runs in window: **{r.get('total_runs')}**")
    out.append(f"\n- With non-empty `git_sha`: **{r.get('with_git_sha_pct')}%**")
    out.append(f"\n- With `data_start_utc` populated: **{r.get('with_data_start_pct')}%**")
    out.append(f"\n- With `data_end_utc` populated: **{r.get('with_data_end_pct')}%**")
    out.append(f"\n- With `model_artifact_id` populated: **{r.get('with_artifact_pct')}%**")
    out.append(f"\n- With the full provenance triple: **{r.get('with_full_triple_pct')}%**")

    out.append("\n\n## Drift monitoring\n")
    f = report.feedback_loop
    out.append(f"\n- Drift reports written: **{f.get('drift_reports')}**")
    out.append(f"\n- Drift detections (`drift_detected = 1`): **{f.get('drift_detections')}**")

    out.append("\n\n## DORA delivery throughput\n")
    d = report.dora
    out.append(f"\n- Successful deployments in window: **{d.get('deployments_success')}**")
    out.append(f"\n- Deploy frequency: **{d.get('deploy_frequency_per_week')}/week**")
    out.append(f"\n- Lead time PR-merge → cd_deploy start (p50): **{d.get('lead_time_minutes_p50')} min**")
    out.append(f"\n- Lead time (p95): **{d.get('lead_time_minutes_p95')} min**")
    out.append("\n- Change failure rate / MTTR: **not reported** (no incident corpus in window)")

    out.append("\n")
    return "".join(out)


if __name__ == "__main__":
    main()
