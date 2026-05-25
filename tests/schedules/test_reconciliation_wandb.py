"""Reconciliation pushes daily reconciled metrics to W&B `algo-prod`."""

from __future__ import annotations

import pytest

from observability_wandb.tracker import WandbTracker

from tests.observability_wandb.conftest import FakeWandb


@pytest.fixture
def enabled_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WANDB_API_KEY", "k")
    monkeypatch.setenv("WANDB_ENTITY", "e")
    monkeypatch.setenv("WANDB_MODE", "online")


def test_reconciliation_logs_to_prod_project(
    enabled_env: None,
    fake_wandb: FakeWandb,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a reconciliation completes for a run, the tracker logs one
    step to the prod-{area} run in the algo-prod project."""
    from schedules import reconciliation

    tracker = WandbTracker(wandb_module=fake_wandb)

    reconciliation._log_run_to_wandb(
        tracker=tracker,
        area="DK1",
        config_name="dk1_lear",
        target_date="2026-05-21",
        metrics={"mae": 4.5, "rmse": 6.1, "smape": 11.0},
    )

    call = fake_wandb.init_calls[0]
    assert call["project"] == "algo-prod"
    assert call["id"] == "prod-dk1-dk1_lear"
    assert fake_wandb.runs[0].logged[0][0]["mae"] == 4.5


def test_reconciliation_passes_model_artifact_id_to_wandb(
    enabled_env: None,
    fake_wandb: FakeWandb,
) -> None:
    """When the run has a model_artifact_id, it lands in the W&B step payload."""
    from schedules import reconciliation

    tracker = WandbTracker(wandb_module=fake_wandb)

    reconciliation._log_run_to_wandb(
        tracker=tracker,
        area="DK1",
        config_name="dk1_lear",
        target_date="2026-05-21",
        metrics={"mae": 4.5, "rmse": 6.1, "smape": 11.0},
        model_artifact_id="art-uuid-42",
    )

    payload = fake_wandb.runs[0].logged[0][0]
    assert payload["model_artifact_id"] == "art-uuid-42"


def test_reconciliation_omits_artifact_id_when_blank(
    enabled_env: None,
    fake_wandb: FakeWandb,
) -> None:
    """Empty-string artifact_id (the CH default for old runs) is treated as None."""
    from schedules import reconciliation

    tracker = WandbTracker(wandb_module=fake_wandb)

    reconciliation._log_run_to_wandb(
        tracker=tracker,
        area="DK1",
        config_name="dk1_lear",
        target_date="2026-05-21",
        metrics={"mae": 4.5},
        model_artifact_id="",
    )

    payload = fake_wandb.runs[0].logged[0][0]
    assert "model_artifact_id" not in payload
