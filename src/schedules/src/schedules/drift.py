"""Drift detection flow.

Runs a Kolmogorov-Smirnov test (via Evidently's ``DataDriftPreset``) on the
day-ahead energy price for the given area, comparing the current 7-day window
to a 90-day reference window. Stores the result in ``algo.drift_reports`` and
emits a WARNING structured log entry when the KS p-value crosses the
significance threshold (drift detected).

Scheduled daily after the reconciliation flow so the latest actuals are in
place. See researh_material/mlops_implementation_plan.md Phase 4.
"""

from __future__ import annotations

import importlib.util
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
from evidently import DataDefinition, Dataset, Report
from evidently.presets import DataDriftPreset
from prefect import flow, task

from infrastructure_clickhouse.client_factory import create_client
from infrastructure_clickhouse.ingest import insert_drift_report
from infrastructure_clickhouse.logging_setup import build_log_extra, get_logger
from infrastructure_clickhouse.queries import get_actual_prices_for_period
from observability_wandb.tracker import WandbTracker
from schedules.retrain import triggered_retrain_flow

LOGGER = get_logger(__name__, service="prefect-drift")

REFERENCE_DAYS = 90
CURRENT_DAYS = 7
MIN_SAMPLE_SIZE = 30
TARGET_COLUMN = "price"
_VALUE_DRIFT_METRIC_TYPE = "evidently:metric_v2:ValueDrift"
_DRIFTED_COLUMNS_COUNT_METRIC_TYPE = "evidently:metric_v2:DriftedColumnsCount"


@dataclass
class DriftWindows:
    reference_start: datetime
    reference_end: datetime
    current_start: datetime
    current_end: datetime


def _compute_windows(now: datetime) -> DriftWindows:
    """Derive the reference and current windows ending at the last full UTC day.

    Current window: ``[today - 7, today)`` (midnights UTC).
    Reference window: ``[today - 97, today - 7)`` — the 90 days immediately
    preceding the current window, with no overlap.
    """
    today_utc = now.astimezone(timezone.utc).date()
    current_end = datetime.combine(today_utc, datetime.min.time(), tzinfo=timezone.utc)
    current_start = current_end - timedelta(days=CURRENT_DAYS)
    reference_end = current_start
    reference_start = reference_end - timedelta(days=REFERENCE_DAYS)
    return DriftWindows(
        reference_start=reference_start,
        reference_end=reference_end,
        current_start=current_start,
        current_end=current_end,
    )


def _compute_drift(
    reference_prices: list[float], current_prices: list[float]
) -> tuple[float, float, str, bool]:
    """Return ``(drift_score, drift_threshold, stat_test_label, drift_detected)``.

    Evidently's ``DataDriftPreset`` auto-selects the statistical test based on
    sample size (e.g. K-S p-value for small samples, Wasserstein distance for
    large ones). Each test has its own threshold direction, so we read the
    boolean verdict from the preset's ``DriftedColumnsCount`` summary instead
    of comparing score vs threshold ourselves.
    """
    ref_df = pd.DataFrame({TARGET_COLUMN: reference_prices})
    cur_df = pd.DataFrame({TARGET_COLUMN: current_prices})
    data_def = DataDefinition(numerical_columns=[TARGET_COLUMN])
    ref_ds = Dataset.from_pandas(ref_df, data_definition=data_def)
    cur_ds = Dataset.from_pandas(cur_df, data_definition=data_def)
    report = Report([DataDriftPreset()])
    result = report.run(reference_data=ref_ds, current_data=cur_ds)

    drift_score: float | None = None
    drift_threshold: float | None = None
    stat_test: str | None = None
    drifted_count: int | None = None
    for metric in result.dict().get("metrics", []):
        config = metric.get("config", {})
        metric_type = config.get("type")
        if metric_type == _VALUE_DRIFT_METRIC_TYPE:
            drift_score = float(metric["value"])
            drift_threshold = float(config.get("threshold", 0.0))
            stat_test = str(config.get("method", "auto"))
        elif metric_type == _DRIFTED_COLUMNS_COUNT_METRIC_TYPE:
            drifted_count = int(metric["value"]["count"])

    if drift_score is None or drift_threshold is None or stat_test is None:
        raise RuntimeError(
            "Evidently DataDriftPreset report did not contain a ValueDrift metric"
        )
    if drifted_count is None:
        raise RuntimeError(
            "Evidently DataDriftPreset report did not contain a "
            "DriftedColumnsCount metric"
        )
    return drift_score, drift_threshold, stat_test, drifted_count > 0


def _log_drift_to_wandb(
    *,
    tracker: WandbTracker,
    area: str,
    curve_name: str,
    target_date: str,
    drift_score: float,
    drift_threshold: float,
    stat_test: str,
    drift_detected: bool,
) -> None:
    try:
        tracker.log_drift_event(
            area=area,
            curve_name=curve_name,
            target_date=target_date,
            drift_score=drift_score,
            drift_threshold=drift_threshold,
            stat_test=stat_test,
            drift_detected=drift_detected,
        )
    except Exception as exc:  # noqa: BLE001 — never crash the drift flow over W&B
        LOGGER.warning(
            "W&B drift-event sync failed; continuing",
            extra=build_log_extra(area=area, curve_name=curve_name, error=str(exc)),
        )


@task(retries=2, retry_delay_seconds=60, log_prints=True)
def detect_drift_for_area_task(area: str) -> dict:
    """Fetch both windows, compute drift via Evidently, persist, and log."""
    windows = _compute_windows(datetime.now(timezone.utc))
    # get_actual_prices_for_period matches any ENTSOE {area} EnergyPrice % curve;
    # the stored label reflects that LIKE pattern rather than a single resolution.
    curve_name = f"ENTSOE {area} EnergyPrice"

    LOGGER.info(
        "Starting drift detection",
        extra=build_log_extra(
            area=area,
            chunk_start=windows.reference_start.isoformat(),
            chunk_end=windows.current_end.isoformat(),
        ),
    )
    print(
        f"[{area}] Drift windows: "
        f"ref {windows.reference_start.date()}..{windows.reference_end.date()}, "
        f"cur {windows.current_start.date()}..{windows.current_end.date()}"
    )

    client = create_client()
    try:
        ref_rows = get_actual_prices_for_period(
            client, area, windows.reference_start, windows.reference_end
        )
        cur_rows = get_actual_prices_for_period(
            client, area, windows.current_start, windows.current_end
        )
        reference_prices = [float(r["price"]) for r in ref_rows]
        current_prices = [float(r["price"]) for r in cur_rows]

        if (
            len(reference_prices) < MIN_SAMPLE_SIZE
            or len(current_prices) < MIN_SAMPLE_SIZE
        ):
            LOGGER.warning(
                "Skipping drift check: insufficient samples",
                extra=build_log_extra(
                    area=area,
                    row_count=len(reference_prices) + len(current_prices),
                ),
            )
            print(
                f"[{area}] Insufficient data: ref={len(reference_prices)}, "
                f"cur={len(current_prices)}, skipping"
            )
            return {
                "area": area,
                "status": "skipped_insufficient_samples",
                "reference_n": len(reference_prices),
                "current_n": len(current_prices),
            }

        drift_score, drift_threshold, stat_test, drift_detected = _compute_drift(
            reference_prices, current_prices
        )

        now = datetime.now(timezone.utc)
        report_id = str(uuid.uuid4())
        insert_drift_report(
            client,
            report_id=report_id,
            created_utc=now,
            area=area,
            curve_name=curve_name,
            reference_start_utc=windows.reference_start,
            reference_end_utc=windows.reference_end,
            current_start_utc=windows.current_start,
            current_end_utc=windows.current_end,
            stat_test=stat_test,
            drift_score=drift_score,
            drift_threshold=drift_threshold,
            drift_detected=drift_detected,
            reference_n=len(reference_prices),
            current_n=len(current_prices),
        )
        _log_drift_to_wandb(
            tracker=WandbTracker(),
            area=area,
            curve_name=curve_name,
            target_date=windows.current_end.date().isoformat(),
            drift_score=drift_score,
            drift_threshold=drift_threshold,
            stat_test=stat_test,
            drift_detected=drift_detected,
        )
    finally:
        client.close()

    log_extra = build_log_extra(area=area)
    score_vs_threshold = f"{stat_test}={drift_score:.4g} (threshold={drift_threshold})"
    if drift_detected:
        LOGGER.warning(f"Drift detected: {score_vs_threshold}", extra=log_extra)
        print(f"[{area}] DRIFT DETECTED: {score_vs_threshold}")
        from schedules.alerting import notify
        notify(
            subject=f"Drift detected on {area}",
            message=f"{score_vs_threshold}; report_id={report_id}",
            severity="warning",
        )
        _maybe_trigger_retrain(
            area=area, drift_detected=True, drift_report_id=report_id,
        )
    else:
        LOGGER.info(f"No drift: {score_vs_threshold}", extra=log_extra)
        print(f"[{area}] No drift: {score_vs_threshold}")

    return {
        "area": area,
        "status": "detected" if drift_detected else "ok",
        "drift_score": drift_score,
        "drift_threshold": drift_threshold,
        "stat_test": stat_test,
        "report_id": report_id,
        "reference_n": len(reference_prices),
        "current_n": len(current_prices),
    }


@flow(name="drift-detection", log_prints=True)
def drift_detection_flow(area: str = "DK1") -> dict:
    return detect_drift_for_area_task(area)


def _configs_for_area(area: str):
    """Return configs whose area matches and retrain_on_drift is True."""
    matches = []
    configs_dir = Path("/app/configs")
    if not configs_dir.exists():
        configs_dir = Path.cwd() / "configs"
    for py in configs_dir.glob("*.py"):
        spec = importlib.util.spec_from_file_location(py.stem, py)
        if not spec or not spec.loader:
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception:
            continue
        config = getattr(module, "config", None)
        if config is None:
            continue
        if getattr(config, "area", None) == area and getattr(config, "retrain_on_drift", False):
            matches.append(config)
    return matches


def _maybe_trigger_retrain(*, area: str, drift_detected: bool, drift_report_id: str | None) -> None:
    if not drift_detected:
        return
    for config in _configs_for_area(area):
        if not getattr(config, "retrain_on_drift", False):
            continue
        LOGGER.info(
            "Triggering retrain for config due to drift",
            extra=build_log_extra(
                area=area, config_name=config.experiment_name,
                drift_report_id=drift_report_id,
            ),
        )
        triggered_retrain_flow(
            config_name=config.experiment_name, triggered_by="drift",
            drift_report_id=drift_report_id, area=area,
        )


if __name__ == "__main__":
    drift_detection_flow()
