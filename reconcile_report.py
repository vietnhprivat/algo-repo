"""Throwaway: reconcile all unreconciled runs (no Prefect server) and print
a per-run results table for runs created today. Safe to delete.

Usage: uv run python reconcile_report.py
"""

from __future__ import annotations

import json
from collections import defaultdict

from infrastructure_clickhouse.client_factory import create_client
from schedules.reconciliation import (
    find_unreconciled_runs_task,
    reconcile_area_task,
)


def reconcile() -> None:
    runs = find_unreconciled_runs_task.fn()
    print(f"unreconciled runs: {len(runs)}")
    by_area: dict[str, list] = defaultdict(list)
    for r in runs:
        by_area[r["area"]].append(r)
    for area, area_runs in by_area.items():
        res = reconcile_area_task.fn(area, area_runs)
        print(f"  {area}: {res}")


def report() -> None:
    c = create_client()
    # target date per run = date of its earliest prediction timestamp
    q = """
        SELECT r.experiment_name AS cfg, r.area AS area,
               toDate(p.min_ts) AS target_date,
               r.metrics_json AS metrics, r.created_utc AS created
        FROM (
            SELECT run_id, min(timestamp_utc) AS min_ts,
                   countIf(actual != 0) AS matched, count() AS n
            FROM algo.experiment_predictions FINAL GROUP BY run_id
        ) p
        INNER JOIN algo.experiment_runs FINAL r ON r.run_id = p.run_id
        WHERE r.created_utc >= today()
        ORDER BY cfg, target_date
    """
    rows = c.query(q).result_rows
    print(f"\n{'config':18}{'date':12}{'MAE':>9}{'RMSE':>9}{'sMAPE':>9}")
    print("-" * 57)
    agg: dict[str, list] = defaultdict(list)
    for cfg, area, td, metrics, created in rows:
        m = json.loads(metrics) if metrics else {}
        mae = m.get("mae")
        rmse = m.get("rmse")
        smape = m.get("smape")
        if mae is None:
            print(f"{cfg:18}{str(td):12}{'(unreconciled)':>27}")
            continue
        print(f"{cfg:18}{str(td):12}{mae:>9.3f}{rmse:>9.3f}{smape:>9.3f}")
        agg[cfg].append((mae, rmse, smape))
    print("\n=== mean over replayed days ===")
    print(f"{'config':18}{'n':>4}{'MAE':>9}{'RMSE':>9}{'sMAPE':>9}")
    for cfg, vals in sorted(agg.items()):
        n = len(vals)
        mae = sum(v[0] for v in vals) / n
        rmse = sum(v[1] for v in vals) / n
        smape = sum(v[2] for v in vals) / n
        print(f"{cfg:18}{n:>4}{mae:>9.3f}{rmse:>9.3f}{smape:>9.3f}")
    c.close()


if __name__ == "__main__":
    reconcile()
    report()
