"""Drift flow pushes one step per drift check to the prod-drift-{area} W&B run."""

from __future__ import annotations

import pytest

from observability_wandb.tracker import WandbTracker

from tests.observability_wandb.conftest import FakeWandb


@pytest.fixture
def enabled_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WANDB_API_KEY", "k")
    monkeypatch.setenv("WANDB_ENTITY", "e")
    monkeypatch.setenv("WANDB_MODE", "online")


def test_drift_logs_to_prod_drift_run(
    enabled_env: None,
    fake_wandb: FakeWandb,
) -> None:
    """The drift module's _log_drift_to_wandb helper posts one step to W&B."""
    from schedules import drift

    tracker = WandbTracker(wandb_module=fake_wandb)

    drift._log_drift_to_wandb(
        tracker=tracker,
        area="DK1",
        curve_name="ENTSOE DK1 EnergyPrice",
        target_date="2026-05-21",
        drift_score=0.12,
        drift_threshold=0.05,
        stat_test="ks",
        drift_detected=True,
    )

    call = fake_wandb.init_calls[0]
    assert call["project"] == "algo-prod"
    assert call["id"] == "prod-drift-dk1"

    payload = fake_wandb.runs[0].logged[0][0]
    assert payload["curve_name"] == "ENTSOE DK1 EnergyPrice"
    assert payload["drift_score"] == 0.12
    assert payload["drift_detected"] == 1


def test_drift_helper_swallows_tracker_errors(
    monkeypatch: pytest.MonkeyPatch,
    fake_wandb: FakeWandb,
) -> None:
    """A tracker exception must not abort the drift flow."""
    from schedules import drift

    class BoomTracker:
        def log_drift_event(self, **_: object) -> None:
            raise RuntimeError("boom")

    drift._log_drift_to_wandb(
        tracker=BoomTracker(),
        area="DK1",
        curve_name="ENTSOE DK1 EnergyPrice",
        target_date="2026-05-21",
        drift_score=0.12,
        drift_threshold=0.05,
        stat_test="ks",
        drift_detected=True,
    )
    # No exception bubbled. Nothing else to assert.
