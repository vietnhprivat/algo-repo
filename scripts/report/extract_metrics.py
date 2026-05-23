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
    raise NotImplementedError


def collect_dora(window_days: int) -> dict[str, Any]:
    raise NotImplementedError


def render_markdown(report: MetricsReport) -> str:
    raise NotImplementedError


if __name__ == "__main__":
    main()
