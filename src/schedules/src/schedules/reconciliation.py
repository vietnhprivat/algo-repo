"""Reconciliation flow.

Backfills actual prices from algo.timeseries into live prediction rows
(where actual=0.0 at prediction time) and computes accuracy metrics
(MAE, RMSE, sMAPE), storing them in experiment_runs.metrics_json.

Runs daily after ENTSO-E day-ahead prices have been published.
"""

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np
import polars as pl
from prefect import flow, task

from infrastructure_clickhouse.client_factory import create_client
from infrastructure_clickhouse.ingest import (
    insert_experiment_predictions,
    insert_experiment_run,
)
from infrastructure_clickhouse.logging_setup import build_log_extra, get_logger
from infrastructure_clickhouse.queries import (
    get_actual_prices_for_period,
    get_predictions_for_runs,
    get_recent_accuracy,
    get_unreconciled_runs,
)
from price_forecasting.evaluation import (
    calculate_mae,
    calculate_rmse,
    calculate_smape,
)
from observability_wandb.tracker import WandbTracker
from schedules.alerting import notify

LOGGER = get_logger(__name__, service="prefect-reconciliation")


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime is UTC-aware; clickhouse-connect returns tz-aware values
    for DateTime('UTC') columns, but be defensive."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _log_run_to_wandb(
    *,
    tracker: WandbTracker,
    area: str,
    config_name: str,
    target_date: str,
    metrics: dict[str, float],
    model_artifact_id: str | None = None,
) -> None:
    # ClickHouse stores model_artifact_id as a non-nullable String; old rows have
    # the empty string. Treat blanks as absent so the W&B payload stays clean.
    cleaned = model_artifact_id if model_artifact_id else None
    tracker.log_prod_reconciled(
        area=area,
        config_name=config_name,
        target_date=target_date,
        metrics=metrics,
        model_artifact_id=cleaned,
    )


@task(log_prints=True)
def find_unreconciled_runs_task() -> list[dict]:
    client = create_client()
    try:
        runs = get_unreconciled_runs(client)
    finally:
        client.close()
    LOGGER.info("Loaded unreconciled runs", extra=build_log_extra(run_count=len(runs)))
    print(f"Found {len(runs)} unreconciled run(s)")
    return runs


@task(retries=2, retry_delay_seconds=60, log_prints=True)
def reconcile_area_task(area: str, runs: list[dict]) -> dict:
    """Reconcile all unreconciled runs for a single area in one batch.

    Fetches predictions and actuals with one query each, then for each run
    matches predictions to actuals, computes metrics, and re-inserts the
    updated rows (ReplacingMergeTree deduplication handles the upsert).
    """
    tracker = WandbTracker()
    client = create_client()
    try:
        LOGGER.info(
            "Starting area reconciliation batch",
            extra=build_log_extra(area=area),
        )
        run_ids = [r["run_id"] for r in runs]
        predictions = get_predictions_for_runs(client, run_ids)
        if not predictions:
            LOGGER.warning(
                "No predictions found for reconciliation runs",
                extra=build_log_extra(area=area),
            )
            print(f"[{area}] No predictions found for runs")
            return {"area": area, "reconciled": 0, "skipped": 0}

        # Determine time range for a single actuals query (min prediction ts to
        # max prediction ts + 1 hour buffer to ensure inclusive fetch)
        all_timestamps = [_ensure_utc(p["timestamp_utc"]) for p in predictions]
        min_ts = min(all_timestamps)
        max_ts = max(all_timestamps) + timedelta(hours=1)

        actuals = get_actual_prices_for_period(client, area, min_ts, max_ts)
        actuals_lookup: dict[datetime, float] = {
            _ensure_utc(a["timestamp_utc"]): float(a["price"]) for a in actuals
        }
        LOGGER.info(
            "Loaded actual prices for reconciliation",
            extra=build_log_extra(area=area),
        )
        print(f"[{area}] Loaded {len(actuals_lookup)} actual price points")

        # Group predictions by run_id — cast to str because clickhouse-connect
        # may return LowCardinality(String) as a Python object, not a plain str.
        preds_by_run: dict[str, list[dict]] = defaultdict(list)
        for p in predictions:
            preds_by_run[str(p["run_id"])].append(p)

        reconciled = 0
        skipped = 0
        now = datetime.now(timezone.utc)
        baseline_cache: dict[str, float | None] = {}

        for run in runs:
            run_id = str(run["run_id"])
            run_preds = preds_by_run.get(run_id, [])
            if not run_preds:
                LOGGER.warning(
                    "Reconciliation run has no prediction rows",
                    extra=build_log_extra(area=area, run_id=run_id),
                )
                print(f"[{area}] Run {run_id}: no predictions, skipping")
                skipped += 1
                continue

            # Match each prediction to an actual
            rows = []
            missing = 0
            for p in run_preds:
                ts = _ensure_utc(p["timestamp_utc"])
                actual = actuals_lookup.get(ts)
                if actual is None:
                    missing += 1
                    continue
                rows.append(
                    {
                        "run_id": str(run_id),
                        "timestamp_utc": ts,
                        "actual": float(actual),
                        "predicted": float(p["predicted"]),
                    }
                )

            if missing > 0:
                LOGGER.warning(
                    "Reconciliation skipped because actuals are incomplete",
                    extra=build_log_extra(area=area, run_id=run_id),
                )
                print(
                    f"[{area}] Run {run_id}: missing {missing}/{len(run_preds)} "
                    "actuals, skipping (will retry tomorrow)"
                )
                skipped += 1
                continue

            # Re-insert predictions with actuals backfilled
            updated_preds_df = pl.DataFrame(
                rows,
                schema={
                    "run_id": pl.String,
                    "timestamp_utc": pl.Datetime("us", "UTC"),
                    "actual": pl.Float32,
                    "predicted": pl.Float32,
                },
            )
            insert_experiment_predictions(client, updated_preds_df)

            # Compute metrics from flat arrays
            actuals_arr = np.array([r["actual"] for r in rows], dtype=float)
            predicted_arr = np.array([r["predicted"] for r in rows], dtype=float)
            metrics = {
                "mae": float(calculate_mae(actuals_arr, predicted_arr)),
                "rmse": float(calculate_rmse(actuals_arr, predicted_arr)),
                "smape": float(calculate_smape(actuals_arr, predicted_arr)),
            }
            metrics_json = json.dumps(metrics)

            # Re-insert experiment_run with updated metrics_json + new created_utc
            # so ReplacingMergeTree(created_utc) keeps this as the winning row.
            insert_experiment_run(
                client,
                run_id=run_id,
                created_utc=now,
                experiment_name=run["experiment_name"],
                area=run["area"],
                model_type=run["model_type"],
                config_json=run["config_json"],
                metrics_json=metrics_json,
                training_duration_seconds=run["training_duration_seconds"],
                data_start_utc=_ensure_utc(run["data_start_utc"]),
                data_end_utc=_ensure_utc(run["data_end_utc"]),
                model_artifact_id=run["model_artifact_id"],
                git_sha=run["git_sha"],
            )

            LOGGER.info(
                "Reconciled live prediction run",
                extra=build_log_extra(area=area, run_id=run_id),
            )
            print(
                f"[{area}] Run {run_id}: reconciled {len(rows)} periods, "
                f"mae={metrics['mae']:.2f}, rmse={metrics['rmse']:.2f}, "
                f"smape={metrics['smape']:.2f}"
            )
            reconciled += 1

            config_name = run["experiment_name"]
            target_date = min(r["timestamp_utc"] for r in rows).strftime("%Y-%m-%d")
            try:
                _log_run_to_wandb(
                    tracker=tracker,
                    area=area,
                    config_name=config_name,
                    target_date=target_date,
                    metrics=metrics,
                    model_artifact_id=run.get("model_artifact_id"),
                )
            except Exception as exc:
                LOGGER.warning(
                    "W&B prod-sync failed; continuing",
                    extra=build_log_extra(
                        area=area, config_name=config_name, error=str(exc),
                    ),
                )
            if config_name not in baseline_cache:
                try:
                    baseline_cache[config_name] = get_recent_accuracy(
                        client, area, config_name
                    )
                except Exception as exc:
                    LOGGER.warning(
                        "Failed to fetch accuracy baseline; skipping alert",
                        extra=build_log_extra(
                            area=area, config_name=config_name, error=str(exc),
                        ),
                    )
                    baseline_cache[config_name] = None
            try:
                _maybe_alert_accuracy_degradation(
                    area=area,
                    config_name=config_name,
                    today_mae=metrics["mae"],
                    baseline_median_mae=baseline_cache[config_name],
                )
            except Exception as exc:
                LOGGER.warning(
                    "Accuracy-degradation alert failed; continuing",
                    extra=build_log_extra(
                        area=area, config_name=config_name, error=str(exc),
                    ),
                )
    finally:
        client.close()

    return {"area": area, "reconciled": reconciled, "skipped": skipped}


def _maybe_alert_accuracy_degradation(
    *,
    area: str,
    config_name: str,
    today_mae: float,
    baseline_median_mae: float | None,
    threshold_multiplier: float = 1.5,
) -> None:
    """Slack-alert when today's MAE is >threshold_multiplier × baseline median."""
    if baseline_median_mae is None or baseline_median_mae <= 0:
        return
    if today_mae <= threshold_multiplier * baseline_median_mae:
        return
    notify(
        subject=f"Accuracy degradation on {area} ({config_name})",
        message=(
            f"Today's MAE {today_mae:.2f} > {threshold_multiplier}× 30-day median "
            f"{baseline_median_mae:.2f}. Investigate."
        ),
        severity="warning",
    )


@flow(name="reconcile-predictions", log_prints=True)
def reconcile_predictions_flow() -> dict:
    runs = find_unreconciled_runs_task()
    if not runs:
        LOGGER.info("No unreconciled runs found")
        print("No unreconciled runs — nothing to do")
        return {"total_runs": 0, "areas": {}}

    runs_by_area: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        runs_by_area[run["area"]].append(run)

    LOGGER.info("Starting reconciliation flow", extra=build_log_extra(run_count=len(runs)))
    print(f"Reconciling {len(runs)} run(s) across {len(runs_by_area)} area(s)")

    area_results = {}
    for area, area_runs in runs_by_area.items():
        area_results[area] = reconcile_area_task(area, area_runs)

    total_reconciled = sum(r["reconciled"] for r in area_results.values())
    total_skipped = sum(r["skipped"] for r in area_results.values())
    LOGGER.info(
        "Completed reconciliation flow",
        extra=build_log_extra(
            total_reconciled=total_reconciled,
            total_skipped=total_skipped,
        ),
    )
    print(
        f"Reconciliation complete: {total_reconciled} reconciled, "
        f"{total_skipped} skipped"
    )

    return {
        "total_runs": len(runs),
        "total_reconciled": total_reconciled,
        "total_skipped": total_skipped,
        "areas": area_results,
    }


if __name__ == "__main__":
    reconcile_predictions_flow()
