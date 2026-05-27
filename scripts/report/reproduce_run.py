"""Reproducibility demonstration for the report.

Re-runs a logged forecast from its committed config + target date and compares
the re-run prediction against the prediction stored in
algo.experiment_predictions, reporting the max absolute difference.

Usage:
    uv run python -m scripts.report.reproduce_run --config dk1_lear --date 2026-03-20
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

import numpy as np

from forecast_cli.config_loader import load_config
from infrastructure_clickhouse.client_factory import create_client
from price_forecasting import LiveRunner


def max_abs_diff(a: Sequence[float], b: Sequence[float]) -> float:
    """Max absolute elementwise difference between two equal-length sequences."""
    arr_a = np.asarray(a, dtype=float)
    arr_b = np.asarray(b, dtype=float)
    if arr_a.shape != arr_b.shape:
        raise ValueError(f"shape mismatch: {arr_a.shape} vs {arr_b.shape}")
    return float(np.max(np.abs(arr_a - arr_b)))


def fetch_stored_prediction(client, config_name: str, area: str, target_date: str) -> tuple[str | None, list[float] | None]:
    """Return (run_id, [predicted...]) for the most recent run of this config
    that has predictions on target_date, or (None, None)."""
    runs = client.query(
        """
        SELECT run_id FROM algo.experiment_runs FINAL
        WHERE experiment_name = {cfg:String} AND area = {area:String}
        ORDER BY created_utc DESC
        LIMIT 50
        """,
        parameters={"cfg": config_name, "area": area},
    ).result_rows
    for (run_id,) in runs:
        rows = client.query(
            """
            SELECT timestamp_utc, predicted FROM algo.experiment_predictions FINAL
            WHERE run_id = {rid:String} AND toDate(timestamp_utc) = {d:Date}
            ORDER BY timestamp_utc
            """,
            parameters={"rid": run_id, "d": target_date},
        ).result_rows
        if rows:
            return run_id, [float(r[1]) for r in rows]
    return None, None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="config name, e.g. dk1_lear")
    parser.add_argument("--date", required=True, help="target date YYYY-MM-DD")
    args = parser.parse_args()

    config = load_config(args.config)
    client = create_client()
    try:
        run_id, stored = fetch_stored_prediction(
            client, config.experiment_name, config.area, args.date
        )
    finally:
        client.close()

    if stored is None:
        print(
            f"No stored prediction found for config={args.config} area={config.area} "
            f"date={args.date}. Pick a date that has a logged run.",
            file=sys.stderr,
        )
        return 2

    result = LiveRunner(config).run_live_with_metadata(args.date)
    rerun = list(result.prediction.values)

    diff = max_abs_diff(rerun, stored)
    print(f"config={args.config} area={config.area} date={args.date}")
    print(f"matched run_id={run_id}")
    print(f"periods={len(stored)}  max_abs_diff={diff:.6f}")
    print("REPRODUCED (max abs diff < 1e-4)" if diff < 1e-4 else f"DIFF {diff:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
