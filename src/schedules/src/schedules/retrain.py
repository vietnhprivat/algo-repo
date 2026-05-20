"""Drift-triggered retrain flow.

Invoked from the drift detection flow when retrain_on_drift=True on the
matching config. Re-runs daily_forecast_flow for tomorrow and writes an
audit row to algo.retrain_events.
"""
import uuid
from datetime import datetime, timezone

from prefect import flow

from infrastructure_clickhouse.client_factory import create_client
from infrastructure_clickhouse.logging_setup import build_log_extra, get_logger
from schedules.forecast import daily_forecast_flow

LOGGER = get_logger(__name__, service="prefect-retrain")


def _insert_retrain_event(**kwargs) -> None:
    """Insert one row into algo.retrain_events. Indirected via free function
    so tests can monkeypatch without touching ClickHouse.

    `updated_utc` is the ReplacingMergeTree version key — callers must pass a
    strictly later value on each re-insert for the same event_id so the
    terminal status row wins deduplication.
    """
    client = create_client()
    try:
        client.insert(
            "algo.retrain_events",
            [[
                kwargs["event_id"], kwargs["created_utc"], kwargs["updated_utc"],
                kwargs["triggered_by"], kwargs["area"], kwargs["config_name"],
                kwargs.get("drift_report_id"), kwargs["status"],
                kwargs.get("completed_utc"), kwargs.get("new_run_id"),
                kwargs.get("notes"),
            ]],
            column_names=[
                "event_id", "created_utc", "updated_utc", "triggered_by", "area",
                "config_name", "drift_report_id", "status", "completed_utc",
                "new_run_id", "notes",
            ],
        )
    finally:
        client.close()


@flow(name="triggered-retrain", log_prints=True)
def triggered_retrain_flow(
    config_name: str, triggered_by: str = "manual",
    drift_report_id: str | None = None, area: str = "",
) -> dict:
    event_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc)
    LOGGER.info(
        "Starting triggered retrain",
        extra=build_log_extra(
            config_name=config_name, triggered_by=triggered_by,
            drift_report_id=drift_report_id, event_id=event_id,
        ),
    )
    _insert_retrain_event(
        event_id=event_id, created_utc=started, updated_utc=started,
        triggered_by=triggered_by, area=area, config_name=config_name,
        drift_report_id=drift_report_id, status="running",
    )
    try:
        forecast_result = daily_forecast_flow(config_name=config_name)
    except Exception as exc:
        failed_at = datetime.now(timezone.utc)
        _insert_retrain_event(
            event_id=event_id, created_utc=started, updated_utc=failed_at,
            triggered_by=triggered_by, area=area, config_name=config_name,
            drift_report_id=drift_report_id, status="failed",
            completed_utc=failed_at, notes=str(exc)[:500],
        )
        raise

    completed_at = datetime.now(timezone.utc)
    _insert_retrain_event(
        event_id=event_id, created_utc=started, updated_utc=completed_at,
        triggered_by=triggered_by, area=area, config_name=config_name,
        drift_report_id=drift_report_id, status="completed",
        completed_utc=completed_at, new_run_id=forecast_result.get("run_id"),
    )
    return {"event_id": event_id, "status": "completed",
            "new_run_id": forecast_result.get("run_id")}
