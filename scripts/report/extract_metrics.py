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
    raise NotImplementedError


def collect_reproducibility(client, window_days: int) -> dict[str, Any]:
    raise NotImplementedError


def collect_feedback_loop(client, window_days: int) -> dict[str, Any]:
    raise NotImplementedError


def collect_dora(window_days: int) -> dict[str, Any]:
    raise NotImplementedError


def render_markdown(report: MetricsReport) -> str:
    raise NotImplementedError


if __name__ == "__main__":
    main()
