"""Tracker-level no-op semantics."""

from __future__ import annotations

import pytest

from observability_wandb.tracker import WandbTracker

from tests.observability_wandb.conftest import FakeWandb


class TestNoOpWhenDisabled:
    def test_log_backtest_run_noops_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch, fake_wandb: FakeWandb
    ) -> None:
        monkeypatch.setenv("WANDB_MODE", "disabled")
        tracker = WandbTracker(wandb_module=fake_wandb)

        tracker.log_backtest_run(
            run_id="r1",
            config={"area": "DK1"},
            summary={"mae": 5.0},
            per_day=[],
            tags=[],
        )

        assert fake_wandb.init_calls == []
        assert fake_wandb.runs == []

    def test_enabled_when_key_present(
        self, enabled_env: None, fake_wandb: FakeWandb
    ) -> None:
        tracker = WandbTracker(wandb_module=fake_wandb)
        assert tracker.is_enabled is True
